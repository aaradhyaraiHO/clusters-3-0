"""Stage the built cluster pages as a Vercel site behind the @headout.com Google sign-in, in site/.

  python3 stage_site.py

Copies every CE's built page from ces.json, writes an index linking them, and copies the auth gate (middleware.js,
api/auth/, vercel.json) unchanged from ~/analytics/central-tracking, as central-tracking copied it from the market
notebook. Deploying stays user-run (internal revenue data); the commands are in site/DEPLOY.md.
"""
import html
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
AUTH = Path.home() / "analytics" / "central-tracking"


def main():
    reg = json.loads((HERE / "ces.json").read_text())
    if SITE.exists():
        for p in SITE.iterdir():
            if p.name != ".vercel":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    SITE.mkdir(exist_ok=True)
    shutil.copy(AUTH / "middleware.js", SITE / "middleware.js")
    shutil.copy(AUTH / "vercel.json", SITE / "vercel.json")
    shutil.copytree(AUTH / "api", SITE / "api")
    pkg = json.loads((AUTH / "package.json").read_text())
    pkg.update(name="clusters-3-0", description="Clusters 3.0 prototype pages behind a Google @headout.com auth gate. No database.")
    (SITE / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")
    links = []
    for ce, cfg in reg["ces"].items():
        page = HERE / cfg["page"]
        if not page.exists():
            continue
        shutil.copy(page, SITE / cfg["page"])
        links.append(f'<li><a href="/{cfg["page"][:-5]}">{html.escape(cfg["name"])}</a> <span>CE {ce}</span></li>')
    (SITE / "index.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clusters 3.0</title>
<style>
:root{{--bg:#f8f8f8;--card:#fff;--fg:#222;--fg3:#666;--ink:#6600cc}}
body{{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
main{{max-width:640px;margin:48px auto;padding:0 16px}}h1{{font-size:20px;font-weight:600;margin:0 0 4px}}p{{color:var(--fg3);margin:0 0 20px;font-size:14px}}
ul{{list-style:none;padding:0;margin:0;background:var(--card);border-radius:12px;box-shadow:0 1px 6px 1px rgba(17,17,17,.10)}}
li{{padding:14px 16px;border-bottom:1px solid #f0f0f0;font-size:15px}}li:last-child{{border-bottom:0}}a{{color:var(--ink);text-decoration:none;font-weight:500}}span{{color:var(--fg3);font-size:12px;margin-left:6px}}
</style></head><body><main><h1>Clusters 3.0</h1><p>Prototype · data {html.escape(reg["window"]["label"])} · Headout only</p>
<ul>{"".join(links)}</ul></main></body></html>
""")
    (SITE / "DEPLOY.md").write_text("""# Deploying site/ (user-run)

One-time:
1. `cd <this folder> && vercel link` → team `headout`, create project `clusters-3-0`.
2. Google Cloud console → APIs & Services → Credentials → the OAuth client central-tracking uses → add the redirect URI
   `https://clusters-3-0.vercel.app/api/auth/callback`.
3. Vercel → clusters-3-0 → Settings → Environment Variables (all environments): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   (same as central-tracking), `AUTH_SECRET` (`openssl rand -hex 32`), optional `ALLOWED_DOMAIN` (default headout.com).

Each deploy: `python3 stage_site.py && vercel deploy --prod --cwd site`. Open it from https://clusters-3-0.vercel.app
(sign-in breaks on per-deployment URLs).
""")
    print(f"staged {len(links)} pages in {SITE}")


if __name__ == "__main__":
    main()
