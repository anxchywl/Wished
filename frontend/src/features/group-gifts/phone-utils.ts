// Strict international phone: + followed by 7–15 digits (spaces/dashes stripped before check)
export const PHONE_STRICT_RE = /^\+\d{7,15}$/;
// Free-form credentials: 4–50 non-whitespace characters
export const CREDENTIALS_RE = /^[^\s]{4,50}$/;

export function isPhoneMode(value: string) {
  return value.startsWith("+");
}

export function formatPhoneInput(raw: string): string {
  if (!raw.startsWith("+")) return raw;
  const digits = raw.slice(1).replace(/\D/g, "").slice(0, 15);
  if (!digits) return "+";

  // +7 (Russia / Kazakhstan): +7 ### ### ## ##
  if (digits.startsWith("7")) {
    const d = digits.slice(1, 11);
    let out = "+7";
    if (d.length > 0) out += " " + d.slice(0, 3);
    if (d.length > 3) out += " " + d.slice(3, 6);
    if (d.length > 6) out += " " + d.slice(6, 8);
    if (d.length > 8) out += " " + d.slice(8, 10);
    return out;
  }

  // +1 (USA / Canada): +1 ### ###-####
  if (digits.startsWith("1")) {
    const d = digits.slice(1, 11);
    let out = "+1";
    if (d.length > 0) out += " " + d.slice(0, 3);
    if (d.length > 3) out += " " + d.slice(3, 6);
    if (d.length > 6) out += "-" + d.slice(6, 10);
    return out;
  }

  // +44 (UK): +44 #### ######
  if (digits.startsWith("44")) {
    const d = digits.slice(2, 13);
    let out = "+44";
    if (d.length > 0) out += " " + d.slice(0, 4);
    if (d.length > 4) out += " " + d.slice(4, 10);
    return out;
  }

  // +49 (Germany): +49 ### #######
  if (digits.startsWith("49")) {
    const d = digits.slice(2, 13);
    let out = "+49";
    if (d.length > 0) out += " " + d.slice(0, 3);
    if (d.length > 3) out += " " + d.slice(3, 10);
    return out;
  }

  // +33 (France): +33 # ## ## ## ##
  if (digits.startsWith("33")) {
    const d = digits.slice(2, 12);
    let out = "+33";
    if (d.length > 0) out += " " + d.slice(0, 1);
    if (d.length > 1) out += " " + d.slice(1, 3);
    if (d.length > 3) out += " " + d.slice(3, 5);
    if (d.length > 5) out += " " + d.slice(5, 7);
    if (d.length > 7) out += " " + d.slice(7, 9);
    return out;
  }

  // Generic: keep digits with + (no extra formatting, max 15 digits)
  return "+" + digits;
}

export function formatAccountInput(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 16);
  const groups = digits.match(/.{1,4}/g);
  return groups ? groups.join(" ") : digits;
}

export function validatePhoneOrCredentials(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (isPhoneMode(v)) {
    const digits = v.replace(/[\s\-()+]/g, "").replace(/^\+/, "");
    return digits.length >= 7 && digits.length <= 15 && /^\d+$/.test(digits);
  }
  const noSpaces = v.replace(/\s+/g, "");
  return CREDENTIALS_RE.test(noSpaces);
}
