import type { Metadata, Viewport } from "next";
import Script from "next/script";
import type { ReactNode } from "react";

import { AppProviders } from "@/app/providers";
import "@/app/globals.css";

const captureTelegramInitDataScript = `
(function () {
  try {
    var TELEGRAM_INIT_DATA_TEST_TRIGGER = "test";
    var url = new URL(window.location.href);
    var searchParams = new URLSearchParams(url.search);
    var hashParams = new URLSearchParams((url.hash || "").replace(/^#/, ""));
    var fromUrl = searchParams.get("tgWebAppData") || hashParams.get("tgWebAppData");
    var webApp = window.Telegram && window.Telegram.WebApp;
    var fromWebApp = webApp && webApp.initData;

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
    if (webApp) {
      if (typeof webApp.expand === "function") webApp.expand();
    }
  } catch (e) {}
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
        <AppProviders>
          {children}
        </AppProviders>
      </body>
    </html>
  );
}
