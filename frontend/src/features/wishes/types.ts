import type { GroupGiftSummary } from "@/features/group-gifts/api";
export type { GroupGiftSummary };

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
  _stableKey?: string;
  wishlist_id: string;
  title: string;
  description: string | null;
  url: string | null;
  priority: number;
  position: number;
  price: string | null;
  currency: string | null;
  status: string;
  original_product_url: string | null;
  source_marketplace: string | null;
  images: WishImage[];
  created_at: string;
  updated_at: string;
  group_gift: GroupGiftSummary | null;
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
  original_product_url?: string | null;
  source_marketplace?: string | null;
  pending_marketplace_image_id?: string | null;
};

export type ProductImportPayload = {
  original_url: string;
  title?: string | null;
  description?: string | null;
  price?: string | null;
  currency?: string | null;
  image_url?: string | null;
  marketplace?: string | null;
};

export type ProductImportResult = {
  title: string | null;
  description: string | null;
  price: string | null;
  currency: string | null;
  marketplace: string | null;
  original_url: string;
  pending_image_id: string | null;
  pending_image_thumbnail_url: string | null;
};

export type WishUpdateInput = {
  wishlist_id?: string;
  title?: string;
  description?: string | null;
  url?: string | null;
  original_product_url?: string | null;
  priority?: number;
  price?: string | null;
  currency?: string | null;
};

export type WishReorderInput = {
  wish_ids: string[];
};

export type LinkPreviewRequest = {
  url: string;
};

export type LinkPreviewResult = {
  title: string | null;
  description: string | null;
  image_url: string | null;
  price: string | null;
  currency: string | null;
  source: string | null;
};
