// Clear the session cookie and send back to sign-in.
export default async function handler(req, res) {
  res.statusCode = 302;
  res.setHeader("Set-Cookie", "mmr_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0");
  res.setHeader("Location", "/api/auth/login");
  res.end();
}
