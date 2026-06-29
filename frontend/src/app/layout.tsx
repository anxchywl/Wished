import type { Metadata, Viewport } from "next";
import Script from "next/script";
import type { ReactNode } from "react";

import { ClientAppProviders } from "@/app/client-providers";
import "@/app/globals.css";

const captureTelegramInitDataScript = `
(function () {
  try {
    var TELEGRAM_INIT_DATA_TEST_TRIGGER = "test";
    var url = new URL(window.location.href);
    var searchParams = new URLSearchParams(url.search);
    var hashParams = new URLSearchParams((url.hash || "").replace(/^#/, ""));
    var fromUrl = searchParams.get("tgWebAppData") || hashParams.get("tgWebAppData");
    var startParam =
      searchParams.get("tgWebAppStartParam") ||
      hashParams.get("tgWebAppStartParam");
    var webApp = window.Telegram && window.Telegram.WebApp;
    var fromWebApp = webApp && webApp.initData;
    var startParamFromWebApp =
      webApp &&
      webApp.initDataUnsafe &&
      webApp.initDataUnsafe.start_param;

    if (fromUrl === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
      if (searchParams.get("tgWebAppData") === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
        searchParams.delete("tgWebAppData");
      }
      if (hashParams.get("tgWebAppData") === TELEGRAM_INIT_DATA_TEST_TRIGGER) {
        hashParams.delete("tgWebAppData");
        url.hash = hashParams.toString();
      }
      url.search = searchParams.toString();
      window.history.replaceState(null, "", url.toString());
    }

    var raw = fromUrl === TELEGRAM_INIT_DATA_TEST_TRIGGER ? fromWebApp : fromUrl || fromWebApp;
    if (raw) {
      sessionStorage.setItem("wished/tgInitDataRaw", raw);
    }
    var effectiveStartParam = startParam || startParamFromWebApp;
    if (effectiveStartParam) {
      sessionStorage.setItem("wished/tgStartParam", effectiveStartParam);
    }
    if (webApp) {
      if (typeof webApp.expand === "function") webApp.expand();
    }

    // eagerly navigate to the wishlist popup URL before React hydrates so that
    // useSearchParams() already has the correct values on first render
    if (effectiveStartParam && effectiveStartParam.indexOf("wl_") === 0) {
      try {
        var b64 = effectiveStartParam.slice(3).replace(/-/g, "+").replace(/_/g, "/");
        var padLen = (4 - (b64.length % 4)) % 4;
        for (var i = 0; i < padLen; i++) b64 += "=";
        var json = decodeURIComponent(escape(atob(b64)));
        var parsed = JSON.parse(json);
        if (parsed && typeof parsed.wishlistId === "string" && typeof parsed.userId === "string" && parsed.userId) {
          var targetSearch = "?profile_id=" + encodeURIComponent(parsed.userId) +
            "&wishlist=" + encodeURIComponent(parsed.wishlistId);
          if (parsed.shareToken && typeof parsed.shareToken === "string") {
            targetSearch += "&share_token=" + encodeURIComponent(parsed.shareToken);
          }
          var currentSearch = new URLSearchParams(window.location.search);
          var alreadyThere =
            currentSearch.get("profile_id") === parsed.userId &&
            currentSearch.get("wishlist") === parsed.wishlistId;
          if (!alreadyThere) {
            window.history.replaceState(null, "", "/users" + targetSearch);
          }
        }
      } catch (e2) {}
    }
    if (effectiveStartParam && effectiveStartParam.indexOf("p_") === 0) {
      try {
        var publicUsername = effectiveStartParam.slice(2).toLowerCase();
        if (/^[a-z0-9_]{3,32}$/.test(publicUsername)) {
          var currentPublicSearch = new URLSearchParams(window.location.search);
          if (currentPublicSearch.get("profile_public") !== publicUsername) {
            window.history.replaceState(null, "", "/users?profile_public=" + encodeURIComponent(publicUsername));
          }
        }
      } catch (e3) {}
    }
  } catch (e) {}
})();
`;

const recoverStaleChunkScript = `
(function () {
  var key = "wished/chunk-reload";
  var cooldown = 30000;
  function recover(reason) {
    var message = reason && reason.message ? reason.message : String(reason || "");
    if (!/ChunkLoadError|Loading chunk [\\w-]+ failed|Failed to fetch dynamically imported module/i.test(message)) return;
    var lastReloadAt = Number(sessionStorage.getItem(key) || "0");
    if (Date.now() - lastReloadAt < cooldown) return;
    sessionStorage.setItem(key, String(Date.now()));
    var reloadUrl = new URL(window.location.href);
    reloadUrl.searchParams.set("_wished_reload", String(Date.now()));
    window.location.replace(reloadUrl.toString());
  }
  window.addEventListener("error", function (event) { recover(event.error || event.message); });
  window.addEventListener("unhandledrejection", function (event) { recover(event.reason); });
})();
`;

export const metadata: Metadata = {
  title: "Wished",
  description: "Telegram Mini App social wishlist platform.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "overlays-content",
};

type RootLayoutProps = {
  children: ReactNode;
};

/**
 * render app shell
 */
export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <Script id="capture-tg-init" strategy="beforeInteractive">
          {captureTelegramInitDataScript}
        </Script>
        <Script id="recover-stale-chunks" strategy="beforeInteractive">
          {recoverStaleChunkScript}
        </Script>
        <ClientAppProviders>{children}</ClientAppProviders>
      </body>
    </html>
  );
}
