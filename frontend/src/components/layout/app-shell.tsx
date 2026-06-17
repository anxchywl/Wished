import type { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
};

/**
 * render app shell
 */
export function AppShell({ children }: AppShellProps) {
  return <div className="min-h-dvh bg-background text-foreground">{children}</div>;
}
