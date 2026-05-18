import base64
import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import config
from database import get_db
from models import User, GrindTransaction
from schemas import UserMe, SetHandleRequest, SetHandleResponse, VerifyHandleResponse

# ── PKCE state store (in-memory; fine for single-process dev server) ──────────
# Maps  state_token -> code_verifier  for X OAuth flows in progress.
_x_oauth_states: dict[str, str] = {}

router = APIRouter(prefix="/auth", tags=["auth"])

# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_jwt(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_jwt(token: str) -> int:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    authorization: str = None,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — extracts Bearer token from Authorization header."""
    from fastapi import Request
    raise HTTPException(status_code=401, detail="Use get_current_user_from_request")


# Proper dependency that reads from the actual request
from fastapi import Request

def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth[len("Bearer "):]


def get_current_user_dep(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request)
    user_id = decode_jwt(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_optional_user_dep(
    request: Request,
    db: Session = Depends(get_db),
) -> "User | None":
    """Like get_current_user_dep but returns None instead of raising 401."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth[len("Bearer "):]
        user_id = decode_jwt(token)
        return db.query(User).filter(User.id == user_id).first()
    except HTTPException:
        return None


# ── Rank helper ───────────────────────────────────────────────────────────────

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


def award_grind(
    db: Session,
    user: User,
    amount: int,
    tx_type: str,
    description: str,
    related_raid_id: int | None = None,
) -> GrindTransaction:
    """
    Award (positive) or deduct (negative) $GRIND from user.
    Updates balance, lifetime total, and rank. Returns the created transaction.
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


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/discord")
def discord_login():
    """Redirect user to Discord OAuth2 authorization page."""
    params = (
        f"client_id={config.DISCORD_CLIENT_ID}"
        f"&redirect_uri={config.DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
    )
    return RedirectResponse(f"{config.DISCORD_OAUTH_URL}?{params}")


@router.get("/discord/callback")
def discord_callback(code: str = Query(...), db: Session = Depends(get_db)):
    """Exchange OAuth2 code for Discord token, create/update user, return JWT."""

    # Exchange code for access token
    try:
        with httpx.Client() as client:
            token_resp = client.post(
                config.DISCORD_TOKEN_URL,
                data={
                    "client_id": config.DISCORD_CLIENT_ID,
                    "client_secret": config.DISCORD_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": config.DISCORD_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Failed to obtain Discord access token")

            # Fetch Discord user info
            user_resp = client.get(
                f"{config.DISCORD_API_BASE}/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            user_resp.raise_for_status()
            discord_user = user_resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Discord API error: {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Discord connection error: {exc}")

    discord_id = discord_user["id"]
    discord_username = discord_user.get("username", "")
    avatar_hash = discord_user.get("avatar")
    discord_avatar = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"
        if avatar_hash
        else None
    )

    # Upsert user
    user = db.query(User).filter(User.discord_id == discord_id).first()
    is_new = user is None

    if is_new:
        user = User(
            discord_id=discord_id,
            discord_username=discord_username,
            discord_avatar=discord_avatar,
        )
        db.add(user)
        db.flush()  # get user.id before award_grind
        award_grind(db, user, 20, "signup_bonus", "Welcome bonus for joining raid-fun!")
    else:
        user.discord_username = discord_username
        user.discord_avatar = discord_avatar

    db.flush()
    jwt_token = create_jwt(user.id)

    return RedirectResponse(f"{config.FRONTEND_URL}/?token={jwt_token}")


@router.get("/me", response_model=UserMe)
def get_me(current_user: User = Depends(get_current_user_dep)):
    return current_user


@router.post("/set-handle", response_model=SetHandleResponse)
def set_handle(
    body: SetHandleRequest,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    """Save X/Twitter handle and generate verification code."""
    handle = body.x_handle

    # Check uniqueness (ignore current user's own handle)
    existing = (
        db.query(User)
        .filter(User.x_handle == handle, User.id != current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="That X handle is already linked to another account")

    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    current_user.x_handle = handle
    current_user.x_handle_verified = False
    current_user.verification_code = code

    tweet_text = f"Verifying+my+raid-fun+account+{code}"
    tweet_url = f"https://x.com/intent/tweet?text={tweet_text}"

    return SetHandleResponse(verification_code=code, tweet_url=tweet_url)


@router.get("/verify-handle", response_model=VerifyHandleResponse)
def verify_handle(
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    """Poll to check if X handle verification tweet has been found."""
    if not current_user.x_handle:
        raise HTTPException(status_code=400, detail="No X handle set. Call /auth/set-handle first.")

    if current_user.x_handle_verified:
        return VerifyHandleResponse(verified=True, message="X handle already verified")

    if not current_user.verification_code:
        raise HTTPException(status_code=400, detail="No verification code found. Call /auth/set-handle first.")

    if config.MOCK_MODE:
        # In mock mode, auto-verify immediately
        current_user.x_handle_verified = True
        current_user.verification_code = None
        return VerifyHandleResponse(verified=True, message="[MOCK] X handle verified successfully")

    # Real mode: use twscrape to search for the verification tweet
    try:
        import asyncio
        import twscrape

        async def _search():
            api = twscrape.API()
            query = f"from:{current_user.x_handle} \"{current_user.verification_code}\""
            async for tweet in api.search(query, limit=10):
                if current_user.verification_code in tweet.rawContent:
                    return True
            return False

        found = asyncio.run(_search())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"twscrape error: {exc}")

    if found:
        current_user.x_handle_verified = True
        current_user.verification_code = None
        return VerifyHandleResponse(verified=True, message="X handle verified successfully")

    return VerifyHandleResponse(verified=False, message="Verification tweet not found yet. Please tweet the code and try again.")


# ── X / Twitter OAuth 2.0 (PKCE) ─────────────────────────────────────────────

@router.get("/x")
def x_login():
    """Redirect user to X OAuth 2.0 authorization page (PKCE flow)."""
    # Generate PKCE pair
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _x_oauth_states[state] = code_verifier

    params = urlencode({
        "response_type": "code",
        "client_id": config.X_CLIENT_ID,
        "redirect_uri": config.X_REDIRECT_URI,
        "scope": "tweet.read users.read",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"{config.X_AUTH_URL}?{params}")


@router.get("/x/callback")
def x_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Exchange X OAuth2 code for access token, create/update user, return JWT."""
    # Validate PKCE state
    code_verifier = _x_oauth_states.pop(state, None)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # Exchange code for access token
    try:
        with httpx.Client() as client:
            token_resp = client.post(
                config.X_TOKEN_URL,
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": config.X_CLIENT_ID,
                    "redirect_uri": config.X_REDIRECT_URI,
                    "code_verifier": code_verifier,
                },
                # Basic auth with client_id:client_secret for confidential clients
                auth=(config.X_CLIENT_ID, config.X_CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Failed to obtain X access token")

            # Fetch X user profile
            user_resp = client.get(
                config.X_USER_URL,
                params={"user.fields": "profile_image_url"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            user_resp.raise_for_status()
            x_user = user_resp.json().get("data", {})

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"X API error: {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"X connection error: {exc}")

    x_id = x_user.get("id")
    if not x_id:
        raise HTTPException(status_code=502, detail="Could not fetch X user ID")

    x_username = x_user.get("username", "")
    x_avatar_raw = x_user.get("profile_image_url")
    # Strip Twitter's _normal suffix to get a larger avatar
    x_avatar = x_avatar_raw.replace("_normal", "") if x_avatar_raw else None

    # Upsert: look up by x_id first
    user = db.query(User).filter(User.x_id == x_id).first()
    is_new = user is None

    if is_new:
        # If a Discord-authed user already claimed this handle, link it
        existing_by_handle = (
            db.query(User)
            .filter(User.x_handle == x_username, User.x_id.is_(None))
            .first()
        )
        if existing_by_handle:
            # Attach the X identity to their existing account
            user = existing_by_handle
            user.x_id = x_id
            user.x_handle_verified = True
            if x_avatar:
                user.x_avatar = x_avatar
        else:
            # Brand-new user via X
            user = User(
                x_id=x_id,
                x_handle=x_username,
                x_handle_verified=True,
                x_avatar=x_avatar,
            )
            db.add(user)
            db.flush()
            award_grind(db, user, 20, "signup_bonus", "Welcome bonus for joining raid-fun!")
    else:
        # Returning X user — refresh handle and avatar
        user.x_handle = x_username
        user.x_handle_verified = True
        if x_avatar:
            user.x_avatar = x_avatar

    db.flush()
    jwt_token = create_jwt(user.id)
    return RedirectResponse(f"{config.FRONTEND_URL}/?token={jwt_token}")
