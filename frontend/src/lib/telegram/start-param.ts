// "wb_" = compact binary format (two raw UUIDs); "wl_" = legacy base64(JSON) links
const WISHLIST_BINARY_PREFIX = "wb_";
const WISHLIST_PREFIX = "wl_";
const PROFILE_PREFIX = "p_";
const PUBLIC_USERNAME_PATTERN = /^[a-z0-9_]{3,32}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// 16 bytes per UUID, 2 UUIDs → 32 bytes → 43 base64url chars (no padding)
const BINARY_UUIDS_LENGTH = 43;

type WishlistStartParam = {
  userId: string;
  wishlistId: string;
  shareToken?: string;
  username?: string;
};

function toBase64Url(value: string) {
  const bytes = new TextEncoder().encode(value);
  return bytesToBase64Url(bytes);
}

function fromBase64Url(value: string) {
  return new TextDecoder().decode(base64UrlToBytes(value));
}

function bytesToBase64Url(bytes: Uint8Array) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlToBytes(value: string) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function uuidToBytes(uuid: string): Uint8Array | null {
  if (!UUID_PATTERN.test(uuid)) return null;
  const hex = uuid.replace(/-/g, "");
  const bytes = new Uint8Array(16);
  for (let i = 0; i < 16; i += 1) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function bytesToUuid(bytes: Uint8Array): string {
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
}

export function encodeWishlistStartParam(userId: string, wishlistId: string, shareToken?: string) {
  const userBytes = uuidToBytes(userId);
  const wishlistBytes = uuidToBytes(wishlistId);
  // compact binary form keeps the deep link short; fall back to legacy JSON if ids aren't UUIDs
  if (userBytes && wishlistBytes) {
    const blob = new Uint8Array(32);
    blob.set(userBytes, 0);
    blob.set(wishlistBytes, 16);
    return `${WISHLIST_BINARY_PREFIX}${bytesToBase64Url(blob)}${shareToken ?? ""}`;
  }
  const payload: WishlistStartParam = { userId, wishlistId };
  if (shareToken) payload.shareToken = shareToken;
  return `${WISHLIST_PREFIX}${toBase64Url(JSON.stringify(payload))}`;
}

export function decodeWishlistStartParam(value: string): WishlistStartParam | null {
  if (value.startsWith(WISHLIST_BINARY_PREFIX)) {
    try {
      const body = value.slice(WISHLIST_BINARY_PREFIX.length);
      const bytes = base64UrlToBytes(body.slice(0, BINARY_UUIDS_LENGTH));
      if (bytes.length < 32) return null;
      const shareToken = body.slice(BINARY_UUIDS_LENGTH);
      return {
        userId: bytesToUuid(bytes.slice(0, 16)),
        wishlistId: bytesToUuid(bytes.slice(16, 32)),
        shareToken: shareToken || undefined,
      };
    } catch {
      return null;
    }
  }

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

export function encodeProfileStartParam(publicUsername: string) {
  const normalizedUsername = publicUsername.trim().replace(/^@/, "").toLowerCase();
  if (!PUBLIC_USERNAME_PATTERN.test(normalizedUsername)) return null;
  return `${PROFILE_PREFIX}${normalizedUsername}`;
}

export function decodeProfileStartParam(value: string): string | null {
  if (!value.startsWith(PROFILE_PREFIX)) return null;
  const normalizedUsername = value.slice(PROFILE_PREFIX.length).trim().replace(/^@/, "").toLowerCase();
  return PUBLIC_USERNAME_PATTERN.test(normalizedUsername) ? normalizedUsername : null;
}
