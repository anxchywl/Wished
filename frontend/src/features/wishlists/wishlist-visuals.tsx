"use client";

import { useEffect, useState } from "react";
import type React from "react";

import { DEFAULT_COVER_GRADIENT } from "@/features/wishlists/utils";
import { useAuthStore } from "@/stores/auth-store";

type WishVisualProps = {
  id: string;
  title: string;
  imageUrl?: string | null;
  className?: string;
};

type WishlistCoverStyleInput = {
  coverStyle: string;
  fallback: {
    angle: number;
    a: string;
    b: string;
    c: string;
    d: string;
  };
};


const imageObjectUrlCache = new Map<string, string>();
const imageObjectUrlRequests = new Map<string, Promise<string>>();
const PERSISTENT_IMAGE_CACHE = "wished-images-v1";

function stableImageCacheKey(url: string, accountId: number | null): string {
  const resolvedUrl = resolveImageUrl(url);
  try {
    const parsed = new URL(resolvedUrl, window.location.origin);
    return `${accountId ?? "anonymous"}:${parsed.pathname}`;
  } catch {
    return `${accountId ?? "anonymous"}:${resolvedUrl.split("?")[0]}`;
  }
}

async function loadCachedImage(url: string, accountId: number | null): Promise<string> {
  const resolvedUrl = resolveImageUrl(url);
  const cacheKey = stableImageCacheKey(url, accountId);
  const cached = imageObjectUrlCache.get(cacheKey);
  if (cached) return cached;

  const pending = imageObjectUrlRequests.get(cacheKey);
  if (pending) return pending;

  const request = (async () => {
    const persistentCache = "caches" in window
      ? await caches.open(PERSISTENT_IMAGE_CACHE)
      : null;
    const persistentRequest = new Request(
      `${window.location.origin}/wished-image-cache/${encodeURIComponent(cacheKey)}`,
    );
    const storedResponse = await persistentCache?.match(persistentRequest);
    const response = storedResponse ?? await fetch(resolvedUrl);
    if (!response.ok) throw new Error(`image request failed: ${response.status}`);
    if (!storedResponse && persistentCache) {
      await persistentCache.put(persistentRequest, response.clone());
    }
    return response.blob();
  })()
    .then((blob) => {
      const objectUrl = URL.createObjectURL(blob);
      imageObjectUrlCache.set(cacheKey, objectUrl);
      imageObjectUrlRequests.delete(cacheKey);
      return objectUrl;
    })
    .catch((error) => {
      imageObjectUrlRequests.delete(cacheKey);
      throw error;
    });

  imageObjectUrlRequests.set(cacheKey, request);
  return request;
}

/**
 * build cover gradient
 */
function buildCoverGradient(fallback: WishlistCoverStyleInput["fallback"]) {
  return `radial-gradient(ellipse at 12% 8%, color-mix(in srgb, ${fallback.c} 42%, transparent) 0%, transparent 58%), radial-gradient(ellipse at 90% 18%, color-mix(in srgb, ${fallback.d} 36%, transparent) 0%, transparent 62%), radial-gradient(ellipse at 46% 92%, color-mix(in srgb, ${fallback.a} 34%, transparent) 0%, transparent 68%), linear-gradient(${fallback.angle}deg, color-mix(in srgb, ${fallback.a} 74%, #ffffff) 0%, color-mix(in srgb, ${fallback.b} 82%, #ffffff) 48%, color-mix(in srgb, ${fallback.c} 66%, #ffffff) 100%)`;
}

/**
 * hash string value
 */
function hashString(value: string): number {
  return value.split("").reduce((hash, char) => (hash * 31 + char.charCodeAt(0)) >>> 0, 0);
}

/**
 * get wishlist cover style
 */
export function getWishlistCoverStyle({ coverStyle, fallback }: WishlistCoverStyleInput): React.CSSProperties {
  const fallbackVars = {
    "--fallback-angle": `${fallback.angle}deg`,
    "--fallback-a": fallback.a,
    "--fallback-b": fallback.b,
    "--fallback-c": fallback.c,
    "--fallback-d": fallback.d,
  } as React.CSSProperties;

  if (!coverStyle || coverStyle === DEFAULT_COVER_GRADIENT) {
    return fallbackVars;
  }

  if (coverStyle.startsWith("data:") || coverStyle.startsWith("http")) {
    return {
      ...fallbackVars,
      backgroundImage: `url(${coverStyle}), ${buildCoverGradient(fallback)}`,
      backgroundSize: "cover, 180% 180%",
      backgroundPosition: "center, center",
    };
  }

  return {
    ...fallbackVars,
    background: coverStyle,
  };
}

/**
 * wish image placeholder
 */
export function WishImagePlaceholder({ id, title, className = "" }: Omit<WishVisualProps, "imageUrl">) {
  // hash on title only so the gradient is stable during the optimistic→real id transition
  const hash = hashString(title);
  // golden-angle hue steps so adjacent wishes never share the same hue
  const h1 = (hash * 137) % 360;
  const h2 = (h1 + 50 + (hash % 60)) % 360;
  const s1 = 75 + (hash % 15);
  const l1 = 72 + (hash % 12);
  const s2 = 70 + ((hash >> 5) % 15);
  const l2 = 62 + ((hash >> 5) % 12);
  const angle = 110 + (hash % 100);
  const bg = `linear-gradient(${angle}deg, hsl(${h1},${s1}%,${l1}%) 0%, hsl(${h2},${s2}%,${l2}%) 100%)`;

  return (
    <div className={`wish-image-placeholder ${className}`} style={{ background: bg }} aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M20 12v8.5H4V12" />
        <path d="M3.5 8h17v4h-17z" />
        <path d="M12 8v12.5" />
        <path d="M12 8H8.5a2.5 2.5 0 1 1 2.35-3.35L12 8Z" />
        <path d="M12 8h3.5a2.5 2.5 0 1 0-2.35-3.35L12 8Z" />
      </svg>
    </div>
  );
}

/**
 * resolve image url helper
 */
export function resolveImageUrl(url?: string | null): string {
  if (!url) return "";
  // Serve MinIO objects through the Next.js /wished-media rewrite (same tunnel as the Mini App).
  // Handles both direct localhost access and Docker-internal minio:9000 hostnames.
  if (url.includes("localhost:9000") || url.includes("127.0.0.1:9000")) {
    return url.replace(/^https?:\/\/(localhost|127\.0\.0\.1):9000/, "");
  }
  if (url.includes("minio:9000")) {
    return url.replace(/^https?:\/\/minio:9000/, "");
  }
  return url;
}

/**
 * wish image thumbnail
 */
export function WishImageThumb({ id, title, imageUrl, className = "" }: WishVisualProps) {
  const accountId = useAuthStore((state) => state.tgUserId);
  const [failed, setFailed] = useState(false);
  const [displayUrl, setDisplayUrl] = useState("");

  useEffect(() => {
    setFailed(false);
    if (!imageUrl) {
      setDisplayUrl("");
      return;
    }

    if (imageUrl.startsWith("data:") || imageUrl.startsWith("blob:")) {
      setDisplayUrl(imageUrl);
      return;
    }

    let active = true;
    const cacheKey = stableImageCacheKey(imageUrl, accountId);
    setDisplayUrl(imageObjectUrlCache.get(cacheKey) ?? "");
    loadCachedImage(imageUrl, accountId)
      .then((url) => {
        if (active) setDisplayUrl(url);
      })
      .catch(() => {
        if (active) setFailed(true);
      });

    return () => {
      active = false;
    };
  }, [accountId, imageUrl]);

  if (!imageUrl || failed) {
    return <WishImagePlaceholder id={id} title={title} className={className} />;
  }

  if (!displayUrl) {
    return <WishImagePlaceholder id={id} title={title} className={className} />;
  }

  return (
    <img
      src={displayUrl}
      alt={title}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
