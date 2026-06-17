"use client";

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

/**
 * render startup error
 */
export default function GlobalError({ error, reset }: GlobalErrorProps) {
  return (
    <html lang="en">
      <body>
        <main className="min-h-dvh flex flex-col items-center justify-center gap-3 px-6 text-center bg-background text-foreground">
          <h1 className="text-base font-bold">Application error</h1>
          <p className="text-sm text-muted break-words">{error.message || "Unknown client error"}</p>
          <button
            className="h-10 rounded-xl bg-primary px-4 text-sm font-semibold text-white"
            onClick={reset}
            type="button"
          >
            Reload
          </button>
        </main>
      </body>
    </html>
  );
}
