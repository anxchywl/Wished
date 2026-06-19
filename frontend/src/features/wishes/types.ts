export type WishImage = {
  id: string;
  wish_id: string;
  url: string;
  thumbnail_url: string | null;
  medium_url: string | null;
  file_name: string;
  content_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
};

export type Wish = {
  id: string;
  wishlist_id: string;
  title: string;
  description: string | null;
  url: string | null;
  priority: number;
  position: number;
  price: string | null;
  currency: string | null;
  images: WishImage[];
  created_at: string;
  updated_at: string;
};

export type WishListResponse = {
  items: Wish[];
};

export type WishCreateInput = {
  title: string;
  description?: string | null;
  url?: string | null;
  priority?: number;
  price?: string | null;
  currency?: string | null;
};

export type WishUpdateInput = {
  wishlist_id?: string;
  title?: string;
  description?: string | null;
  url?: string | null;
  priority?: number;
  price?: string | null;
  currency?: string | null;
};

export type WishReorderInput = {
  wish_ids: string[];
};
