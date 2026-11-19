# Deploying site/ (user-run)

One-time:
1. `cd <this folder> && vercel link` → team `headout`, create project `clusters-3-0`.
2. Google Cloud console → APIs & Services → Credentials → the OAuth client central-tracking uses → add the redirect URI
   `https://clusters-3-0.vercel.app/api/auth/callback`.
3. Vercel → clusters-3-0 → Settings → Environment Variables (all environments): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   (same as central-tracking), `AUTH_SECRET` (`openssl rand -hex 32`), optional `ALLOWED_DOMAIN` (default headout.com).

Each deploy: `python3 stage_site.py && vercel deploy --prod --cwd site`. Open it from https://clusters-3-0.vercel.app
(sign-in breaks on per-deployment URLs).
