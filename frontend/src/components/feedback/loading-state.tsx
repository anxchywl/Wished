type LoadingStateProps = {
  label?: string;
};

/**
 * render loading state
 */
export function LoadingState({ label = "Loading" }: LoadingStateProps) {
  return <p className="text-sm text-muted">{label}</p>;
}
