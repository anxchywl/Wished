// wishlist helpers

export const DEFAULT_COVER_GRADIENT = "linear-gradient(135deg, hsl(210 100% 65%), hsl(280 100% 65%))";

/**
 * parse cover photo and clean description
 */
export function parseWishlistDescription(rawDescription: string | null | undefined): {
  description: string | null;
  coverStyle: string;
} {
  if (!rawDescription) {
    return { description: null, coverStyle: DEFAULT_COVER_GRADIENT };
  }

  const match = rawDescription.match(/\[cover:([^\]]+)\]/);
  if (!match) {
    return { description: rawDescription, coverStyle: DEFAULT_COVER_GRADIENT };
  }

  const [fullMatch, coverStyle] = match;
  const description = rawDescription.replace(fullMatch, "").trim() || null;

  return { description, coverStyle };
}

/**
 * format description — cover is now stored in MinIO, not embedded in description
 */
export function formatWishlistDescription(description: string | null | undefined): string {
  return description ? description.trim() : "";
}

/**
 * compress image file using canvas to small base64 string
 */
export function compressImage(file: File, maxWidth = 600, maxHeight = 400, quality = 0.65): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        let width = img.width;
        let height = img.height;

        if (width > height) {
          if (width > maxWidth) {
            height = Math.round((height * maxWidth) / width);
            width = maxWidth;
          }
        } else {
          if (height > maxHeight) {
            width = Math.round((width * maxHeight) / height);
            height = maxHeight;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(e.target?.result as string);
          return;
        }

        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", quality));
      };
      img.onerror = () => reject(new Error("Image load error"));
      img.src = e.target?.result as string;
    };
    reader.onerror = () => reject(new Error("File read error"));
    reader.readAsDataURL(file);
  });
}
