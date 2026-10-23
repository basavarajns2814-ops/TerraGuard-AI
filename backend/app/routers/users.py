from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import User
from app.schemas import UserResponse, UserCreate
from app.core.security import get_password_hash
from app.core.deps import get_current_user, require_roles, log_audit

router = APIRouter(prefix="/api/users", tags=["User & Role Management"])

@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserResponse.model_validate(u) for u in users]

@router.get("/officers", response_model=List[UserResponse])
def list_officers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    users = db.query(User).filter(User.is_active == True).all()
    return [UserResponse.model_validate(u) for u in users]

@router.post("", response_model=UserResponse)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed_pw = get_password_hash(req.password)
    new_user = User(
        email=req.email,
        hashed_password=hashed_pw,
        full_name=req.full_name,
        role=req.role,
        department=req.department,
        badge_number=req.badge_number,
        is_active=req.is_active,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(db, current_user.email, "CREATE_USER", "USER", str(new_user.id), f"Created user {new_user.email} with role {new_user.role}")
    return UserResponse.model_validate(new_user)

@router.put("/{user_id}/toggle-status", response_model=UserResponse)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)

    log_audit(db, current_user.email, "TOGGLE_USER_STATUS", "USER", str(user.id), f"Status set to {user.is_active}")
    return UserResponse.model_validate(user)
