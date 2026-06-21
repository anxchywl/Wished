import { apiClient } from "@/lib/api";
import type {
  ProductImportPayload,
  ProductImportResult,
  Wish,
  WishCreateInput,
  WishImage,
  WishListResponse,
  WishReorderInput,
  WishUpdateInput,
} from "@/features/wishes/types";

/**
 * import product data from a marketplace URL (client-assisted: caller extracts metadata)
 */
export function importProductUrl(accessToken: string, payload: ProductImportPayload) {
  return apiClient<ProductImportResult>("/marketplace/import", {
    method: "POST",
    accessToken,
    body: payload,
  });
}

/**
 * list wishes
 */
export function listWishes(accessToken: string, wishlistId: string, shareToken?: string | null) {
  const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : "";
  return apiClient<WishListResponse>(`/wishlists/${wishlistId}/wishes${query}`, { accessToken });
}

/**
 * create wish
 */
export function createWish(accessToken: string, wishlistId: string, input: WishCreateInput) {
  return apiClient<Wish>(`/wishlists/${wishlistId}/wishes`, {
    method: "POST",
    accessToken,
    body: input,
  });
}

/**
 * update wish
 */
export function updateWish(accessToken: string, wishId: string, input: WishUpdateInput) {
  return apiClient<Wish>(`/wishes/${wishId}`, {
    method: "PATCH",
    accessToken,
    body: input,
  });
}

/**
 * reorder wishes
 */
export function reorderWishes(accessToken: string, wishlistId: string, input: WishReorderInput) {
  return apiClient<WishListResponse>(`/wishlists/${wishlistId}/wishes/reorder`, {
    method: "PATCH",
    accessToken,
    body: input,
  });
}

/**
 * delete wish
 */
export function deleteWish(accessToken: string, wishId: string) {
  return apiClient<null>(`/wishes/${wishId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * copy wish
 */
export function copyWish(accessToken: string, wishId: string, wishlistId: string) {
  return apiClient<Wish>(`/wishes/${wishId}/copy`, {
    method: "POST",
    accessToken,
    body: { wishlist_id: wishlistId },
  });
}

/**
 * upload wish image
 */
export function uploadWishImage(accessToken: string, wishId: string, file: File) {
  const body = new FormData();
  body.append("file", file);

  return apiClient<WishImage>(`/wishes/${wishId}/images`, {
    method: "POST",
    accessToken,
    body,
  });
}

/**
 * delete wish image
 */
export function deleteWishImage(accessToken: string, wishId: string, imageId: string) {
  return apiClient<null>(`/wishes/${wishId}/images/${imageId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * mark wish as fulfilled
 */
export function completeWish(accessToken: string, wishId: string) {
  return apiClient<Wish>(`/wishes/${wishId}/complete`, {
    method: "POST",
    accessToken,
  });
}

/**
 * restore fulfilled wish to active
 */
export function uncompleteWish(accessToken: string, wishId: string) {
  return apiClient<Wish>(`/wishes/${wishId}/complete`, {
    method: "DELETE",
    accessToken,
  });
}
