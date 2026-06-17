type EmptyStateProps = {
  title: string;
  description?: string;
};

/**
 * render empty state
 */
export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded-md border border-border p-4">
      <p className="text-sm font-medium">{title}</p>
      {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
    </div>
  );
}
