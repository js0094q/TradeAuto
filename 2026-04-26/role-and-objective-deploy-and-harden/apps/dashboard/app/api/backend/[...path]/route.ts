import { request as httpsRequest } from "node:https";

import { NextResponse } from "next/server";

import {
  getBackendBasicAuthHeader,
  getBackendTransportOverrides,
  getDashboardConfig,
  requireBackendAdminToken,
} from "@/lib/config";
import { hasValidSession } from "@/lib/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const GET_ALLOWLIST = new Set(["health", "ready", "metrics"]);
const POST_ALLOWLIST = new Set(["admin/kill", "admin/resume"]);
const ADMIN_REQUIRED = new Set(["ready", "metrics", "admin/kill", "admin/resume"]);

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

type BackendResponse = {
  ok: boolean;
  status: number;
  headers: {
    get(name: string): string | null;
  };
  json(): Promise<unknown>;
  text(): Promise<string>;
};

async function fetchBackend(
  url: string,
  init: {
    method: "GET" | "POST";
    headers: Headers;
    cache: "no-store";
    signal: AbortSignal;
  },
): Promise<BackendResponse> {
  const { hostHeader, tlsServername } = getBackendTransportOverrides();
  if (!hostHeader && !tlsServername) {
    return fetch(url, init);
  }

  const parsed = new URL(url);
  if (parsed.protocol !== "https:") {
    throw new Error("Backend transport overrides require HTTPS");
  }

  const headers = Object.fromEntries(init.headers.entries());
  if (hostHeader) {
    headers.Host = hostHeader;
  }

  return new Promise((resolve, reject) => {
    const request = httpsRequest(
      {
        hostname: parsed.hostname,
        port: parsed.port || 443,
        path: `${parsed.pathname}${parsed.search}`,
        method: init.method,
        servername: tlsServername || hostHeader || parsed.hostname,
        headers,
        timeout: 8000,
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          resolve({
            ok: Boolean(response.statusCode && response.statusCode >= 200 && response.statusCode < 300),
            status: response.statusCode || 502,
            headers: {
              get(name: string) {
                const value = response.headers[name.toLowerCase()];
                return Array.isArray(value) ? value.join(", ") : value || null;
              },
            },
            async json() {
              return JSON.parse(body);
            },
            async text() {
              return body;
            },
          });
        });
      },
    );

    init.signal.addEventListener("abort", () => {
      request.destroy(new Error("Backend request timed out"));
    });
    request.on("timeout", () => {
      request.destroy(new Error("Backend request timed out"));
    });
    request.on("error", reject);
    request.end();
  });
}

async function validateControlGate(path: string, request?: Request) {
  if (process.env.DASHBOARD_ALLOW_CONTROL_ACTIONS !== "true") {
    return NextResponse.json({ ok: false, error: "Control actions are disabled" }, { status: 403 });
  }

  const body = (await request?.json().catch(() => null)) as { confirmation?: string } | null;
  const expected = path === "admin/resume" ? "YES_I_UNDERSTAND" : "ENABLE_KILL_SWITCH";
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
