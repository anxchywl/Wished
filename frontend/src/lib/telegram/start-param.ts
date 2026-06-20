const WISHLIST_PREFIX = "wl_";

type WishlistStartParam = {
  username: string;
  wishlistId: string;
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

export function encodeWishlistStartParam(username: string, wishlistId: string) {
  return `${WISHLIST_PREFIX}${toBase64Url(JSON.stringify({ username, wishlistId }))}`;
}

export function decodeWishlistStartParam(value: string): WishlistStartParam | null {
  if (!value.startsWith(WISHLIST_PREFIX)) return null;

  try {
    const parsed = JSON.parse(fromBase64Url(value.slice(WISHLIST_PREFIX.length))) as Partial<WishlistStartParam>;
    if (
      typeof parsed.username !== "string" ||
      !parsed.username ||
      typeof parsed.wishlistId !== "string" ||
      !parsed.wishlistId
    ) {
      return null;
    }
    return {
      username: parsed.username,
      wishlistId: parsed.wishlistId,
    };
  } catch {
    return null;
  }
}
