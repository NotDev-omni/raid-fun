from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, field_validator


# ── User ──────────────────────────────────────────────────────────────────────

class UserPublic(BaseModel):
    id: int
    discord_username: Optional[str]   # None for X-only users
    discord_avatar: Optional[str]
    x_handle: Optional[str]
    x_handle_verified: bool
    x_avatar: Optional[str]           # avatar from X OAuth (may be richer than Discord's)
    grind_balance: int
    grind_earned_lifetime: int
    rank: str
    streak_days: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMe(UserPublic):
    discord_id: Optional[str]         # None for X-only users
    x_id: Optional[str]               # None for Discord-only users
    verification_code: Optional[str]
    last_raid_date: Optional[date]


# ── Raid ──────────────────────────────────────────────────────────────────────

class RaidPostCreate(BaseModel):
    tweet_url: str
    extra_hours: int = 0

    @field_validator("extra_hours")
    @classmethod
    def extra_hours_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("extra_hours must be >= 0")
        return v


class RaidClaimPublic(BaseModel):
    id: int
    raid_id: int
    raider_user_id: int
    raider_handle: Optional[str] = None
    reply_verified: bool
    reply_verified_at: Optional[datetime]
    mutual_claim_submitted: bool
    mutual_verified: bool
    mutual_verified_at: Optional[datetime]
    grind_awarded: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RaidPostPublic(BaseModel):
    id: int
    host_user_id: int
    host_username: Optional[str] = None
    host_avatar: Optional[str] = None
    tweet_url: str
    tweet_id: str
    grind_cost: int
    expires_at: datetime
    status: str
    created_at: datetime
    time_left_seconds: Optional[int] = None
    viewer_claim: Optional[RaidClaimPublic] = None

    model_config = {"from_attributes": True}


class RaidPostDetail(RaidPostPublic):
    claims: list[RaidClaimPublic] = []


# ── Auth ──────────────────────────────────────────────────────────────────────

class SetHandleRequest(BaseModel):
    x_handle: str

    @field_validator("x_handle")
    @classmethod
    def strip_at(cls, v: str) -> str:
        return v.lstrip("@").strip()


class SetHandleResponse(BaseModel):
    verification_code: str
    tweet_url: str


class VerifyHandleResponse(BaseModel):
    verified: bool
    message: str


# ── Grind ─────────────────────────────────────────────────────────────────────

class GrindBalance(BaseModel):
    balance: int
    rank: str
    grind_earned_lifetime: int
    streak_days: int


class GrindTransactionPublic(BaseModel):
    id: int
    amount: int
    type: str
    description: str
    related_raid_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Extend Raid ───────────────────────────────────────────────────────────────

class ExtendRaidRequest(BaseModel):
    hours: int

    @field_validator("hours")
    @classmethod
    def hours_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("hours must be at least 1")
        return v


# ── WebSocket events ──────────────────────────────────────────────────────────

class WSGrindEarned(BaseModel):
    type: str = "grind_earned"
    amount: int
    total: int
    description: str
    bonus: bool = False


class WSMutualAvailable(BaseModel):
    type: str = "mutual_available"
    claim_id: int
    raider_handle: str
    raid_id: int


class WSRaidExpiring(BaseModel):
    type: str = "raid_expiring"
    raid_id: int
    minutes_left: int


class WSLiveFeed(BaseModel):
    type: str = "live_feed"
    message: str
