from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user_dep
from database import get_db
from models import GrindTransaction, User
from schemas import GrindBalance, GrindTransactionPublic

router = APIRouter(prefix="/grind", tags=["grind"])


@router.get("/balance", response_model=GrindBalance)
def get_balance(current_user: User = Depends(get_current_user_dep)):
    """Current user's $GRIND balance, rank, and streak."""
    return GrindBalance(
        balance=current_user.grind_balance,
        rank=current_user.rank,
        grind_earned_lifetime=current_user.grind_earned_lifetime,
        streak_days=current_user.streak_days,
    )


@router.get("/transactions", response_model=list[GrindTransactionPublic])
def get_transactions(
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    """Last 50 $GRIND transactions for the current user."""
    txs = (
        db.query(GrindTransaction)
        .filter(GrindTransaction.user_id == current_user.id)
        .order_by(GrindTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    return txs
