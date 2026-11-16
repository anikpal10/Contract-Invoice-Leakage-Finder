from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from backend.app.core.database import get_db
from backend.app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.models.user import User, UserRole
from backend.app.models.organization import Organization, Workspace, WorkspaceMember
from backend.app.models.rule_config import RuleConfiguration
from backend.app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, RegisterRequest
from backend.app.schemas.user import UserResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )

    # Create slug from organization name
    base_slug = "".join(c.lower() if c.isalnum() else "-" for c in request.organization_name).strip("-")
    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create organization
    org = Organization(name=request.organization_name, slug=slug)
    db.add(org)
    db.flush()

    # Create user
    user = User(
        organization_id=org.id,
        email=request.email.lower(),
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
        role=UserRole.ADMIN.value,
        is_active=True
    )
    db.add(user)
    db.flush()

    # Create default workspace
    workspace = Workspace(
        organization_id=org.id,
        name="General Workspace",
        description="Default operational workspace for financial leak reviews"
    )
    db.add(workspace)
    db.flush()

    # Add user to workspace
    ws_member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="ADMIN"
    )
    db.add(ws_member)

    # Initialize default v1 RuleConfiguration for this tenant
    default_rule_config = RuleConfiguration(
        organization_id=org.id,
        version=1,
        is_active=True,
        price_variance_tolerance_pct=0.00,
        price_variance_tolerance_abs=0.00,
        quantity_variance_tolerance_pct=0.00,
        duplicate_window_days=90,
        fuzzy_match_threshold=85,
        high_severity_threshold=500.00,
        critical_severity_threshold=2500.00,
        require_grn_for_goods=True,
        created_by_id=user.id,
        change_reason="Initial baseline configuration"
    )
    db.add(default_rule_config)
    db.commit()

    log_audit_event(
        db=db,
        organization_id=org.id,
        action="USER_REGISTERED",
        resource_type="ORGANIZATION",
        resource_id=org.id,
        user_id=user.id,
        payload_after={"email": user.email, "organization": org.name}
    )

    access_token = create_access_token(data={"sub": user.id, "org": org.id, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.id, "org": org.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_id=org.id,
        organization_name=org.name
    )

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    lookup_email = (request.email or request.username or "").strip().lower()
    if not lookup_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username is required")

    user = db.query(User).filter(User.email == lookup_email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is disabled")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    access_token = create_access_token(data={"sub": user.id, "org": user.organization_id, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.id, "org": user.organization_id})

    log_audit_event(
        db=db,
        organization_id=user.organization_id,
        action="USER_LOGIN",
        resource_type="USER",
        resource_id=user.id,
        user_id=user.id
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=org.name if org else "Unknown Org"
    )

@router.post("/token", response_model=TokenResponse)
def login_oauth2_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password form login compatible with Swagger UI /docs Authorize button."""
    lookup_email = form_data.username.strip().lower()
    user = db.query(User).filter(User.email == lookup_email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is disabled")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    access_token = create_access_token(data={"sub": user.id, "org": user.organization_id, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.id, "org": user.organization_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=org.name if org else "Unknown Org"
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(request.refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    new_access_token = create_access_token(data={"sub": user.id, "org": user.organization_id, "role": user.role})
    new_refresh_token = create_refresh_token(data={"sub": user.id, "org": user.organization_id})

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=org.name if org else ""
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

