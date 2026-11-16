from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.organization import Workspace, WorkspaceMember
from backend.app.schemas.user import WorkspaceCreate, WorkspaceResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

@router.get("/", response_model=List[WorkspaceResponse])
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workspaces = db.query(Workspace).filter(
        Workspace.organization_id == current_user.organization_id
    ).all()
    return workspaces

@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    request: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    workspace = Workspace(
        organization_id=current_user.organization_id,
        name=request.name,
        description=request.description
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="ADMIN"
    )
    db.add(member)
    db.commit()

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="WORKSPACE_CREATED",
        resource_type="WORKSPACE",
        resource_id=workspace.id,
        user_id=current_user.id,
        payload_after={"name": workspace.name}
    )

    return workspace

