// telegram init data capture
const EARLY_INIT_DATA_KEY = "wished/tgInitDataRaw";
const TELEGRAM_INIT_DATA_TEST_TRIGGER = "test";

/**
 * read early captured init data
 */
export function getEarlyCapturedInitDataRaw(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const stored = window.sessionStorage.getItem(EARLY_INIT_DATA_KEY);
    if (!stored) return null;
    if (!new URLSearchParams(stored).has("hash")) {
      window.sessionStorage.removeItem(EARLY_INIT_DATA_KEY);
      return null;
    }
    return stored;
  } catch {
    return null;
  }
}

/**
 * store init data for sdk fallback
 */
export function storeEarlyInitDataRaw(value: string) {
  if (typeof window === "undefined" || !value || value === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
    return;
  }
  if (!new URLSearchParams(value).has("hash")) {
    return;
  }

  try {
    window.sessionStorage.setItem(EARLY_INIT_DATA_KEY, value);
  } catch {}
}

function removeTelegramInitDataTriggerFromLocation(): void {
  try {
    const url = new URL(window.location.href);
    const searchParams = url.searchParams;
    const hashParams = new URLSearchParams(url.hash.replace(/^#/, ""));

    if (searchParams.get("tgWebAppData") === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
      searchParams.delete("tgWebAppData");
    }
    if (hashParams.get("tgWebAppData") === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
      hashParams.delete("tgWebAppData");
      url.hash = hashParams.toString();
    }

    if (url.search !== window.location.search || url.hash !== window.location.hash.replace(/^#/, "")) {
      window.history.replaceState(null, "", url.toString());
    }
  } catch {
    // ignore history replacement failures
  }
}

/**
 * capture init data from url or webapp
 */
export function captureTelegramInitDataFromLocation(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const searchParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const fromUrl = searchParams.get("tgWebAppData") || hashParams.get("tgWebAppData");
  const webApp = (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp;
  const fromWebApp = webApp?.initData || null;

  if (fromUrl === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
    removeTelegramInitDataTriggerFromLocation();
    return fromWebApp;
  }

  const raw = fromUrl || fromWebApp;
  if (raw) {
    storeEarlyInitDataRaw(raw);
  }

  return raw;
}
