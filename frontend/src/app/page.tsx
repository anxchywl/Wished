import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

/**
 * render home page
 */
/**
 * render home page and forward launch parameters
 */
export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedParams = await searchParams;
  const query = new URLSearchParams(resolvedParams as Record<string, string>).toString();
  redirect(`/wishlists${query ? `?${query}` : ""}`);
}
