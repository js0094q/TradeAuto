import { cookies } from "next/headers";

export const SESSION_COOKIE = "trading_dashboard_session";

export function getSessionSecret(): string | null {
  const secret = process.env.DASHBOARD_SESSION_SECRET?.trim();
  if (!secret || secret === "replace_with_random_cookie_secret") {
    return null;
  }
  return secret;
}

export function getAccessToken(): string | null {
  const token = process.env.DASHBOARD_ACCESS_TOKEN?.trim();
  if (!token || token === "replace_with_operator_login_token") {
    return null;
  }
  return token;
}

export async function hasValidSession(): Promise<boolean> {
  const secret = getSessionSecret();
  if (!secret) {
    return false;
  }

  const cookieStore = await cookies();
  return timingSafeStringEqual(cookieStore.get(SESSION_COOKIE)?.value || "", secret);
}

export function timingSafeStringEqual(actual: string, expected: string): boolean {
  if (actual.length !== expected.length) {
    return false;
  }

  let mismatch = 0;
  for (let index = 0; index < expected.length; index += 1) {
    mismatch |= actual.charCodeAt(index) ^ expected.charCodeAt(index);
  }
  return mismatch === 0;
}
