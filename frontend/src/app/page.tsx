import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type HomePageProps = {
  searchParams: Promise<{
    tgWebAppStartParam?: string | string[];
  }>;
};

/**
 * redirect root to wishlists
 */
export default async function HomePage({ searchParams }: HomePageProps) {
  const params = await searchParams;
  const startParam = Array.isArray(params.tgWebAppStartParam)
    ? params.tgWebAppStartParam[0]
    : params.tgWebAppStartParam;

  if (startParam) {
    redirect(`/users?tgWebAppStartParam=${encodeURIComponent(startParam)}`);
  }

  redirect("/wishlists");
}
