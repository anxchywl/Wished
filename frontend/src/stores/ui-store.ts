"use client";

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

type Theme = "light" | "dark";
type Lang = "en" | "kz" | "ru";

type CoverStyle = {
  angle: number;
  a: string;
  b: string;
  c: string;
  d: string;
};

type UIState = {
  theme: Theme;
  lang: Lang;
  coverStyle: CoverStyle;
  setTheme: (theme: Theme) => void;
  setLang: (lang: Lang) => void;
  toggleTheme: (event?: React.MouseEvent) => void;
  toggleLang: (event?: React.MouseEvent) => void;
  regenerateCoverStyle: (theme?: Theme) => void;
};

const fallbackStorage: StateStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
};

const getStorage = (): StateStorage => {
  if (typeof window !== "undefined") {
    try {
      const testKey = "wished-storage-test";
      window.localStorage.setItem(testKey, testKey);
      window.localStorage.removeItem(testKey);
      return window.localStorage;
    } catch {
      return fallbackStorage;
    }
  }
  return fallbackStorage;
};

function generateRandomColors(theme: Theme): CoverStyle {
  const h1 = Math.floor(Math.random() * 360);
  const h2 = (h1 + 90 + Math.floor(Math.random() * 90)) % 360;
  const h3 = (h2 + 90 + Math.floor(Math.random() * 90)) % 360;
  const h4 = (h3 + 90 + Math.floor(Math.random() * 90)) % 360;
  const sat = 95 + Math.floor(Math.random() * 6);
  const light = theme === "dark" ? 60 + Math.floor(Math.random() * 15) : 65 + Math.floor(Math.random() * 15);
  const glowLight = theme === "dark" ? 74 + Math.floor(Math.random() * 14) : 82 + Math.floor(Math.random() * 10);
  const accentLight = theme === "dark" ? 64 + Math.floor(Math.random() * 14) : 70 + Math.floor(Math.random() * 12);
  const angle = Math.floor(Math.random() * 360);

  return {
    angle,
    a: `hsl(${h1} ${sat}% ${light}%)`,
    b: `hsl(${h2} ${sat}% ${light}%)`,
    c: `hsl(${h3} ${sat}% ${glowLight}%)`,
    d: `hsl(${h4} ${sat}% ${accentLight}%)`,
  };
}

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      theme: "light",
      lang: "en",
      coverStyle: {
        angle: 135,
        a: "hsl(210 100% 65%)",
        b: "hsl(280 100% 65%)",
        c: "hsl(150 100% 80%)",
        d: "hsl(340 100% 70%)",
      },
      setTheme: (theme) => {
        set({ theme });
        if (typeof document !== "undefined") {
          document.documentElement.dataset.theme = theme;
          if (theme === "dark") {
            document.documentElement.classList.add("dark");
          } else {
            document.documentElement.classList.remove("dark");
          }
        }
      },
      setLang: (lang) => {
        set({ lang });
        if (typeof document !== "undefined") {
          document.documentElement.lang = lang;
        }
      },
      regenerateCoverStyle: (theme) => {
        const activeTheme = theme || get().theme;
        set({ coverStyle: generateRandomColors(activeTheme) });
      },
      toggleTheme: (event) => {
        const nextTheme = get().theme === "light" ? "dark" : "light";
        const applyTheme = () => {
          get().setTheme(nextTheme);
          get().regenerateCoverStyle(nextTheme);
        };

        if (typeof document === "undefined" || !document.startViewTransition || !event) {
          if (typeof document !== "undefined") {
            document.documentElement.classList.add("theme-transitioning");
            applyTheme();
            setTimeout(() => {
              document.documentElement.classList.remove("theme-transitioning");
              // force repaint
              if (typeof document !== "undefined") {
                const _ = document.body.offsetHeight;
              }
            }, 600);
          } else {
            applyTheme();
          }
          return;
        }

        const x = event.clientX;
        const y = event.clientY;
        const endRadius = Math.hypot(
          Math.max(x, window.innerWidth - x),
          Math.max(y, window.innerHeight - y)
        );

        document.documentElement.classList.add("theme-transitioning");

        const transition = document.startViewTransition(() => {
          document.documentElement.classList.add("no-transitions");
          applyTheme();
        });

        transition.ready.then(() => {
          document.documentElement.animate(
            {
              clipPath: [
                `circle(0px at ${x}px ${y}px)`,
                `circle(${endRadius}px at ${x}px ${y}px)`,
              ],
            },
            {
              duration: 450,
              easing: "cubic-bezier(0.4, 0, 0.2, 1)",
              pseudoElement: "::view-transition-new(root)",
            }
          );
        });

        transition.finished.finally(() => {
          document.documentElement.classList.remove("theme-transitioning");
          // force repaint
          if (typeof document !== "undefined") {
            const _ = document.body.offsetHeight;
          }
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              document.documentElement.classList.remove("no-transitions");
            });
          });
        });
      },
      toggleLang: (event) => {
        const langs: Lang[] = ["en", "kz", "ru"];
        const currentIndex = langs.indexOf(get().lang);
        const nextLang = langs[(currentIndex + 1) % langs.length];
        const applyLang = () => {
          get().setLang(nextLang);
        };

        if (typeof document === "undefined" || !document.startViewTransition || !event) {
          if (typeof document !== "undefined") {
            document.documentElement.classList.add("theme-transitioning");
            applyLang();
            setTimeout(() => {
              document.documentElement.classList.remove("theme-transitioning");
              // force repaint
              if (typeof document !== "undefined") {
                const _ = document.body.offsetHeight;
              }
            }, 600);
          } else {
            applyLang();
          }
          return;
        }

        const x = event.clientX;
        const y = event.clientY;
        const endRadius = Math.hypot(
          Math.max(x, window.innerWidth - x),
          Math.max(y, window.innerHeight - y)
        );

        document.documentElement.classList.add("theme-transitioning");

        const transition = document.startViewTransition(() => {
          document.documentElement.classList.add("no-transitions");
          applyLang();
        });

        transition.ready.then(() => {
          document.documentElement.animate(
            {
              clipPath: [
                `circle(0px at ${x}px ${y}px)`,
                `circle(${endRadius}px at ${x}px ${y}px)`,
              ],
            },
            {
              duration: 450,
              easing: "cubic-bezier(0.4, 0, 0.2, 1)",
              pseudoElement: "::view-transition-new(root)",
            }
          );
        });

        transition.finished.finally(() => {
          document.documentElement.classList.remove("theme-transitioning");
          // force repaint
          if (typeof document !== "undefined") {
            const _ = document.body.offsetHeight;
          }
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              document.documentElement.classList.remove("no-transitions");
            });
          });
        });
      },
    }),
    {
      name: "wished-ui",
      storage: createJSONStorage(() => getStorage()),
    }
  )
);
