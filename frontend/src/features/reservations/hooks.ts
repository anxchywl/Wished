// reservations queries and mutations
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelReservation,
  createReservation,
  getReservationStatus,
} from "@/features/reservations/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import { useAuthStore } from "@/stores/auth-store";

export const reservationQueryKeys = {
  status: (wishId: string) => ["reservations", "status", wishId] as const,
};

/**
 * load reservation status for a wish
 */
export function useReservationStatusQuery(wishId: string) {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useQuery({
    queryKey: reservationQueryKeys.status(wishId),
    queryFn: () => getReservationStatus(accessToken ?? "", wishId),
    enabled: Boolean(accessToken && wishId),
    staleTime: 15 * 1000,
  });
}

/**
 * create reservation mutation
 */
export function useCreateReservationMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (wishId: string) => createReservation(accessToken ?? "", wishId),
    onSuccess: (_data, wishId) => {
      queryClient.invalidateQueries({ queryKey: reservationQueryKeys.status(wishId) });
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
    },
  });
}

/**
 * cancel reservation mutation
 */
export function useCancelReservationMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: ({ reservationId, wishId }: { reservationId: string; wishId: string }) =>
      cancelReservation(accessToken ?? "", reservationId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: reservationQueryKeys.status(variables.wishId) });
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
    },
  });
}
