"use client";

import { useState } from "react";
import type React from "react";

import { DEFAULT_COVER_GRADIENT } from "@/features/wishlists/utils";

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

const wishPlaceholderPalette = [
  ["#f9a8d4", "#c084fc", "#60a5fa"],
  ["#fcd34d", "#fb7185", "#a78bfa"],
  ["#86efac", "#67e8f9", "#818cf8"],
  ["#fdba74", "#f472b6", "#93c5fd"],
  ["#c4b5fd", "#f0abfc", "#7dd3fc"],
  ["#f0abfc", "#5eead4", "#93c5fd"],
  ["#fde68a", "#f9a8d4", "#38bdf8"],
  ["#bbf7d0", "#a78bfa", "#fda4af"],
];

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
  const hash = hashString(`${id}-${title}`);
  const colors = wishPlaceholderPalette[hash % wishPlaceholderPalette.length];
  const angle = 120 + (hash % 70);
  const firstStop = 12 + (hash % 12);
  const secondStop = 42 + (hash % 18);
  const variant = `linear-gradient(${angle}deg, ${colors[0]} 0%, ${colors[0]} ${firstStop}%, ${colors[1]} ${secondStop}%, ${colors[2]} 100%)`;

  return (
    <div className={`wish-image-placeholder ${className}`} style={{ background: variant }} aria-hidden="true">
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
  if (url.includes("localhost:9000")) {
    return url.replace("http://localhost:9000", "https://jarring-succulent-jumbo.ngrok-free.dev");
  }
  if (url.includes("127.0.0.1:9000")) {
    return url.replace("http://127.0.0.1:9000", "https://jarring-succulent-jumbo.ngrok-free.dev");
  }
  return url;
}

/**
 * wish image thumbnail
 */
export function WishImageThumb({ id, title, imageUrl, className = "" }: WishVisualProps) {
  const [failed, setFailed] = useState(false);

  if (!imageUrl || failed) {
    return <WishImagePlaceholder id={id} title={title} className={className} />;
  }

  return (
    <img
      src={resolveImageUrl(imageUrl)}
      alt={title}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
