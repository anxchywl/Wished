"use client";

import { useState } from "react";
import { useUIStore } from "@/stores/ui-store";

/**
 * ui controls component
 */
export function UIControls() {
  const { lang, toggleTheme, toggleLang } = useUIStore();
  const [themeSwitching, setThemeSwitching] = useState(false);
  const [langSwitching, setLangSwitching] = useState(false);

  const handleThemeClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.blur();
    setThemeSwitching(true);
    toggleTheme(e);
    setTimeout(() => {
      setThemeSwitching(false);
    }, 460);
  };

  const handleLangClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.blur();
    setLangSwitching(true);
    toggleLang(e);
    setTimeout(() => {
      setLangSwitching(false);
    }, 460);
  };

  return (
    <div className="top-controls">
      <button
        className={themeSwitching ? "theme-toggle theme-switching" : "theme-toggle"}
        type="button"
        onClick={handleThemeClick}
        aria-label="Theme"
      >
        <svg className="sun" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
        <svg className="moon" viewBox="0 0 24 24">
          <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3 6.5 6.5 0 0 0 21 12.8z" />
        </svg>
      </button>
      <button className={langSwitching ? "lang-toggle lang-switching" : "lang-toggle"} type="button" onClick={handleLangClick}>
        {lang.toUpperCase()}
      </button>
    </div>
  );
}
