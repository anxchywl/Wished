// reservations api client
import { apiClient } from "@/lib/api";

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
