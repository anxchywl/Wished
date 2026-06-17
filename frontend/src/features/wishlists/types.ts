export type WishlistVisibility = "private" | "public";

export type Wishlist = {
  id: string;
  owner_user_id: string;
  title: string;
  description: string | null;
  visibility: WishlistVisibility;
  position: number;
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
