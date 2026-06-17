import { WishlistDetailManager } from "@/features/wishlists";

export const dynamic = "force-dynamic";

type WishesPageProps = {
  params: Promise<{
    wishlistId: string;
  }>;
};

/**
 * render wishes page
 */
export default async function WishesPage({ params }: WishesPageProps) {
  const { wishlistId } = await params;

  return <WishlistDetailManager wishlistId={wishlistId} />;
}
