from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role
from backend.app.core.security import get_password_hash
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserUpdate, UserResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/users", tags=["User Management"])

@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Tenant isolated listing
    users = db.query(User).filter(User.organization_id == current_user.organization_id).all()
    return users

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    existing = db.query(User).filter(User.email == request.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = User(
        organization_id=current_user.organization_id,
        email=request.email.lower(),
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
        role=request.role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="USER_CREATED",
        resource_type="USER",
        resource_id=new_user.id,
        user_id=current_user.id,
        payload_after={"email": new_user.email, "role": new_user.role}
    )

    return new_user

@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    target_user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == current_user.organization_id
    ).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    payload_before = {"full_name": target_user.full_name, "role": target_user.role, "is_active": target_user.is_active}
    
    if request.full_name is not None:
        target_user.full_name = request.full_name
    if request.role is not None:
        target_user.role = request.role
    if request.is_active is not None:
        target_user.is_active = request.is_active

    db.commit()
    db.refresh(target_user)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="USER_UPDATED",
        resource_type="USER",
        resource_id=target_user.id,
        user_id=current_user.id,
        payload_before=payload_before,
        payload_after={"full_name": target_user.full_name, "role": target_user.role, "is_active": target_user.is_active}
    )

    return target_user

