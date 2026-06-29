import { notFound, redirect } from "next/navigation";

export const dynamic = "force-dynamic";

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

type PublicProfileLinkPageProps = {
  params: Promise<{
    publicUsername: string;
  }>;
};

/**
 * launch a clean public profile URL into the telegram mini app
 */
export default async function PublicProfileLinkPage({ params }: PublicProfileLinkPageProps) {
  const { publicUsername } = await params;
  const decodedPublicUsername = decodeURIComponent(publicUsername);
  if (!decodedPublicUsername.startsWith("@")) {
    notFound();
  }

  const username = decodedPublicUsername.slice(1).trim().toLowerCase();
  if (!PUBLIC_USERNAME_PATTERN.test(username) || RESERVED_PUBLIC_USERNAMES.has(username)) {
    notFound();
  }

  const botUsername = (
    process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ||
    process.env.TELEGRAM_BOT_USERNAME ||
    ""
  )
    .trim()
    .replace(/^@/, "");
  if (!botUsername) {
    notFound();
  }

  redirect(`https://t.me/${botUsername}?startapp=p_${encodeURIComponent(username)}`);
}
