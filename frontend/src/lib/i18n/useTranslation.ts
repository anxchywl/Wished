"use client";

import { useUIStore } from "@/stores/ui-store";
import { dict, type DictKey } from "./dict";

/**
 * translation hook
 */
export function useTranslation() {
  const lang = useUIStore((state) => state.lang);
  const toggleLang = useUIStore((state) => state.toggleLang);

  const t = (key: DictKey): string => {
    const translation = dict[lang]?.[key] || dict["en"]?.[key] || String(key);
    return translation;
  };

  return { t, lang, toggleLang };
}
