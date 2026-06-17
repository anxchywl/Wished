import { apiClient } from "@/lib/api";
import type {
  Wish,
  WishCreateInput,
  WishImage,
  WishListResponse,
  WishReorderInput,
  WishUpdateInput,
} from "@/features/wishes/types";

/**
 * list wishes
 */
export function listWishes(accessToken: string, wishlistId: string) {
  return apiClient<WishListResponse>(`/wishlists/${wishlistId}/wishes`, { accessToken });
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
