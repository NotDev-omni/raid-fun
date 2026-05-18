from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Boolean, DateTime, Date, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Discord auth fields (nullable — user may have logged in via X instead)
    discord_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    discord_username: Mapped[str | None] = mapped_column(String, nullable=True)
    discord_avatar: Mapped[str | None] = mapped_column(String, nullable=True)
    # X / Twitter auth fields
    x_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    x_avatar: Mapped[str | None] = mapped_column(String, nullable=True)
    x_handle: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    x_handle_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[str | None] = mapped_column(String, nullable=True)
    grind_balance: Mapped[int] = mapped_column(Integer, default=20)
    grind_earned_lifetime: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[str] = mapped_column(String, default="ANON")
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_raid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    hosted_raids: Mapped[list["RaidPost"]] = relationship(
        "RaidPost", back_populates="host_user", foreign_keys="RaidPost.host_user_id"
    )
    raid_claims: Mapped[list["RaidClaim"]] = relationship(
        "RaidClaim", back_populates="raider_user", foreign_keys="RaidClaim.raider_user_id"
    )
    transactions: Mapped[list["GrindTransaction"]] = relationship(
        "GrindTransaction", back_populates="user"
    )


class RaidPost(Base):
    __tablename__ = "raid_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    host_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tweet_url: Mapped[str] = mapped_column(String, nullable=False)
    tweet_id: Mapped[str] = mapped_column(String, nullable=False)
    grind_cost: Mapped[int] = mapped_column(Integer, default=50)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")  # active/expired/completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    host_user: Mapped["User"] = relationship(
        "User", back_populates="hosted_raids", foreign_keys=[host_user_id]
    )
    claims: Mapped[list["RaidClaim"]] = relationship("RaidClaim", back_populates="raid")


class RaidClaim(Base):
    __tablename__ = "raid_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raid_id: Mapped[int] = mapped_column(Integer, ForeignKey("raid_posts.id"), nullable=False)
    raider_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reply_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mutual_claim_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    mutual_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mutual_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grind_awarded: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/verified/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    raid: Mapped["RaidPost"] = relationship("RaidPost", back_populates="claims")
    raider_user: Mapped["User"] = relationship(
        "User", back_populates="raid_claims", foreign_keys=[raider_user_id]
    )


class GrindTransaction(Base):
    __tablename__ = "grind_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # positive=earned negative=spent
    type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    related_raid_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
