import { NextResponse } from "next/server";

import {
  SESSION_COOKIE,
  getAccessToken,
  getSessionSecret,
  timingSafeStringEqual,
} from "@/lib/session";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const expectedToken = getAccessToken();
  const sessionSecret = getSessionSecret();
  if (!expectedToken || !sessionSecret) {
    return NextResponse.json(
      { ok: false, error: "Dashboard auth env is not configured" },
      { status: 503 },
    );
  }

  const body = (await request.json().catch(() => null)) as { token?: string } | null;
  const token = body?.token?.trim() || "";
  if (!timingSafeStringEqual(token, expectedToken)) {
    return NextResponse.json({ ok: false, error: "Invalid token" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: sessionSecret,
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: "",
    path: "/",
    maxAge: 0,
  });
  return response;
}
