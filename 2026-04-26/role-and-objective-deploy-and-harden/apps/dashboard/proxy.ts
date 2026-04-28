import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "trading_dashboard_session";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (
    pathname === "/login" ||
    pathname === "/api/session" ||
    pathname.startsWith("/_next/") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  const sessionSecret = process.env.DASHBOARD_SESSION_SECRET;
  const sessionValue = request.cookies.get(SESSION_COOKIE)?.value;
  if (!sessionSecret || sessionValue !== sessionSecret) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
