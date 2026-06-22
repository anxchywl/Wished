function fromBase64Url(value) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function decodeWishlistStartParam(value) {
  const WISHLIST_PREFIX = "wl_";
  if (!value.startsWith(WISHLIST_PREFIX)) return null;

  try {
    const str = fromBase64Url(value.slice(WISHLIST_PREFIX.length));
    console.log("Decoded string:", str);
    const parsed = JSON.parse(str);
    console.log("Parsed:", parsed);
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
      shareToken: typeof parsed.shareToken === "string" ? parsed.shareToken : undefined,
    };
  } catch (err) {
    console.error("Error decoding:", err);
    return null;
  }
}

decodeWishlistStartParam("wl_eyJ1c2VybmFtZSI6ImVta2FlcHQiLCJ3aXNobGlzdElkIjoiOTIwODhlNGYtOGU5NS00ZWFjLWE4NDQtNWM5MmNlYTJjZTZlIiwic2hhcmVUb2tlbiI6IkllUjdqWmllVTFPa0xEM25NaTlKSXQxQ0pBdS1EODZKMzdtWGF6T0xJN1UifQ");
