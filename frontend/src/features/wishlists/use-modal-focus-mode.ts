"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type React from "react";

/**
 * detect mobile keyboard target
 */
function isMobileKeyboardTarget() {
  if (typeof window === "undefined") return false;

  return window.matchMedia("(pointer: coarse)").matches && window.innerWidth <= 820;
}

/**
 * modal keyboard focus mode
 */
export function useModalFocusMode() {
  const [focusedSection, setFocusedSection] = useState<string | null>(null);
  const [mobileKeyboardTarget, setMobileKeyboardTarget] = useState(false);
  const blurTimer = useRef<number | null>(null);

  useEffect(() => {
    const updateKeyboardTarget = () => setMobileKeyboardTarget(isMobileKeyboardTarget());

    updateKeyboardTarget();
    window.addEventListener("resize", updateKeyboardTarget);
    window.visualViewport?.addEventListener("resize", updateKeyboardTarget);

    return () => {
      window.removeEventListener("resize", updateKeyboardTarget);
      window.visualViewport?.removeEventListener("resize", updateKeyboardTarget);
    };
  }, []);

  const handleFocus = useCallback((section: string) => (event: React.FocusEvent<HTMLElement>) => {
    const target = event.currentTarget;

    if (!mobileKeyboardTarget) return;

    if (blurTimer.current) {
      window.clearTimeout(blurTimer.current);
      blurTimer.current = null;
    }

    // delay collapsing other fields to let native focus start first
    setTimeout(() => {
      setFocusedSection(section);
      
      // delay scroll to center after viewport begins resizing
      setTimeout(() => {
        if (target.isConnected) {
          target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
        }
      }, 100);
    }, 60);
  }, [mobileKeyboardTarget]);

  const handleBlur = useCallback(() => {
    blurTimer.current = window.setTimeout(() => {
      const active = document.activeElement;
      if (!mobileKeyboardTarget || !active || !active.closest(".modal-sheet")) {
        setFocusedSection(null);
      }
    }, 120);
  }, [mobileKeyboardTarget]);

  const clearFocus = useCallback(() => {
    if (blurTimer.current) {
      window.clearTimeout(blurTimer.current);
      blurTimer.current = null;
    }

    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

    // delay focus clear to let mobile keyboard start hiding smoothly
    setTimeout(() => {
      setFocusedSection(null);
    }, 200);
  }, []);

  return {
    focusedSection,
    fieldFocusProps: (section: string) => ({
      "data-active-section": focusedSection === section ? "true" : undefined,
      onFocus: handleFocus(section),
    }),
    onFieldBlur: handleBlur,
    clearFocus,
    isFocusMode: mobileKeyboardTarget && Boolean(focusedSection),
    sectionClass: (section: string) =>
      mobileKeyboardTarget && focusedSection && focusedSection !== section ? "modal-focus-collapsed" : "modal-focus-section",
  };
}
