# raid-fun — Project Summary for Claude

## What This Is
A social raiding platform for the IDOL64 community. Users log in with X (Twitter) or Discord, post their X posts as "raids", and other community members reply/engage to earn $GRIND tokens. Ranks up over time: ANON → SIGNAL → RAIDER → BASED → GIGACHAD.

## How to Run Locally

**Backend** — double-click `RUN_BACKEND.bat` in the root folder.
- Kills anything on port 8000, starts FastAPI on `http://localhost:8000`
- The bat file is at `C:\Users\belha\OneDrive\Bureau\raid-fun\RUN_BACKEND.bat`

**Frontend** — double-click `START_FRONTEND.bat` in the root folder, or just open `http://localhost:5500` in Chrome if it's already running via Live Server.

## Tech Stack
- **Backend**: Python, FastAPI, SQLite (SQLAlchemy), APScheduler, uvicorn
- **Frontend**: Vanilla JS PWA (no framework), HTML/CSS, service worker
- **Auth**: X OAuth 2.0 (PKCE) + Discord OAuth 2.0
- **Real-time**: WebSockets (FastAPI + custom WS manager)
- **Tweet verification**: twscrape (scraping, no paid API needed)

## Folder Structure
```
raid-fun/
├── backend/
│   ├── main.py           # FastAPI app, lifespan, CORS, WebSocket endpoint
│   ├── auth.py           # JWT helpers + /auth/discord + /auth/x OAuth routes
│   ├── config.py         # Loads .env values
│   ├── database.py       # SQLAlchemy engine, session, init_db (with auto-migration)
│   ├── models.py         # User, RaidPost, RaidClaim, GrindTransaction
│   ├── schemas.py        # Pydantic schemas
│   ├── run.py            # Pre-bind socket launcher (fixes port race condition on Windows)
│   ├── .env              # Secrets (Discord, X, JWT, DB URL)
│   ├── raidfun.db        # SQLite database (auto-created)
│   ├── routes/
│   │   ├── raids.py      # POST/GET raid endpoints
│   │   ├── users.py      # /leaderboard, /users/:id
│   │   └── grind.py      # $GRIND balance, transactions, history
│   └── services/
│       ├── verifier.py   # APScheduler job: verifies replies, mutual engagement, expires raids
│       ├── grind_service.py  # award_grind, streak logic, reply reward calculation
│       └── ws_manager.py     # WebSocket connection manager
├── frontend/
│   ├── index.html        # Single-page app shell (all views)
│   ├── app.js            # All frontend logic (~1000 lines)
│   ├── style.css         # Dark theme, monospace font
│   ├── sw.js             # Service worker (caches app.js/style.css, NOT index.html)
│   └── manifest.json     # PWA manifest
├── RUN_BACKEND.bat       # ← USE THIS to start backend
├── START_FRONTEND.bat    # ← USE THIS to start frontend
└── CLAUDE.md             # This file
```

## Environment Variables (`backend/.env`)
```
DISCORD_CLIENT_ID=1503879259180240987
DISCORD_CLIENT_SECRET=pn_RuO6hLZeh2BYm3LQT99llq7dQBp18
DISCORD_REDIRECT_URI=http://localhost:8000/auth/discord/callback
JWT_SECRET=idol64-raid-fun-super-secret-key-2026-xK9mP3nQ
DATABASE_URL=sqlite:///./raidfun.db
MOCK_MODE=true
FRONTEND_URL=http://localhost:5500
X_CLIENT_ID=b3R5bTIzaFN2dlZkNGFGUGVTWjk6MTpjaQ
X_CLIENT_SECRET=DkvJ9l9zXJRfz5Qfs-1N44EXZsP-AWINR-Dm2vOpyUQw8xbFdN
X_REDIRECT_URI=http://localhost:8000/auth/x/callback
```

## Auth Flow

### Sign in with X (primary — recommended)
1. User clicks "Sign in with X" → frontend calls `GET /auth/x`
2. Backend generates PKCE pair + state, redirects to `https://twitter.com/i/oauth2/authorize`
3. User authorizes on X → X redirects to `GET /auth/x/callback?code=...&state=...`
4. Backend exchanges code for token, fetches X profile (username, avatar)
5. User created/updated in DB with `x_handle_verified=True` (no manual verification needed)
6. JWT returned → frontend stores as `localStorage.raidfun_token` → goes straight to feed

### Login with Discord (secondary)
1. User clicks "Login with Discord" → `GET /auth/discord` → Discord OAuth
2. On callback, user created in DB but `x_handle_verified=False`
3. Frontend shows "link your X account" step where user enters handle + tweets a code
4. Verification job (runs every 30s) checks for the tweet via twscrape

## Current Status
- ✅ X OAuth login working end-to-end
- ✅ Discord OAuth login working end-to-end
- ✅ Feed (active raids), Post raid, Profile, Alerts views
- ✅ $GRIND balance, rank, streak tracking
- ✅ WebSocket real-time updates (grind earned, live feed ticker)
- ✅ APScheduler verification job (reply verification, mutual verification, raid expiry)
- ✅ MOCK_MODE=true (auto-verifies everything instantly for local dev)
- ✅ Auto-migration for DB columns on startup

## Known Issues / What To Work On Next
- Service worker was caching `index.html` causing stale UI — fixed (sw.js v2 now network-first for HTML)
- Discord login users still need the "link X handle" step — can be removed if Discord-only users are no longer needed
- No Discord server membership check yet (planned: verify user is in the IDOL64 Discord before allowing access)
- `MOCK_MODE=true` means tweet verification is instant — set to `false` for production with twscrape accounts
- No deployment yet — runs locally only. For production: needs real domain, HTTPS, and updated OAuth callback URLs

## Key Technical Notes
- **Port 8000 race condition fix**: `run.py` pre-binds the socket before uvicorn lifespan, preventing "port already in use" errors on Windows/OneDrive
- **JWT key**: frontend stores token as `localStorage.raidfun_token` (not `token`)
- **DB auto-migration**: `database.py`'s `_auto_migrate_columns()` adds missing columns on startup without losing data
- **X OAuth app**: Created at developer.twitter.com under project "Pay Per Use", app name "Raid-Fun", type "Web App (confidential client)"
