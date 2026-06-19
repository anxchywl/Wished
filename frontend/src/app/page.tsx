import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

/**
 * redirect root to wishlists
 */
export default function HomePage() {
  redirect("/wishlists");
}
