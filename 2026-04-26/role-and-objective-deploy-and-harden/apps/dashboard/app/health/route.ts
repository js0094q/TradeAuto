import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/backend";
import { getDashboardConfig } from "@/lib/config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const { backendBaseUrl } = getDashboardConfig();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const upstream = await fetchBackend(`${backendBaseUrl}/health`, {
      method: "GET",
      headers: new Headers({ Accept: "application/json" }),
      cache: "no-store",
      signal: controller.signal,
    });
    const contentType = upstream.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await upstream.json() : await upstream.text();
    return NextResponse.json(body, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend health check failed";
    return NextResponse.json({ ok: false, error: message }, { status: 502 });
  } finally {
    clearTimeout(timeout);
  }
}
