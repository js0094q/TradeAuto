import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";

import { getBackendTransportOverrides } from "@/lib/config";

export type BackendResponse = {
  ok: boolean;
  status: number;
  headers: {
    get(name: string): string | null;
  };
  json(): Promise<unknown>;
  text(): Promise<string>;
};

export async function fetchBackend(
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
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("Unsupported backend protocol");
  }

  const headers = Object.fromEntries(init.headers.entries());
  if (hostHeader) {
    headers.Host = hostHeader;
  }

  return new Promise((resolve, reject) => {
    const request = (parsed.protocol === "https:" ? httpsRequest : httpRequest)(
      {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
        path: `${parsed.pathname}${parsed.search}`,
        method: init.method,
        ...(parsed.protocol === "https:" ? { servername: tlsServername || hostHeader || parsed.hostname } : {}),
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
