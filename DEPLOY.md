# raid-fun — Deployment Guide

**Stack:** Render (backend, free) + Netlify (frontend, free)
**Time:** ~20 minutes

---

## Overview

```
GitHub repo
    ├── backend/  →  Render (free web service)  →  https://raid-fun-backend.onrender.com
    └── frontend/ →  Netlify (free static site)  →  https://raid-fun.netlify.app
```

---

## Step 1 — Push your code to GitHub

If you haven't already:

```bash
cd C:\Users\belha\OneDrive\Bureau\raid-fun
git init
git add .
git commit -m "initial commit"
```

Then create a repo on https://github.com/new and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/raid-fun.git
git push -u origin main
```

> **Note:** The `backend/.env` file contains secrets. Make sure `.env` is in your `.gitignore` so it's not pushed to GitHub. You'll add those values manually in Render's dashboard.

---

## Step 2 — Deploy the backend on Render (free)

1. Go to https://render.com and sign up / log in.
2. Click **New → Web Service**.
3. Connect your GitHub repo.
4. Render will detect `render.yaml` automatically. If it asks for settings manually:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. Click **Create Web Service**.
6. Wait for the first deploy to finish (~2–3 min).
7. Copy your Render URL — it looks like: `https://raid-fun-backend.onrender.com`

> **⚠️ Free tier note:** Render free services spin down after 15 minutes of inactivity and take ~30 seconds to wake up on the first request. This is fine for testing.

---

## Step 3 — Set environment variables on Render

In your Render dashboard → your service → **Environment**:

| Key | Value |
|-----|-------|
| `DISCORD_CLIENT_ID` | `1503879259180240987` |
| `DISCORD_CLIENT_SECRET` | `pn_RuO6hLZeh2BYm3LQT99llq7dQBp18` |
| `DISCORD_REDIRECT_URI` | `https://YOUR_RENDER_URL.onrender.com/auth/discord/callback` |
| `X_CLIENT_ID` | `X1o2RDhuQXo1UDZIM2hfMFBjNEc6MTpjaQ` |
| `X_CLIENT_SECRET` | `8Iu5XOe9J7M7gThA1K2c5MMXl1p2GOvOUgV4GrAKnE308z_iUi` |
| `X_REDIRECT_URI` | `https://YOUR_RENDER_URL.onrender.com/auth/x/callback` |
| `JWT_SECRET` | any long random string (e.g. `raid-fun-prod-secret-2026-xyz123`) |
| `MOCK_MODE` | `true` (set to `false` for real tweet verification) |
| `FRONTEND_URL` | `https://YOUR_NETLIFY_URL.netlify.app` (fill in after Step 5) |
| `DATABASE_URL` | `sqlite:///./raidfun.db` |

After adding vars, click **Save Changes** — Render will redeploy automatically.

---

## Step 4 — Update frontend config with your Render URL

Open `frontend/config.js` and replace the placeholder:

```js
// Before:
: 'https://REPLACE_WITH_YOUR_RENDER_URL.onrender.com';

// After (your actual Render URL):
: 'https://raid-fun-backend.onrender.com';
```

Save the file.

---

## Step 5 — Deploy the frontend on Netlify (free)

### Option A — Drag and drop (easiest, no GitHub needed)

1. Go to https://app.netlify.com/drop
2. Drag your `frontend/` folder onto the page.
3. Done! Netlify gives you a URL like `https://amazing-name-123.netlify.app`.

### Option B — Connect GitHub (auto-deploys on push)

1. Go to https://app.netlify.com → **Add new site → Import an existing project**.
2. Connect your GitHub repo.
3. Settings:
   - **Base directory:** `frontend`
   - **Publish directory:** `frontend`
   - **Build command:** (leave empty)
4. Click **Deploy site**.

Copy your Netlify URL — you'll need it for the next step.

---

## Step 6 — Update FRONTEND_URL on Render

Go back to Render → Environment and set:

```
FRONTEND_URL = https://YOUR_NETLIFY_URL.netlify.app
```

Render will redeploy automatically.

---

## Step 7 — Update OAuth callback URLs

You need to add the production callback URLs to both developer portals. **The old localhost URLs still work locally**, so don't remove them — just add the new ones.

### Discord (https://discord.com/developers/applications)

1. Open your application → **OAuth2 → Redirects**
2. Add: `https://YOUR_RENDER_URL.onrender.com/auth/discord/callback`
3. Save.

### X / Twitter (https://developer.twitter.com/en/portal/dashboard)

1. Open your app → **Settings → User authentication settings → Edit**
2. Under **Callback URI / Redirect URL**, add: `https://YOUR_RENDER_URL.onrender.com/auth/x/callback`
3. Save.

---

## Step 8 — Test it

1. Open your Netlify URL in the browser.
2. Try logging in with X — you should be redirected to Twitter and back.
3. Check the Render logs if anything fails: Render dashboard → your service → **Logs**.

---

## Troubleshooting

**CORS error in browser console**
→ Check that `FRONTEND_URL` on Render exactly matches your Netlify URL (no trailing slash).

**OAuth redirect_uri mismatch**
→ The URL in the developer portal must exactly match what's in `DISCORD_REDIRECT_URI` / `X_REDIRECT_URI` env vars on Render.

**"Service unavailable" / 502 on first load**
→ The Render free tier is waking up — wait 30 seconds and refresh.

**Service worker showing old version**
→ Open browser DevTools → Application → Service Workers → click "Update" or "Unregister", then reload.

**SQLite data loss after Render redeploy**
→ Expected on the free tier (ephemeral disk). For persistent data, upgrade to a paid Render plan and switch to PostgreSQL. For now, MOCK_MODE=true means everything auto-verifies so data loss doesn't break testing.

---

## Local dev still works

Nothing changed for local development. `double-click RUN_BACKEND.bat` and `START_FRONTEND.bat` as before — `config.js` auto-detects localhost and uses `http://localhost:8000`.
