import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";

/**
 * Navigate with a CSS View Transition. Falls back to plain push when the API is
 * unavailable (older WebViews). Direction drives the enter/exit animation:
 * "forward" slides up/in (page deepens), "back" slides down/in (page returns).
 */
export function navigateWithTransition(
  router: AppRouterInstance,
  href: string,
  direction: "forward" | "back" = "forward",
): void {
  if (typeof document === "undefined" || !document.startViewTransition) {
    router.push(href);
    return;
  }

  const html = document.documentElement;
  html.classList.add("page-transitioning");
  if (direction === "back") {
    html.setAttribute("data-nav-direction", "back");
  } else {
    html.removeAttribute("data-nav-direction");
  }

  const t = document.startViewTransition(() => {
    router.push(href);
  });

  t.finished.finally(() => {
    html.classList.remove("page-transitioning");
    html.removeAttribute("data-nav-direction");
  });
}
