// Google redirects back here with ?code&state. Verify state, exchange the code,
// read the verified email from userinfo, enforce @headout.com, then set a signed
// session JWT cookie and bounce back to where the user was headed.
import { SignJWT } from "jose";

function parseCookies(header) {
  const out = {};
  (header || "").split(/;\s*/).forEach((p) => {
    const i = p.indexOf("=");
    if (i > 0) out[p.slice(0, i)] = p.slice(i + 1);
  });
  return out;
}

function forbiddenHtml(email, domain) {
  return `<!doctype html><meta charset=utf-8><title>Access denied</title>
  <div style="font:500 16px system-ui;max-width:520px;margin:12vh auto;text-align:center;color:#1C1726">
    <div style="width:34px;height:34px;border-radius:50% 50% 50% 4px;background:#8000FF;margin:0 auto 18px"></div>
    <h1 style="font:800 22px system-ui">Headout access only</h1>
    <p style="color:#6E6680">Signed in as <b>${String(email || "unknown")
      .replace(/[&<>]/g, "")}</b>, which isn't a <b>@${domain}</b> account.</p>
    <p><a href="/api/auth/logout" style="color:#8000FF;font-weight:700">Try another account →</a></p>
  </div>`;
}

export default async function handler(req, res) {
  const proto = String(req.headers["x-forwarded-proto"] || "https").split(",")[0];
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const base = `${proto}://${host}`;
  const url = new URL(req.url, base);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");

  const cookies = parseCookies(req.headers.cookie);
  let saved = {};
  try { saved = JSON.parse(Buffer.from(cookies.mmr_oauth || "", "base64url").toString()); } catch (_) {}

  if (!code || !state || state !== saved.s) { res.statusCode = 400; res.end("Bad OAuth state."); return; }

  const redirectUri = `${base}/api/auth/callback`;
  const domain = (process.env.ALLOWED_DOMAIN || "headout.com").toLowerCase();

  try {
    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: process.env.GOOGLE_CLIENT_ID,
        client_secret: process.env.GOOGLE_CLIENT_SECRET,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
    });
    if (!tokenRes.ok) { res.statusCode = 502; res.end("Token exchange failed."); return; }
    const tokens = await tokenRes.json();

    const uiRes = await fetch("https://openidconnect.googleapis.com/v1/userinfo", {
      headers: { authorization: `Bearer ${tokens.access_token}` },
    });
    if (!uiRes.ok) { res.statusCode = 502; res.end("Userinfo fetch failed."); return; }
    const info = await uiRes.json();

    if (!info.email_verified || !String(info.email || "").toLowerCase().endsWith("@" + domain)) {
      res.statusCode = 403;
      res.setHeader("content-type", "text/html");
      res.end(forbiddenHtml(info.email, domain));
      return;
    }

    const secret = new TextEncoder().encode(process.env.AUTH_SECRET);
    const jwt = await new SignJWT({ email: info.email, name: info.name || info.email })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("12h")
      .sign(secret);

    const nextPath = typeof saved.n === "string" && saved.n.startsWith("/") ? saved.n : "/";
    res.statusCode = 302;
    res.setHeader("Set-Cookie", [
      `mmr_session=${jwt}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=43200`,
      `mmr_oauth=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
    ]);
    res.setHeader("Location", nextPath);
    res.end();
  } catch (e) {
    res.statusCode = 500;
    res.end("Auth error.");
  }
}
