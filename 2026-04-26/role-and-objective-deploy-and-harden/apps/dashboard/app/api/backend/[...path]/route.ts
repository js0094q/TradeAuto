import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/backend";
import {
  getBackendBasicAuthHeader,
  getDashboardConfig,
  requireBackendAdminToken,
} from "@/lib/config";
import { hasValidSession } from "@/lib/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const GET_ALLOWLIST = new Set(["health", "ready", "metrics", "paper-strategy", "live-strategy"]);
const POST_ALLOWLIST = new Set(["admin/kill", "admin/resume", "admin/paper-cycle"]);
const ADMIN_REQUIRED = new Set(["ready", "metrics", "paper-strategy", "live-strategy", "admin/kill", "admin/resume", "admin/paper-cycle"]);

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(_request: Request, context: RouteContext) {
  return proxyRequest(context, "GET");
}

export async function POST(request: Request, context: RouteContext) {
  return proxyRequest(context, "POST", request);
}

async function proxyRequest(context: RouteContext, method: "GET" | "POST", request?: Request) {
  if (!(await hasValidSession())) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  const params = await context.params;
  const path = params.path.join("/");
  const allowed = method === "GET" ? GET_ALLOWLIST : POST_ALLOWLIST;
  if (!allowed.has(path)) {
    return NextResponse.json({ ok: false, error: "Backend path is not allowlisted" }, { status: 404 });
  }

  if (method === "POST") {
    const gate = await validateControlGate(path, request);
    if (gate) {
      return gate;
    }
  }

  const { backendBaseUrl } = getDashboardConfig();
  const headers = new Headers({ Accept: "application/json" });
  if (ADMIN_REQUIRED.has(path)) {
    try {
      headers.set("X-Admin-Token", requireBackendAdminToken());
      const basicAuth = getBackendBasicAuthHeader();
      if (basicAuth) {
        headers.set("Authorization", basicAuth);
      }
    } catch (error) {
      return NextResponse.json(
        { ok: false, error: error instanceof Error ? error.message : "Admin token missing" },
        { status: 503 },
      );
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const upstream = await fetchBackend(`${backendBaseUrl}/${path}`, {
      method,
      headers,
      cache: "no-store",
      signal: controller.signal,
    });
    const contentType = upstream.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await upstream.json() : await upstream.text();
    const detail = isRecord(data) && isRecord(data.detail) ? data.detail : undefined;
    return NextResponse.json(
      {
        ok: upstream.ok,
        status: upstream.status,
        ...(upstream.ok
          ? { data }
          : {
              ...(detail ? { data: detail } : {}),
              error: typeof data === "string" ? data : JSON.stringify(data),
            }),
      },
      {
        status: upstream.ok ? 200 : upstream.status,
        headers: { "Cache-Control": "no-store" },
      },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend request failed";
    return NextResponse.json({ ok: false, status: 502, error: message }, { status: 502 });
  } finally {
    clearTimeout(timeout);
  }
}

async function validateControlGate(path: string, request?: Request) {
  if (process.env.DASHBOARD_ALLOW_CONTROL_ACTIONS !== "true") {
    return NextResponse.json({ ok: false, error: "Control actions are disabled" }, { status: 403 });
  }

  const body = (await request?.json().catch(() => null)) as { confirmation?: string } | null;
  const expected =
    path === "admin/resume"
      ? "YES_I_UNDERSTAND"
      : path === "admin/paper-cycle"
        ? "RUN_PAPER_CYCLE"
        : "ENABLE_KILL_SWITCH";
  if (body?.confirmation !== expected) {
    return NextResponse.json(
      { ok: false, error: `Confirmation phrase required: ${expected}` },
      { status: 400 },
    );
  }

  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
