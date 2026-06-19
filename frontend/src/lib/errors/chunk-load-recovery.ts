const CHUNK_RELOAD_KEY = "wished/chunk-reload";
const CHUNK_RELOAD_COOLDOWN_MS = 30_000;

/**
 * reload once when a deployment leaves the webview on stale next.js chunks
 */
export function recoverFromChunkLoadError(reason: unknown): boolean {
  if (typeof window === "undefined" || !isChunkLoadError(reason)) {
    return false;
  }

  const lastReloadAt = Number(window.sessionStorage.getItem(CHUNK_RELOAD_KEY) ?? "0");
  if (Date.now() - lastReloadAt < CHUNK_RELOAD_COOLDOWN_MS) {
    return false;
  }

  window.sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
  const reloadUrl = new URL(window.location.href);
  reloadUrl.searchParams.set("_wished_reload", String(Date.now()));
  window.location.replace(reloadUrl.toString());
  return true;
}

function isChunkLoadError(reason: unknown): boolean {
  const message = reason instanceof Error ? reason.message : String(reason ?? "");
  return /ChunkLoadError|Loading chunk [\w-]+ failed|Failed to fetch dynamically imported module/i.test(message);
}
