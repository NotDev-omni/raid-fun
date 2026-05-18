import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user_dep, get_optional_user_dep
from database import get_db
from models import RaidClaim, RaidPost, User
from schemas import (
    ExtendRaidRequest,
    RaidClaimPublic,
    RaidPostCreate,
    RaidPostDetail,
    RaidPostPublic,
)
from services.grind_service import award_grind

router = APIRouter(prefix="/raids", tags=["raids"])

TWEET_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter|x)\.com/\w+/status/(\d+)"
)


def _extract_tweet_id(url: str) -> str:
    m = TWEET_URL_RE.search(url)
    if not m:
        raise HTTPException(
            status_code=422, detail="Invalid tweet URL. Expected format: https://x.com/username/status/1234567890"
        )
    return m.group(1)


def _time_left(raid: RaidPost) -> int:
    now = datetime.now(timezone.utc)
    expires = raid.expires_at.replace(tzinfo=timezone.utc) if raid.expires_at.tzinfo is None else raid.expires_at
    return max(0, int((expires - now).total_seconds()))


def _claim_to_schema(claim: RaidClaim) -> RaidClaimPublic:
    raider_handle = claim.raider_user.x_handle if claim.raider_user else None
    return RaidClaimPublic(
        id=claim.id,
        raid_id=claim.raid_id,
        raider_user_id=claim.raider_user_id,
        raider_handle=raider_handle,
        reply_verified=claim.reply_verified,
        reply_verified_at=claim.reply_verified_at,
        mutual_claim_submitted=claim.mutual_claim_submitted,
        mutual_verified=claim.mutual_verified,
        mutual_verified_at=claim.mutual_verified_at,
        grind_awarded=claim.grind_awarded,
        status=claim.status,
        created_at=claim.created_at,
    )


def _raid_to_public(raid: RaidPost, viewer_id: int | None = None) -> RaidPostPublic:
    viewer_claim = None
    if viewer_id is not None:
        for c in raid.claims:
            if c.raider_user_id == viewer_id:
                viewer_claim = _claim_to_schema(c)
                break

    return RaidPostPublic(
        id=raid.id,
        host_user_id=raid.host_user_id,
        host_username=raid.host_user.discord_username if raid.host_user else None,
        host_avatar=raid.host_user.discord_avatar if raid.host_user else None,
        tweet_url=raid.tweet_url,
        tweet_id=raid.tweet_id,
        grind_cost=raid.grind_cost,
        expires_at=raid.expires_at,
        status=raid.status,
        created_at=raid.created_at,
        time_left_seconds=_time_left(raid),
        viewer_claim=viewer_claim,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RaidPostPublic])
def list_raids(
    db: Session = Depends(get_db),
    current_user: "User | None" = Depends(get_optional_user_dep),
):
    """List active raids, newest first."""
    raids = (
        db.query(RaidPost)
        .filter(RaidPost.status == "active")
        .order_by(RaidPost.created_at.desc())
        .all()
    )
    viewer_id = current_user.id if current_user else None
    return [_raid_to_public(r, viewer_id) for r in raids]


@router.get("/authed", response_model=list[RaidPostPublic])
def list_raids_authed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """List active raids with viewer's claim status (authenticated)."""
    raids = (
        db.query(RaidPost)
        .filter(RaidPost.status == "active")
        .order_by(RaidPost.created_at.desc())
        .all()
    )
    return [_raid_to_public(r, current_user.id) for r in raids]


@router.post("", response_model=RaidPostPublic, status_code=201)
def create_raid(
    body: RaidPostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Post a new raid. Costs 50 $GRIND + 10 per extra hour."""
    total_cost = 50 + body.extra_hours * 10
    if current_user.grind_balance < total_cost:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient $GRIND. Need {total_cost}, have {current_user.grind_balance}.",
        )

    tweet_id = _extract_tweet_id(body.tweet_url)

    # Deduct balance
    award_grind(
        db,
        current_user,
        -total_cost,
        "post_raid",
        f"Posted raid for tweet {tweet_id}" + (f" (+{body.extra_hours}h)" if body.extra_hours else ""),
    )

    expires_at = datetime.now(timezone.utc) + timedelta(hours=2 + body.extra_hours)

    raid = RaidPost(
        host_user_id=current_user.id,
        tweet_url=body.tweet_url,
        tweet_id=tweet_id,
        grind_cost=total_cost,
        expires_at=expires_at,
        status="active",
    )
    db.add(raid)
    db.flush()

    return _raid_to_public(raid, current_user.id)


@router.get("/{raid_id}", response_model=RaidPostDetail)
def get_raid(
    raid_id: int,
    db: Session = Depends(get_db),
):
    raid = db.query(RaidPost).filter(RaidPost.id == raid_id).first()
    if not raid:
        raise HTTPException(status_code=404, detail="Raid not found")

    claims = [_claim_to_schema(c) for c in raid.claims]

    return RaidPostDetail(
        **_raid_to_public(raid).model_dump(),
        claims=claims,
    )


@router.post("/{raid_id}/claim", response_model=RaidClaimPublic, status_code=201)
def claim_raid(
    raid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Claim a raid (raider is submitting their reply for verification)."""
    raid = db.query(RaidPost).filter(RaidPost.id == raid_id).first()
    if not raid:
        raise HTTPException(status_code=404, detail="Raid not found")
    if raid.status != "active":
        raise HTTPException(status_code=409, detail="Raid is no longer active")
    if raid.host_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot claim your own raid")
    if not current_user.x_handle_verified:
        raise HTTPException(status_code=403, detail="You must verify your X handle before raiding")

    existing = (
        db.query(RaidClaim)
        .filter(RaidClaim.raid_id == raid_id, RaidClaim.raider_user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="You have already claimed this raid")

    claim = RaidClaim(
        raid_id=raid_id,
        raider_user_id=current_user.id,
        status="pending",
    )
    db.add(claim)
    db.flush()

    return _claim_to_schema(claim)


@router.post("/{raid_id}/mutual/{claim_id}", response_model=RaidClaimPublic)
def submit_mutual(
    raid_id: int,
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Host marks that they have replied to the raider (mutual engagement)."""
    raid = db.query(RaidPost).filter(RaidPost.id == raid_id).first()
    if not raid:
        raise HTTPException(status_code=404, detail="Raid not found")
    if raid.host_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the raid host can submit mutual engagement")

    claim = (
        db.query(RaidClaim)
        .filter(RaidClaim.id == claim_id, RaidClaim.raid_id == raid_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if not claim.reply_verified:
        raise HTTPException(status_code=409, detail="Raider's reply has not been verified yet")
    if claim.mutual_claim_submitted:
        raise HTTPException(status_code=409, detail="Mutual engagement already submitted")

    claim.mutual_claim_submitted = True

    return _claim_to_schema(claim)


@router.post("/{raid_id}/extend", response_model=RaidPostPublic)
def extend_raid(
    raid_id: int,
    body: ExtendRaidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Extend a raid's expiry. Costs 10 $GRIND per hour."""
    raid = db.query(RaidPost).filter(RaidPost.id == raid_id).first()
    if not raid:
        raise HTTPException(status_code=404, detail="Raid not found")
    if raid.host_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the raid host can extend the raid")
    if raid.status != "active":
        raise HTTPException(status_code=409, detail="Cannot extend an inactive raid")

    cost = body.hours * 10
    if current_user.grind_balance < cost:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient $GRIND. Need {cost}, have {current_user.grind_balance}.",
        )

    award_grind(
        db,
        current_user,
        -cost,
        "extend_raid",
        f"Extended raid #{raid_id} by {body.hours}h",
        related_raid_id=raid_id,
    )

    current_expires = raid.expires_at.replace(tzinfo=timezone.utc) if raid.expires_at.tzinfo is None else raid.expires_at
    raid.expires_at = current_expires + timedelta(hours=body.hours)

    return _raid_to_public(raid, current_user.id)
