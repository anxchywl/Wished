"use client";

import { useEffect, useState } from "react";

type AvatarUser = {
  first_name?: string | null;
  last_name?: string | null;
  username?: string | null;
  photo_url?: string | null;
};

const revealedAvatarUrls = new Set<string>();

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

  const photoUrl = user.photo_url ?? "";
  const [imgLoaded, setImgLoaded] = useState(() => Boolean(photoUrl && revealedAvatarUrls.has(photoUrl)));
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    setImgFailed(false);
    setImgLoaded(Boolean(photoUrl && revealedAvatarUrls.has(photoUrl)));
  }, [photoUrl]);

  return (
    <div className="relative w-9 h-9 rounded-full bg-primary/10 border border-border/80 flex-shrink-0 overflow-hidden flex items-center justify-center">
      <span className="text-xs font-bold text-primary">{initials}</span>
      {photoUrl && !imgFailed ? (
        <img
          src={photoUrl}
          alt={displayName}
          className="absolute inset-0 w-full h-full object-cover rounded-full transition-opacity duration-200"
          style={{ opacity: imgLoaded ? 1 : 0 }}
          onLoad={() => {
            revealedAvatarUrls.add(photoUrl);
            setImgLoaded(true);
          }}
          onError={() => setImgFailed(true)}
        />
      ) : null}
    </div>
  );
}
