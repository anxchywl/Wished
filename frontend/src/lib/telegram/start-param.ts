const WISHLIST_PREFIX = "wl_";

type WishlistStartParam = {
  userId: string;
  wishlistId: string;
  shareToken?: string;
  username?: string;
};

function toBase64Url(value: string) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(value: string) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function encodeWishlistStartParam(userId: string, wishlistId: string, shareToken?: string) {
  const payload: WishlistStartParam = { userId, wishlistId };
  if (shareToken) payload.shareToken = shareToken;
  return `${WISHLIST_PREFIX}${toBase64Url(JSON.stringify(payload))}`;
}

export function decodeWishlistStartParam(value: string): WishlistStartParam | null {
  if (!value.startsWith(WISHLIST_PREFIX)) return null;

  try {
    const parsed = JSON.parse(fromBase64Url(value.slice(WISHLIST_PREFIX.length))) as Record<string, unknown>;
    if (typeof parsed.wishlistId !== "string" || !parsed.wishlistId) {
      return null;
    }
    // old links encoded username instead of userId — treat as unresolvable
    if (typeof parsed.userId !== "string" || !parsed.userId) {
      return null;
    }
    return {
      userId: parsed.userId,
      wishlistId: parsed.wishlistId,
      shareToken: typeof parsed.shareToken === "string" ? parsed.shareToken : undefined,
      username: typeof parsed.username === "string" ? parsed.username : undefined,
    };
  } catch {
    return null;
  }
}
