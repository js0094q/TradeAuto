export type DashboardConfig = {
  backendBaseUrl: string;
  backendLabel: string;
  controlActionsEnabled: boolean;
};

export function getDashboardConfig(): DashboardConfig {
  const backendBaseUrl = normalizeBaseUrl(process.env.TRADING_API_BASE_URL || "https://jlsprojects.com");

  return {
    backendBaseUrl,
    backendLabel: new URL(backendBaseUrl).host,
    controlActionsEnabled: process.env.DASHBOARD_ALLOW_CONTROL_ACTIONS === "true",
  };
}

export function requireBackendAdminToken(): string {
  const token = process.env.TRADING_API_ADMIN_TOKEN?.trim();
  if (!token || token === "replace_with_vps_admin_token") {
    throw new Error("TRADING_API_ADMIN_TOKEN is not configured");
  }
  return token;
}

export function getBackendBasicAuthHeader(): string | null {
  const credentials = process.env.TRADING_API_BASIC_AUTH?.trim();
  if (!credentials || credentials === "operator:replace_with_nginx_operator_password") {
    return null;
  }
  return `Basic ${Buffer.from(credentials, "utf8").toString("base64")}`;
}

function normalizeBaseUrl(value: string): string {
  const parsed = new URL(value);
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") {
    throw new Error("TRADING_API_BASE_URL must use HTTPS in production");
  }
  return parsed.origin;
}
