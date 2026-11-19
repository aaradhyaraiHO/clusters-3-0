// Edge Middleware — gates the whole Ledger behind a @headout.com session.
// Runs before every request except the auth endpoints themselves. No valid
// session cookie → redirect to Google sign-in. Verifies the signed session
// JWT (set by /api/auth/callback) and re-checks the email domain on every hit.
import { next } from "@vercel/edge";
import { jwtVerify } from "jose";

// Gate everything EXCEPT the auth routes (so login/callback stay reachable).
export const config = {
  matcher: ["/((?!api/auth).*)"],
};

const enc = new TextEncoder();

export default async function middleware(request) {
  const domain = (process.env.ALLOWED_DOMAIN || "headout.com").toLowerCase();
  const cookie = request.headers.get("cookie") || "";
  const m = cookie.match(/(?:^|;\s*)mmr_session=([^;]+)/);
  if (m && process.env.AUTH_SECRET) {
    try {
      const { payload } = await jwtVerify(m[1], enc.encode(process.env.AUTH_SECRET));
      const email = String(payload.email || "").toLowerCase();
      if (email.endsWith("@" + domain)) return next(); // authenticated → continue
    } catch (_) { /* invalid / expired → fall through to login */ }
  }
  const url = new URL(request.url);
  const login = new URL("/api/auth/login", url.origin);
  login.searchParams.set("next", url.pathname + url.search);
  return Response.redirect(login.toString(), 302);
}
