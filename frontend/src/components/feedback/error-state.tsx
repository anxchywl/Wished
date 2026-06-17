type ErrorStateProps = {
  title?: string;
  message: string;
};

/**
 * render error state
 */
export function ErrorState({ title = "Something went wrong", message }: ErrorStateProps) {
  return (
    <div className="rounded-md border border-border p-4">
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted">{message}</p>
    </div>
  );
}
