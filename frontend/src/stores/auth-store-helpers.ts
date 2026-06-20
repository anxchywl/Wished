export function getPersistedTgUserId(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("wished-auth");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { state?: { tgUserId?: number | null } };
    return parsed?.state?.tgUserId ?? null;
  } catch {
    return null;
  }
}
