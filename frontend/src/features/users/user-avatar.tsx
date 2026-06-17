// user avatar
type AvatarUser = {
  first_name?: string | null;
  last_name?: string | null;
  username?: string | null;
  photo_url?: string | null;
};

/**
 * render user avatar
 */
export function UserAvatar({ user }: { user: AvatarUser }) {
  const displayName = user.first_name
    ? [user.first_name, user.last_name].filter(Boolean).join(" ")
    : (user.username ? `@${user.username}` : "?");
  const initials = displayName
    .split(" ")
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="relative w-9 h-9 rounded-full bg-primary/10 border border-border/80 flex-shrink-0 overflow-hidden flex items-center justify-center">
      {user.photo_url ? (
        <>
          <img
            src={user.photo_url}
            alt={displayName}
            className="absolute inset-0 w-full h-full object-cover rounded-full"
            onError={(event) => {
              (event.currentTarget as HTMLImageElement).style.display = "none";
              const fallback = event.currentTarget.nextElementSibling as HTMLElement | null;
              if (fallback) fallback.style.display = "flex";
            }}
          />
          <span className="text-xs font-bold text-primary flex items-center justify-center w-full h-full" style={{ display: "none" }}>
            {initials}
          </span>
        </>
      ) : (
        <span className="text-xs font-bold text-primary">{initials}</span>
      )}
    </div>
  );
}

