import { WishlistDetailManager } from "@/features/wishlists";

export const dynamic = "force-dynamic";

type WishlistDetailPageProps = {
  params: Promise<{
    wishlistId: string;
  }>;
};

/**
 * render dedicated wishlist page
 */
export default async function WishlistDetailPage({ params }: WishlistDetailPageProps) {
  const { wishlistId } = await params;

  return <WishlistDetailManager wishlistId={wishlistId} />;
}
