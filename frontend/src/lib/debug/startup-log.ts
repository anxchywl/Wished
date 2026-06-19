import type { AuthStatus } from "@/stores/auth-store";

type StartupDetails = Record<string, unknown>;

/**
 * log startup state
 */
export function logStartup(event: string, authStatus: AuthStatus, details: StartupDetails = {}) {
  const timestamp = new Date().toISOString();
  console.info("[wished:start]", {
    timestamp,
    event,
    authStatus,
    ...details,
  });
}
