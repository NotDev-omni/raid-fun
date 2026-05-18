"""
APScheduler background job — runs every 30 seconds.
Handles:
  1. Reply verification
  2. Mutual engagement verification
  3. Raid expiry
  4. Expiry warnings (30 min before)
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from database import get_db_ctx
from models import RaidClaim, RaidPost, User
from services.grind_service import award_grind, compute_reply_reward, update_streak
from services.ws_manager import manager as ws_manager
import config

logger = logging.getLogger(__name__)


# ── twscrape helpers ──────────────────────────────────────────────────────────

_tws_api = None


def _get_tws_api():
    global _tws_api
    if _tws_api is not None:
        return _tws_api

    if config.MOCK_MODE or not config.TWS_ACCOUNTS:
        return None

    try:
        import twscrape
        api = twscrape.API()

        async def _add_accounts():
            for entry in config.TWS_ACCOUNTS.split(","):
                parts = entry.strip().split(":")
                if len(parts) == 4:
                    username, password, email, email_password = parts
                    await api.pool.add_account(username, password, email, email_password)
            await api.pool.login_all()

        asyncio.run(_add_accounts())
        _tws_api = api
        logger.info("twscrape API initialised with accounts")
    except Exception as exc:
        logger.error("Failed to initialise twscrape: %s", exc)
        return None

    return _tws_api


# ── reply verification ────────────────────────────────────────────────────────

async def _verify_reply_real(tweet_id: str, raider_handle: str) -> bool:
    api = _get_tws_api()
    if api is None:
        return False
    try:
        async for tweet in api.tweet_replies(int(tweet_id), limit=100):
            if tweet.user and tweet.user.username.lower() == raider_handle.lower():
                return True
    except Exception as exc:
        logger.error("twscrape tweet_replies error for %s: %s", tweet_id, exc)
    return False


def _should_mock_verify(claim_created_at: datetime) -> bool:
    """In mock mode, auto-verify claims that are at least 5 seconds old."""
    now = datetime.now(timezone.utc)
    created = claim_created_at.replace(tzinfo=timezone.utc) if claim_created_at.tzinfo is None else claim_created_at
    return (now - created).total_seconds() >= 5


# ── main scheduler job ────────────────────────────────────────────────────────

async def run_verification_cycle():
    """Async core of the verification job — called from the sync scheduler wrapper."""
    now = datetime.now(timezone.utc)

    with get_db_ctx() as db:
        # ── 1. Reply verification ────────────────────────────────────────────
        pending_claims = (
            db.query(RaidClaim)
            .filter(RaidClaim.status == "pending", RaidClaim.reply_verified == False)
            .all()
        )

        for claim in pending_claims:
            raid: RaidPost = claim.raid
            raider: User = claim.raider_user

            if raid is None or raider is None:
                continue

            if raid.status != "active":
                claim.status = "failed"
                continue

            # Determine if verified
            verified = False
            if config.MOCK_MODE:
                verified = _should_mock_verify(claim.created_at)
            else:
                verified = await _verify_reply_real(raid.tweet_id, raider.x_handle or "")

            if verified:
                claim.reply_verified = True
                claim.reply_verified_at = now

                # Update streak before computing reward
                update_streak(raider)
                earned, signal_boost = compute_reply_reward(raider)

                tx = award_grind(
                    db,
                    raider,
                    earned,
                    "raid_reply",
                    f"Verified reply on raid #{raid.id}" + (" [Signal Boost!]" if signal_boost else ""),
                    related_raid_id=raid.id,
                )
                claim.grind_awarded += earned

                # Notify raider via WS
                await ws_manager.send_to_user(raider.id, {
                    "type": "grind_earned",
                    "amount": earned,
                    "total": raider.grind_balance,
                    "description": tx.description,
                    "bonus": signal_boost,
                })

                # Live feed broadcast
                handle_display = f"@{raider.x_handle}" if raider.x_handle else raider.discord_username
                await ws_manager.broadcast({
                    "type": "live_feed",
                    "message": f"{handle_display} earned {earned} $GRIND raiding",
                })

                # Notify host that mutual is now available
                host: User = raid.host_user
                if host and raider.x_handle:
                    await ws_manager.send_to_user(host.id, {
                        "type": "mutual_available",
                        "claim_id": claim.id,
                        "raider_handle": raider.x_handle,
                        "raid_id": raid.id,
                    })

                logger.info(
                    "Reply verified: claim_id=%s raider=%s earned=%s signal_boost=%s",
                    claim.id, raider.discord_username, earned, signal_boost,
                )

        # ── 2. Mutual verification ───────────────────────────────────────────
        mutual_pending = (
            db.query(RaidClaim)
            .filter(
                RaidClaim.reply_verified == True,
                RaidClaim.mutual_claim_submitted == True,
                RaidClaim.mutual_verified == False,
            )
            .all()
        )

        for claim in mutual_pending:
            raid: RaidPost = claim.raid
            raider: User = claim.raider_user
            host: User = raid.host_user if raid else None

            if raid is None or raider is None or host is None:
                continue

            verified = False
            if config.MOCK_MODE:
                verified = _should_mock_verify(claim.created_at)
            else:
                # Search for a reply from host to raider within last 3 hours
                api = _get_tws_api()
                if api:
                    try:
                        cutoff = now - timedelta(hours=3)
                        query = f"from:{host.x_handle} to:{raider.x_handle}"
                        async for tweet in api.search(query, limit=10):
                            tweet_created = tweet.date.replace(tzinfo=timezone.utc) if tweet.date.tzinfo is None else tweet.date
                            if tweet_created >= cutoff:
                                verified = True
                                break
                    except Exception as exc:
                        logger.error("twscrape mutual search error: %s", exc)

            if verified:
                claim.mutual_verified = True
                claim.mutual_verified_at = now
                claim.status = "verified"

                # Award both parties
                for recipient in (raider, host):
                    tx = award_grind(
                        db,
                        recipient,
                        5,
                        "mutual_bonus",
                        f"Mutual engagement bonus for raid #{raid.id}",
                        related_raid_id=raid.id,
                    )
                    await ws_manager.send_to_user(recipient.id, {
                        "type": "grind_earned",
                        "amount": 5,
                        "total": recipient.grind_balance,
                        "description": tx.description,
                        "bonus": False,
                    })

                claim.grind_awarded += 5  # raider's share logged on claim

                logger.info("Mutual verified: claim_id=%s", claim.id)

        # ── 3. Expire raids ──────────────────────────────────────────────────
        expired_raids = (
            db.query(RaidPost)
            .filter(RaidPost.status == "active", RaidPost.expires_at < now)
            .all()
        )
        for raid in expired_raids:
            raid.status = "expired"
            logger.info("Raid expired: raid_id=%s", raid.id)

        # ── 4. Expiry warnings (30 minutes) ──────────────────────────────────
        warning_window_start = now + timedelta(minutes=29)
        warning_window_end = now + timedelta(minutes=31)
        expiring_soon = (
            db.query(RaidPost)
            .filter(
                RaidPost.status == "active",
                RaidPost.expires_at >= warning_window_start,
                RaidPost.expires_at <= warning_window_end,
            )
            .all()
        )
        for raid in expiring_soon:
            minutes_left = int((raid.expires_at.replace(tzinfo=timezone.utc) - now).total_seconds() / 60)
            await ws_manager.send_to_user(raid.host_user_id, {
                "type": "raid_expiring",
                "raid_id": raid.id,
                "minutes_left": minutes_left,
            })
            logger.info("Expiry warning sent: raid_id=%s minutes_left=%s", raid.id, minutes_left)


def verification_job():
    """Synchronous wrapper called by APScheduler."""
    try:
        asyncio.run(run_verification_cycle())
    except Exception as exc:
        logger.error("Verification job error: %s", exc, exc_info=True)
