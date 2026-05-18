"""
Shared $GRIND economy helpers used by both routes and the verifier service.
"""
import random
from datetime import date
from sqlalchemy.orm import Session

from models import User, GrindTransaction

RANK_THRESHOLDS = [
    (5000, "GIGACHAD"),
    (1500, "BASED"),
    (500,  "RAIDER"),
    (100,  "SIGNAL"),
    (0,    "ANON"),
]


def compute_rank(lifetime: int) -> str:
    for threshold, rank in RANK_THRESHOLDS:
        if lifetime >= threshold:
            return rank
    return "ANON"


def streak_multiplier(streak_days: int) -> float:
    if streak_days >= 14:
        return 1.5
    if streak_days >= 7:
        return 1.25
    if streak_days >= 3:
        return 1.1
    return 1.0


def award_grind(
    db: Session,
    user: User,
    amount: int,
    tx_type: str,
    description: str,
    related_raid_id: int | None = None,
) -> GrindTransaction:
    """
    Award (positive) or deduct (negative) $GRIND.
    Updates balance, lifetime earnings, and rank.
    Returns the GrindTransaction (not yet committed — caller must commit).
    """
    user.grind_balance += amount
    if amount > 0:
        user.grind_earned_lifetime += amount
    user.rank = compute_rank(user.grind_earned_lifetime)

    tx = GrindTransaction(
        user_id=user.id,
        amount=amount,
        type=tx_type,
        description=description,
        related_raid_id=related_raid_id,
    )
    db.add(tx)
    db.flush()
    return tx


def update_streak(user: User) -> None:
    """Update streak based on today's date. Call after a successful raid action."""
    today = date.today()
    if user.last_raid_date is None:
        user.streak_days = 1
    else:
        delta = (today - user.last_raid_date).days
        if delta == 0:
            pass  # same day, no change
        elif delta == 1:
            user.streak_days += 1
        else:
            user.streak_days = 1  # streak broken
    user.last_raid_date = today


def compute_reply_reward(user: User) -> tuple[int, bool]:
    """
    Returns (total_grind, signal_boost_triggered).
    Base reward = 15, multiplied by streak, rounded to int.
    20% chance of +random(5,10) signal boost.
    """
    base = 15
    multiplier = streak_multiplier(user.streak_days)
    earned = int(base * multiplier)

    signal_boost = random.random() < 0.20
    if signal_boost:
        earned += random.randint(5, 10)

    return earned, signal_boost
