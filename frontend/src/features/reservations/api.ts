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
  reserver_display_name: string | null;
};

export type BookedWishItem = {
  reservation_id: string;
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
};

export type BookedWishListResponse = {
  items: BookedWishItem[];
};

/**
 * create reservation for a wish
 */
export function createReservation(accessToken: string, wishId: string) {
  return apiClient<ReservationResponse>(`/wishes/${wishId}/reserve`, {
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
export function getReservationStatus(accessToken: string, wishId: string) {
  return apiClient<WishReservationStatusResponse>(
    `/wishes/${wishId}/reservation-status`,
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
