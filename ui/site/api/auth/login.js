// Start Google sign-in. Stores a short-lived state+next cookie (CSRF + return
// path), then redirects to Google's consent screen. hd=<domain> asks Google to
// restrict to the Headout workspace; the callback re-checks server-side.
import crypto from "node:crypto";

export default async function handler(req, res) {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  if (!clientId) { res.statusCode = 500; res.end("Auth not configured (GOOGLE_CLIENT_ID missing)."); return; }

  const proto = String(req.headers["x-forwarded-proto"] || "https").split(",")[0];
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const base = `${proto}://${host}`;
  const redirectUri = `${base}/api/auth/callback`;

  const url = new URL(req.url, base);
  const nextPath = url.searchParams.get("next") || "/";
  const state = crypto.randomBytes(16).toString("hex");
  const stateCookie = Buffer.from(JSON.stringify({ s: state, n: nextPath })).toString("base64url");

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email profile",
    state,
    hd: process.env.ALLOWED_DOMAIN || "headout.com",
    prompt: "select_account",
  });

  res.statusCode = 302;
  res.setHeader("Set-Cookie", `mmr_oauth=${stateCookie}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`);
  res.setHeader("Location", `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`);
  res.end();
}
