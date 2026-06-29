import { NextRequest, NextResponse } from "next/server";

const PUBLIC_USERNAME_PATTERN = /^[a-z0-9_]{3,32}$/;
const RESERVED_PUBLIC_USERNAMES = new Set([
  "admin",
  "api",
  "settings",
  "login",
  "help",
  "support",
  "about",
  "users",
  "me",
  "wishlists",
  "wishes",
  "auth",
  "static",
  "assets",
]);

export function middleware(request: NextRequest) {
  const match = request.nextUrl.pathname.match(/^\/@([^/]+)$/);
  if (!match) {
    return NextResponse.next();
  }

  const username = decodeURIComponent(match[1]).trim().toLowerCase();
  if (!PUBLIC_USERNAME_PATTERN.test(username) || RESERVED_PUBLIC_USERNAMES.has(username)) {
    return NextResponse.next();
  }

  const botUsername = (
    process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ||
    process.env.TELEGRAM_BOT_USERNAME ||
    ""
  )
    .trim()
    .replace(/^@/, "");
  if (!botUsername) {
    return NextResponse.next();
  }

  return NextResponse.redirect(
    `https://t.me/${botUsername}?startapp=p_${encodeURIComponent(username)}`,
  );
}

export const config = {
  matcher: ["/:path*"],
};
