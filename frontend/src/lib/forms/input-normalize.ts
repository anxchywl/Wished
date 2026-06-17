// input normalization helpers

const riskyCharsPattern = /[<>&"'/`\\;]/g;
const hiddenCharsPattern = /[\u200b-\u200d\uFEFF\u200e\u200f\u202a-\u202e\u0000-\u001f\u007f-\u009f]/g;

/**
 * normalize text input
 */
export function normalizeTextInput(value: string, maxLength: number): string {
  return value
    .slice(0, maxLength)
    .replace(hiddenCharsPattern, "")
    .replace(riskyCharsPattern, "")
    .replace(/^\s+/, "")
    .replace(/\s{2,}/g, " ");
}

/**
 * finalize text input
 */
export function finalizeTextInput(value: string, maxLength: number): string {
  return normalizeTextInput(value, maxLength).replace(/\s+/g, " ").trim();
}

/**
 * normalize priority input
 */
export function normalizePriorityInput(value: string): number {
  const parsed = Number(value.replace(/[^\d]/g, ""));
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.min(5, Math.max(1, parsed));
}

/**
 * normalize price input
 */
export function normalizePriceInput(value: string): string {
  const cleaned = value.replace(/[^\d.]/g, "");
  const [integer = "", ...decimalParts] = cleaned.split(".");
  const normalizedInteger = integer.replace(/^0+(?=\d)/, "").slice(0, 10);
  const decimal = decimalParts.join("").slice(0, 2);

  if (!cleaned.includes(".")) {
    return normalizedInteger;
  }

  return `${normalizedInteger || "0"}.${decimal}`;
}

/**
 * finalize price input
 */
export function finalizePriceInput(value: string): string {
  return normalizePriceInput(value).replace(/\.$/, "");
}

/**
 * normalize currency input
 */
export function normalizeCurrencyInput(value: string): string {
  return value.replace(/[^a-zA-Z]/g, "").toUpperCase().slice(0, 3);
}
