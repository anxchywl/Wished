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
  const [isSwitching, setIsSwitching] = useState(false);
  const switchTimer = useRef<number | null>(null);

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

    const isEnteringFocusMode = focusedSection === null;

    if (!isEnteringFocusMode && focusedSection !== section) {
      setIsSwitching(true);
      if (switchTimer.current) window.clearTimeout(switchTimer.current);
      // turn off switching class after layout has settled instantly
      switchTimer.current = window.setTimeout(() => setIsSwitching(false), 50);
    }

    // collapse other sections immediately so layout settles before keyboard opens
    setFocusedSection(section);

    // only trigger manual scroll when first opening the keyboard
    // when switching between fields, let the browser handle it naturally to avoid jumping/flickering
    if (isEnteringFocusMode) {
      setTimeout(() => {
        if (target.isConnected) {
          target.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        }
      }, 150);
    }
  }, [mobileKeyboardTarget, focusedSection]);

  const handleBlur = useCallback(() => {
    blurTimer.current = window.setTimeout(() => {
      const active = document.activeElement;
      if (!mobileKeyboardTarget || !active || !active.closest(".modal-sheet")) {
        setFocusedSection(null);
        setIsSwitching(false);
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
      setIsSwitching(false);
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
    isSwitching,
    sectionClass: (section: string) =>
      mobileKeyboardTarget && focusedSection && focusedSection !== section ? "modal-focus-collapsed" : "modal-focus-section",
  };
}
