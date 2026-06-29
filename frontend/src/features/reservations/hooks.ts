// reservations queries and mutations
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type WishReservationStatusResponse,
  type BookedWishListResponse,
  cancelReservation,
  createReservation,
  getBookedWishes,
  getReservationStatus,
  removeWishReservation,
  reorderBookedWishes,
  reorderFulfilledWishes,
} from "@/features/reservations/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import { useAuthStore } from "@/stores/auth-store";

export const reservationQueryKeys = {
  status: (wishId: string) => ["reservations", "status", wishId] as const,
};

export const bookedWishesQueryKey = ["reservations", "booked"] as const;

/**
 * load reservation status for a wish
 *
 * Polls every 30 s so viewers of a shared wishlist see others' bookings update
 * within a reasonable window. Mutations (create/cancel reservation) update the
 * cache immediately via setQueryData so the reserver sees instant feedback.
 */
export function useReservationStatusQuery(wishId: string, shareToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const queryKey = shareToken
    ? ([...reservationQueryKeys.status(wishId), shareToken] as const)
    : reservationQueryKeys.status(wishId);

  return useQuery({
    queryKey,
    queryFn: () => getReservationStatus(accessToken ?? "", wishId, shareToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && wishId),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

/**
 * list wishes booked by the current user
 */
export function useBookedWishesQuery() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: bookedWishesQueryKey,
    queryFn: async () => {
      const response = await getBookedWishes(accessToken ?? "");
      const cached = queryClient.getQueryData<BookedWishListResponse>(bookedWishesQueryKey);
      if (!cached) return response;

      const cachedImages = new Map(
        [...cached.items, ...(cached.fulfilled_items ?? [])].flatMap((item) =>
          item.images.map((image) => [image.id, image] as const),
        ),
      );
      const preserveImages = <T extends { images: typeof response.items[number]["images"] }>(item: T): T => ({
        ...item,
        images: item.images.map((image) => {
          const cachedImage = cachedImages.get(image.id);
          return cachedImage
            ? {
                ...image,
                url: cachedImage.url,
                thumbnail_url: cachedImage.thumbnail_url,
                medium_url: cachedImage.medium_url,
              }
            : image;
        }),
      });
      return {
        items: response.items.map(preserveImages),
        fulfilled_items: (response.fulfilled_items ?? []).map(preserveImages),
      };
    },
    enabled: Boolean(authStatus === "authenticated" && accessToken),
    staleTime: 15_000,
    refetchInterval: 15_000,
    refetchOnMount: "always",
  });
}

/**
 * reorder booked wishes mutation
 */
export function useReorderBookedWishesMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationKey: ["reorderBookedWishes"],
    mutationFn: (input: { wish_ids: string[] }) => reorderBookedWishes(accessToken ?? "", input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: bookedWishesQueryKey });
      const previousBookedWishes = queryClient.getQueryData<BookedWishListResponse>(bookedWishesQueryKey);
      queryClient.setQueryData<BookedWishListResponse>(bookedWishesQueryKey, (current) => ({
        items: reorderBookedWishItems(current?.items ?? [], input.wish_ids),
        fulfilled_items: current?.fulfilled_items ?? [],
      }));
      return { previousBookedWishes };
    },
    onError: (_error, _input, context) => {
      if (context?.previousBookedWishes) {
        queryClient.setQueryData(bookedWishesQueryKey, context.previousBookedWishes);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(bookedWishesQueryKey, data);
    },
  });
}

/**
 * reorder fulfilled wishes mutation
 */
export function useReorderFulfilledWishesMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationKey: ["reorderFulfilledWishes"],
    mutationFn: (input: { fulfilled_ids: string[] }) => reorderFulfilledWishes(accessToken ?? "", input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: bookedWishesQueryKey });
      const previousBookedWishes = queryClient.getQueryData<BookedWishListResponse>(bookedWishesQueryKey);
      queryClient.setQueryData<BookedWishListResponse>(bookedWishesQueryKey, (current) => ({
        items: current?.items ?? [],
        fulfilled_items: reorderFulfilledWishItems(
          current?.fulfilled_items ?? [],
          input.fulfilled_ids,
        ),
      }));
      return { previousBookedWishes };
    },
    onError: (_error, _input, context) => {
      if (context?.previousBookedWishes) {
        queryClient.setQueryData(bookedWishesQueryKey, context.previousBookedWishes);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(bookedWishesQueryKey, data);
    },
  });
}

/**
 * reorder cached booked wishes
 */
export function reorderBookedWishItems(
  items: BookedWishListResponse["items"],
  wishIds: string[],
) {
  const byId = new Map(items.map((item) => [item.wish_id, item]));
  const next = wishIds
    .map((id, position) => {
      const item = byId.get(id);
      return item ? { ...item, position } : null;
    })
    .filter((item): item is BookedWishListResponse["items"][number] => Boolean(item));
  return next.length === items.length ? next : items;
}

/**
 * reorder cached fulfilled wishes
 */
export function reorderFulfilledWishItems(
  items: BookedWishListResponse["fulfilled_items"],
  fulfilledIds: string[],
) {
  const byId = new Map(items.map((item) => [item.fulfilled_id, item]));
  const next = fulfilledIds
    .map((id, position) => {
      const item = byId.get(id);
      return item ? { ...item, position } : null;
    })
    .filter((item): item is BookedWishListResponse["fulfilled_items"][number] => Boolean(item));
  return next.length === items.length ? next : items;
}

/**
 * create reservation mutation
 */
export function useCreateReservationMutation(wishlistId: string, shareToken?: string | null) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (wishId: string) => createReservation(accessToken ?? "", wishId, shareToken),
    onSuccess: (reservation, wishId) => {
      const statusKey = shareToken
        ? ([...reservationQueryKeys.status(wishId), shareToken] as const)
        : reservationQueryKeys.status(wishId);
      queryClient.setQueryData<WishReservationStatusResponse>(
        statusKey,
        {
          wish_id: wishId,
          is_reserved: true,
          is_mine: true,
          reservation_id: reservation.id,
          owner_booking_visibility: null,
          owner_group_gift_visibility: null,
          reserver_display_name: null,
          group_gift_organizer_display_name: null,
          has_active_group_gift: false,
        },
      );
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
    },
  });
}

/**
 * wish owner removes any reservation on their wish
 */
export function useRemoveWishReservationMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (wishId: string) => removeWishReservation(accessToken ?? "", wishId),
    onSuccess: (_data, wishId) => {
      queryClient.setQueryData<WishReservationStatusResponse>(
        reservationQueryKeys.status(wishId),
        (current) => current
          ? {
              ...current,
              is_reserved: false,
              is_mine: false,
              reservation_id: null,
              reserver_display_name: null,
            }
          : current,
      );
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
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
      queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
    },
  });
}
