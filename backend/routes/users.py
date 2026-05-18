from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/leaderboard", response_model=list[UserPublic])
def leaderboard(db: Session = Depends(get_db)):
    """Top 20 users by lifetime $GRIND earned."""
    users = (
        db.query(User)
        .order_by(User.grind_earned_lifetime.desc())
        .limit(20)
        .all()
    )
    return users


@router.get("/{user_id}", response_model=UserPublic)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Public profile for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
