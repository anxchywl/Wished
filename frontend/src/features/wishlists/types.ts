export type WishlistVisibility = "private" | "public";

export type Wishlist = {
  id: string;
  owner_user_id: string;
  title: string;
  description: string | null;
  visibility: WishlistVisibility;
  position: number;
  cover_image_url: string | null;
  cover_thumbnail_url: string | null;
  cover_medium_url: string | null;
  created_at: string;
  updated_at: string;
};

export type WishlistListResponse = {
  items: Wishlist[];
};

export type WishlistCreateInput = {
  title: string;
  description?: string | null;
  visibility?: WishlistVisibility | null;
};

export type WishlistUpdateInput = {
  title?: string;
  description?: string | null;
  visibility?: WishlistVisibility;
};

export type WishlistReorderInput = {
  wishlist_ids: string[];
};
