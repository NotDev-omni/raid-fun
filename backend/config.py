import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET: str = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI: str = os.getenv(
    "DISCORD_REDIRECT_URI", "http://localhost:8000/auth/discord/callback"
)

JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme-in-production")
JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./raidfun.db")

MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")

TWS_ACCOUNTS: str = os.getenv("TWS_ACCOUNTS", "")

FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5500")

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"

# ── X / Twitter OAuth 2.0 ─────────────────────────────────────────────────────
X_CLIENT_ID: str = os.getenv("X_CLIENT_ID", "")
X_CLIENT_SECRET: str = os.getenv("X_CLIENT_SECRET", "")
X_REDIRECT_URI: str = os.getenv(
    "X_REDIRECT_URI", "http://localhost:8000/auth/x/callback"
)
X_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
X_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
X_USER_URL = "https://api.twitter.com/2/users/me"
