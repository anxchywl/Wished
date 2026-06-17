import { useTranslation } from "@/lib/i18n/useTranslation";
import { useTelegram } from "@/lib/telegram/telegram-provider";
import { useMutationState } from "@tanstack/react-query";

type AuthRequiredPanelProps = {
  forcePending?: boolean;
  fullScreen?: boolean;
};

/**
 * render auth required panel
 */
export function AuthRequiredPanel({ forcePending = false, fullScreen = false }: AuthRequiredPanelProps) {
  const { t } = useTranslation();
  const { isReady } = useTelegram();

  const isLoginPending = useMutationState({
    filters: { mutationKey: ["telegramLogin"], status: "pending" },
  }).length > 0;

  const isLoginError = useMutationState({
    filters: { mutationKey: ["telegramLogin"], status: "error" },
  }).length > 0;

  // show spinner while sdk is initializing or login is in-flight
  if (forcePending || (!isLoginError && (!isReady || isLoginPending))) {
    return (
      <div className={fullScreen ? "auth-loading-screen" : "auth-loading-panel"} aria-busy="true" aria-label="loading">
        <span className="auth-loading-spinner" />
      </div>
    );
  }

  return (
    <div className="panel flex flex-col items-center justify-center text-center gap-2 bg-muted/20">
      <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary inline-flex items-center justify-center">
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      </div>
      <p className="text-sm font-semibold text-foreground">{t("pleaseAuthenticateFirst")}</p>
      <p className="text-xs text-muted">{t("openFromTelegram")}</p>
    </div>
  );
}
