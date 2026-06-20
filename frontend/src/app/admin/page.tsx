"use client";

import { useAdminStatus } from "@/features/admin/hooks";
import { AdminPanelManager } from "@/features/admin/admin-panel-manager";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { useAuthStore } from "@/stores/auth-store";
import { UIControls } from "@/components/ui/controls";
import { useUIStore } from "@/stores/ui-store";

export default function AdminPage() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const coverStyle = useUIStore((state) => state.coverStyle);
  const { data: adminMe, isLoading, error } = useAdminStatus();

  if (!accessToken) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--tg-theme-hint-color)" }}>
        {t("pleaseAuthenticateFirst")}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--tg-theme-hint-color)" }}>
        {t("adminLoading")}
      </div>
    );
  }

  if (error || !adminMe?.is_admin) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--tg-theme-destructive-text-color, red)" }}>
        {t("adminAccessDenied")}
      </div>
    );
  }

  return (
    <div className="admin-page">
      <header
        className="cover admin-cover"
        style={{
          "--fallback-angle": `${coverStyle.angle}deg`,
          "--fallback-a": coverStyle.a,
          "--fallback-b": coverStyle.b,
          "--fallback-c": coverStyle.c,
          "--fallback-d": coverStyle.d,
        } as React.CSSProperties}
      >
        <UIControls />
        <h1>{t("adminPanel")}</h1>
      </header>
      <main className="content admin-content">
        <AdminPanelManager />
      </main>
    </div>
  );
}
