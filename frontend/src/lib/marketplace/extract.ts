/**
 * Client-side product metadata extraction.
 *
 * The user's browser fetches the marketplace page (residential IP — no bot blocking)
 * and this module extracts structured data from the HTML response.
 * CORS will block most cross-origin reads; that is handled by the caller as a graceful
 * fallback rather than an error.
 *
 * Extraction priority: JSON-LD → OpenGraph → (no CSS selectors — too fragile)
 */

export type ExtractedProduct = {
  title?: string;
  description?: string;
  price?: string;
  currency?: string;
  image_url?: string;
  marketplace?: string;
};

// exact host → marketplace label. Substring matching is avoided so spoof hosts
// like "kaspi.evil.com" or "notkaspi.com" are not misclassified. This label is
// cosmetic only; the backend re-derives the marketplace from its own allowlist.
const MARKETPLACE_BY_HOST: Record<string, string> = {
  "kaspi.kz": "kaspi",
  "www.kaspi.kz": "kaspi",
  "wildberries.ru": "wildberries",
  "www.wildberries.ru": "wildberries",
  "wildberries.kz": "wildberries",
  "www.wildberries.kz": "wildberries",
  "ozon.ru": "ozon",
  "www.ozon.ru": "ozon",
  "ozon.kz": "ozon",
  "www.ozon.kz": "ozon",
};

export function detectMarketplace(url: string): string | undefined {
  try {
    const { hostname } = new URL(url);
    return MARKETPLACE_BY_HOST[hostname.toLowerCase()];
  } catch {}
  return undefined;
}

function extractJsonLd(doc: Document): Partial<ExtractedProduct> {
  const scripts = doc.querySelectorAll('script[type="application/ld+json"]');
  for (const script of Array.from(scripts)) {
    try {
      const raw: unknown = JSON.parse(script.textContent ?? "");
      const data = Array.isArray(raw)
        ? raw.find((d) => typeof d === "object" && d !== null && (d as Record<string, unknown>)["@type"] === "Product")
        : raw;

      if (
        !data ||
        typeof data !== "object" ||
        (data as Record<string, unknown>)["@type"] !== "Product"
      ) {
        continue;
      }

      const product = data as Record<string, unknown>;
      const result: Partial<ExtractedProduct> = {};

      if (typeof product.name === "string") result.title = product.name.trim();
      if (typeof product.description === "string") result.description = product.description.trim();

      const img = product.image;
      if (typeof img === "string") result.image_url = img;
      else if (Array.isArray(img) && typeof img[0] === "string") result.image_url = img[0];

      const rawOffers = product.offers;
      const offers =
        Array.isArray(rawOffers) && rawOffers.length > 0
          ? rawOffers[0]
          : rawOffers;

      if (offers && typeof offers === "object") {
        const o = offers as Record<string, unknown>;
        if (o.price != null) result.price = String(o.price);
        if (typeof o.priceCurrency === "string")
          result.currency = o.priceCurrency.toUpperCase().slice(0, 3);
      }

      if (result.title) return result;
    } catch {}
  }
  return {};
}

function extractOpenGraph(doc: Document): Partial<ExtractedProduct> {
  const get = (prop: string) =>
    doc.querySelector(`meta[property="${prop}"]`)?.getAttribute("content") ??
    doc.querySelector(`meta[name="${prop}"]`)?.getAttribute("content") ??
    undefined;

  const result: Partial<ExtractedProduct> = {};

  const title = get("og:title");
  if (title) result.title = title.trim();

  const image = get("og:image") ?? get("og:image:url");
  if (image) result.image_url = image;

  const desc = get("og:description");
  if (desc) result.description = desc.trim();

  const price = get("og:price:amount") ?? get("product:price:amount");
  if (price) result.price = price;

  const currency = get("og:price:currency") ?? get("product:price:currency");
  if (currency) result.currency = currency.toUpperCase().slice(0, 3);

  return result;
}

/**
 * Attempt to fetch the product page from the user's browser and extract metadata.
 *
 * Returns whatever could be extracted. If CORS blocks the response (expected for
 * most marketplaces), returns only the detected marketplace name. The caller
 * should always send the result to the backend — the backend may have additional
 * data sources (e.g. Wildberries card API).
 */
export async function fetchAndExtract(url: string): Promise<ExtractedProduct> {
  const marketplace = detectMarketplace(url);

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);

    let html: string;
    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "text/html,application/xhtml+xml" },
      });
      html = await response.text();
    } finally {
      clearTimeout(timeout);
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    const fromJsonLd = extractJsonLd(doc);
    if (fromJsonLd.title) return { marketplace, ...fromJsonLd };

    const fromOg = extractOpenGraph(doc);
    if (fromOg.title) return { marketplace, ...fromOg };
  } catch {
    // CORS error, AbortError (timeout), or network failure — all expected
    // The backend will still be called; it may return data from the WB card API
  }

  return { marketplace };
}
