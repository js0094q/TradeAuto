import { DashboardClient } from "@/components/DashboardClient";
import { getDashboardConfig } from "@/lib/config";

export const dynamic = "force-dynamic";

export default function DashboardPage() {
  const config = getDashboardConfig();

  return (
    <DashboardClient
      backendLabel={config.backendLabel}
      controlActionsEnabled={config.controlActionsEnabled}
    />
  );
}
