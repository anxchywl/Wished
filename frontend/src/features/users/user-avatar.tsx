"use client";

// user avatar
import { useState } from "react";

type AvatarUser = {
  first_name?: string | null;
  last_name?: string | null;
  username?: string | null;
  photo_url?: string | null;
};

/**
 * render user avatar — initials show immediately, photo fades in on load
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

  const [imgLoaded, setImgLoaded] = useState(() => {
    if (!user.photo_url || typeof window === "undefined") return false;
    const probe = new window.Image();
    probe.src = user.photo_url;
    return probe.complete && probe.naturalWidth > 0;
  });
  const [imgFailed, setImgFailed] = useState(false);

  return (
    <div className="relative w-9 h-9 rounded-full bg-primary/10 border border-border/80 flex-shrink-0 overflow-hidden flex items-center justify-center">
      {/* initials always present as base layer */}
      <span className="text-xs font-bold text-primary">{initials}</span>
      {/* photo overlays on top and fades in once loaded */}
      {user.photo_url && !imgFailed ? (
        <img
          src={user.photo_url}
          alt={displayName}
          className="absolute inset-0 w-full h-full object-cover rounded-full transition-opacity duration-200"
          style={{ opacity: imgLoaded ? 1 : 0 }}
          onLoad={() => setImgLoaded(true)}
          onError={() => setImgFailed(true)}
        />
      ) : null}
    </div>
  );
}
