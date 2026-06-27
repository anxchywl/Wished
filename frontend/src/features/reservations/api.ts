// reservations api client
import { apiClient } from "@/lib/api";
import type { WishImage } from "@/features/wishes/types";

export type ReservationResponse = {
  id: string;
  wish_id: string;
  reserver_user_id: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type WishReservationStatusResponse = {
  wish_id: string;
  is_reserved: boolean;
  is_mine: boolean;
  reservation_id: string | null;
  owner_booking_visibility: "hide" | "anonymous" | "names" | null;
  owner_group_gift_visibility: "hide" | "anonymous" | "names" | null;
  reserver_display_name: string | null;
  group_gift_organizer_display_name: string | null;
  has_active_group_gift: boolean;
};

export type BookedWishContributorSummary = {
  first_name: string | null;
  username: string | null;
  amount: string | null;
  status: string;
};

export type BookedWishGroupGiftDetail = {
  group_gift_id: string;
  status: string;
  organizer_first_name: string | null;
  organizer_username: string | null;
  collected_amount: string;
  total_amount: string | null;
  percent_complete: number;
  participant_count: number;
  cancel_approval_count: number;
  unbook_approval_count: number;
  my_cancel_approval: boolean;
  my_unbook_approval: boolean;
  contributors: BookedWishContributorSummary[];
};

export type BookedWishItem = {
  reservation_id: string | null;
  wish_id: string;
  wish_title: string;
  wish_description: string | null;
  wish_url: string | null;
  wish_price: string | null;
  wish_currency: string | null;
  wish_status: string;
  wishlist_id: string;
  wishlist_title: string;
  owner_first_name: string | null;
  owner_username: string | null;
  owner_photo_url: string | null;
  images: WishImage[];
  reserved_at: string;
  is_group_gift: boolean;
  group_gift: BookedWishGroupGiftDetail | null;
  is_fulfilled_history?: boolean;
};

export type FulfilledWishItem = {
  fulfilled_id: string;
  wish_id: string;
  wish_title: string;
  wish_description: string | null;
  wish_url: string | null;
  wish_price: string | null;
  wish_currency: string | null;
  wish_status: string;
  wishlist_id: string;
  wishlist_title: string;
  owner_first_name: string | null;
  owner_username: string | null;
  owner_photo_url: string | null;
  images: WishImage[];
  fulfilled_at: string;
  source: "booking" | "group_gift";
  organizer_first_name: string | null;
  organizer_username: string | null;
  contributor_count: number | null;
  user_contribution_amount: string | null;
  total_collected_amount: string | null;
  group_gift_id: string | null;
};

export type BookedWishListResponse = {
  items: BookedWishItem[];
  fulfilled_items: FulfilledWishItem[];
};

/**
 * create reservation for a wish
 */
export function createReservation(accessToken: string, wishId: string, shareToken?: string | null) {
  const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : "";
  return apiClient<ReservationResponse>(`/wishes/${wishId}/reserve${query}`, {
    method: "POST",
    accessToken,
  });
}

/**
 * cancel own reservation
 */
export function cancelReservation(accessToken: string, reservationId: string) {
  return apiClient<null>(`/reservations/${reservationId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * get viewer-safe reservation status for a wish
 */
export function getReservationStatus(accessToken: string, wishId: string, shareToken?: string | null) {
  const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : "";
  return apiClient<WishReservationStatusResponse>(
    `/wishes/${wishId}/reservation-status${query}`,
    { accessToken },
  );
}

/**
 * wish owner removes any active reservation on their wish
 */
export function removeWishReservation(accessToken: string, wishId: string) {
  return apiClient<null>(`/wishes/${wishId}/reservation`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * list wishes the current user has actively booked
 */
export function getBookedWishes(accessToken: string) {
  return apiClient<BookedWishListResponse>("/me/booked-wishes", { accessToken });
}
