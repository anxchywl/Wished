"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "@/lib/i18n/useTranslation";

/**
 * bottom navigation bar
 */
export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useTranslation();
  const navRef = useRef<HTMLElement>(null);
  const maxViewportHeightRef = useRef(0);

  const tabs = useMemo(() => [
    {
      href: "/wishlists",
      label: t("wishlists"),
      icon: (
        <svg className="nav-icon-heart" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
        </svg>
      ),
    },
    {
      href: "/users",
      label: t("discover"),
      icon: (
        <svg className="nav-icon-compass" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" fill="currentColor" />
        </svg>
      ),
    },
  ], [t]);

  useEffect(() => {
    router.prefetch("/wishlists");
    router.prefetch("/users");
  }, [router]);

  useEffect(() => {
    const nav = navRef.current;
    const viewport = window.visualViewport;
    if (!nav || !viewport) return undefined;

    const updateKeyboardOffset = () => {
      maxViewportHeightRef.current = Math.max(maxViewportHeightRef.current, viewport.height);
      const viewportKeyboardOffset = Math.max(
        0,
        maxViewportHeightRef.current - viewport.height - viewport.offsetTop
      );
      const windowKeyboardOffset = Math.max(
        0,
        window.innerHeight - viewport.height - viewport.offsetTop
      );
      const keyboardOffset = Math.max(viewportKeyboardOffset, windowKeyboardOffset);

      nav.style.setProperty("--keyboard-offset", `${keyboardOffset}px`);
    };

    const resetViewportHeight = () => {
      maxViewportHeightRef.current = viewport.height;
      updateKeyboardOffset();
    };
    const scheduleKeyboardUpdate = () => {
      updateKeyboardOffset();
      window.setTimeout(updateKeyboardOffset, 80);
      window.setTimeout(updateKeyboardOffset, 220);
    };

    updateKeyboardOffset();
    viewport.addEventListener("resize", updateKeyboardOffset);
    viewport.addEventListener("scroll", updateKeyboardOffset);
    window.addEventListener("focusin", scheduleKeyboardUpdate);
    window.addEventListener("focusout", scheduleKeyboardUpdate);
    window.addEventListener("orientationchange", resetViewportHeight);

    return () => {
      viewport.removeEventListener("resize", updateKeyboardOffset);
      viewport.removeEventListener("scroll", updateKeyboardOffset);
      window.removeEventListener("focusin", scheduleKeyboardUpdate);
      window.removeEventListener("focusout", scheduleKeyboardUpdate);
      window.removeEventListener("orientationchange", resetViewportHeight);
    };
  }, []);

  return (
    <nav ref={navRef} className="bottom-nav" aria-label="main navigation">
      {tabs.map((tab) => {
        const isActive = pathname === tab.href || pathname.startsWith(tab.href + "/");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`bottom-nav-tab${isActive ? " active" : ""}`}
          >
            <span className="bottom-nav-icon">{tab.icon}</span>
          </Link>
        );
      })}
    </nav>
  );
}
