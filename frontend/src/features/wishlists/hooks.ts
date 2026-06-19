"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createWishlist,
  deleteWishlist,
  getWishlist,
  listWishlists,
  listUserWishlists,
  reorderWishlists,
  updateWishlist,
} from "@/features/wishlists/api";
import { wishlistQueryKeys } from "@/features/wishlists/query-keys";
import type {
  WishlistCreateInput,
  WishlistListResponse,
  WishlistReorderInput,
  WishlistUpdateInput,
} from "@/features/wishlists/types";
import { useAuthStore } from "@/stores/auth-store";

/**
 * load wishlists
 */
export function useWishlistsQuery() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);
  const authStatus = useAuthStore((state) => state.authStatus);

  return useQuery({
    queryKey: wishlistQueryKeys.all(tgUserId),
    queryFn: () => listWishlists(accessToken ?? ""),
    enabled: Boolean(authStatus === "authenticated" && accessToken),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * find single wishlist in cached list
 */
export function useWishlistQuery(wishlistId: string) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);
  const authStatus = useAuthStore((state) => state.authStatus);
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: [...wishlistQueryKeys.detail(wishlistId), accessToken] as const,
    queryFn: () => getWishlist(accessToken ?? "", wishlistId),
    enabled: Boolean(authStatus === "authenticated" && accessToken && wishlistId),
    initialData: () =>
      queryClient
        .getQueryData<WishlistListResponse>(wishlistQueryKeys.all(tgUserId))
        ?.items.find((wishlist) => wishlist.id === wishlistId),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * load user wishlists
 */
export function useUserWishlistsQuery(username: string, profileToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);

  return useQuery({
    queryKey: [...wishlistQueryKeys.user(username), accessToken, profileToken] as const,
    queryFn: () => listUserWishlists(accessToken ?? "", username, profileToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && username),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * create wishlist mutation
 */
export function useCreateWishlistMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: (input: WishlistCreateInput) => createWishlist(accessToken ?? "", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.all(tgUserId) }),
  });
}

/**
 * update wishlist mutation
 */
export function useUpdateWishlistMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: WishlistUpdateInput }) =>
      updateWishlist(accessToken ?? "", id, input),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
      queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.detail(variables.id) });
    },
  });
}

/**
 * reorder wishlist mutation
 */
export function useReorderWishlistsMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationKey: ["reorderWishlists"],
    mutationFn: (input: WishlistReorderInput) => reorderWishlists(accessToken ?? "", input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
      const previousWishlists = queryClient.getQueryData<WishlistListResponse>(wishlistQueryKeys.all(tgUserId));
      queryClient.setQueryData<WishlistListResponse>(wishlistQueryKeys.all(tgUserId), (current) => ({
        items: reorderWishlistItems(current?.items ?? [], input.wishlist_ids),
      }));
      return { previousWishlists };
    },
    onError: (_error, _input, context) => {
      if (context?.previousWishlists) {
        queryClient.setQueryData(wishlistQueryKeys.all(tgUserId), context.previousWishlists);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(wishlistQueryKeys.all(tgUserId), data);
    },
  });
}

/**
 * reorder cached wishlists
 */
export function reorderWishlistItems(items: WishlistListResponse["items"], wishlistIds: string[]) {
  const byId = new Map(items.map((wishlist) => [wishlist.id, wishlist]));
  const next = wishlistIds
    .map((id, position) => {
      const wishlist = byId.get(id);
      return wishlist ? { ...wishlist, position } : null;
    })
    .filter((wishlist): wishlist is WishlistListResponse["items"][number] => Boolean(wishlist));
  return next.length === items.length ? next : items;
}

/**
 * delete wishlist mutation
 */
export function useDeleteWishlistMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: (id: string) => deleteWishlist(accessToken ?? "", id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
      const previousWishlists = queryClient.getQueryData<WishlistListResponse>(wishlistQueryKeys.all(tgUserId));
      queryClient.setQueryData<WishlistListResponse>(wishlistQueryKeys.all(tgUserId), (current) => ({
        items: (current?.items ?? []).filter((item) => item.id !== id),
      }));
      return { previousWishlists };
    },
    onError: (_error, _id, context) => {
      if (context?.previousWishlists) {
        queryClient.setQueryData(wishlistQueryKeys.all(tgUserId), context.previousWishlists);
      }
    },
    onSuccess: (_data, id) => {
      // remove cached wishes for the deleted wishlist
      queryClient.removeQueries({ queryKey: ["wishes", id] });
    },
  });
}
