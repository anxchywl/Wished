import { apiClient } from "@/lib/api";
import type {
  Wishlist,
  WishlistCreateInput,
  WishlistListResponse,
  WishlistReorderInput,
  WishlistUpdateInput,
} from "@/features/wishlists/types";

/**
 * list wishlists
 */
export function listWishlists(accessToken: string) {
  return apiClient<WishlistListResponse>("/wishlists", { accessToken });
}

/**
 * get wishlist
 */
export function getWishlist(accessToken: string, wishlistId: string) {
  return apiClient<Wishlist>(`/wishlists/${wishlistId}`, { accessToken });
}

/**
 * list user wishlists
 */
export function listUserWishlists(accessToken: string, username: string, profileToken?: string | null) {
  const normalizedUsername = username.trim().replace(/^@/, "");
  const query = profileToken ? `?profile_token=${encodeURIComponent(profileToken)}` : "";
  return apiClient<WishlistListResponse>(`/users/${encodeURIComponent(normalizedUsername)}/wishlists${query}`, {
    accessToken,
  });
}

/**
 * create wishlist
 */
export function createWishlist(accessToken: string, input: WishlistCreateInput) {
  return apiClient<Wishlist>("/wishlists", {
    method: "POST",
    accessToken,
    body: input,
  });
}

/**
 * update wishlist
 */
export function updateWishlist(
  accessToken: string,
  wishlistId: string,
  input: WishlistUpdateInput,
) {
  return apiClient<Wishlist>(`/wishlists/${wishlistId}`, {
    method: "PATCH",
    accessToken,
    body: input,
  });
}

/**
 * reorder wishlists
 */
export function reorderWishlists(accessToken: string, input: WishlistReorderInput) {
  return apiClient<WishlistListResponse>("/wishlists/reorder", {
    method: "PATCH",
    accessToken,
    body: input,
  });
}

/**
 * delete wishlist
 */
export function deleteWishlist(accessToken: string, wishlistId: string) {
  return apiClient<null>(`/wishlists/${wishlistId}`, {
    method: "DELETE",
    accessToken,
  });
}
