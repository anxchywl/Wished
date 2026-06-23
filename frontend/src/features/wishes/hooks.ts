"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  completeWish,
  createWish,
  copyWish,
  deleteWish,
  deleteWishImage,
  fetchLinkPreview,
  importProductUrl,
  listWishes,
  reorderWishes,
  uncompleteWish,
  updateWish,
  uploadWishImage,
} from "@/features/wishes/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import type {
  LinkPreviewRequest,
  LinkPreviewResult,
  ProductImportPayload,
  ProductImportResult,
  Wish,
  WishCreateInput,
  WishListResponse,
  WishReorderInput,
  WishUpdateInput,
} from "@/features/wishes/types";
import { wishlistQueryKeys } from "@/features/wishlists/query-keys";
import {
  bookedWishesQueryKey,
  reservationQueryKeys,
} from "@/features/reservations/hooks";
import { useAuthStore } from "@/stores/auth-store";

/**
 * import product data from a marketplace URL
 */
export function useImportProductUrlMutation() {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation<ProductImportResult, Error, ProductImportPayload>({
    mutationFn: (payload: ProductImportPayload) => importProductUrl(accessToken ?? "", payload),
  });
}

/**
 * fetch product metadata from a URL via server-side extraction
 */
export function useLinkPreviewMutation() {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation<LinkPreviewResult, Error, LinkPreviewRequest>({
    mutationFn: (payload: LinkPreviewRequest) => fetchLinkPreview(accessToken ?? "", payload),
  });
}

/**
 * load wishes
 */
export function useWishesQuery(wishlistId: string, enabled = true, shareToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const queryClient = useQueryClient();
  const queryKey = shareToken
    ? ([...wishQueryKeys.list(wishlistId), shareToken] as const)
    : wishQueryKeys.list(wishlistId);

  return useQuery({
    queryKey,
    queryFn: async () => {
      const response = await listWishes(accessToken ?? "", wishlistId, shareToken);
      const cached = queryClient.getQueryData<WishListResponse>(queryKey);
      return preserveWishImageUrls(response, cached);
    },
    enabled: Boolean(enabled && authStatus === "authenticated" && accessToken && wishlistId),
    staleTime: 30 * 1000,
    refetchInterval: 1_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: "always",
  });
}

function preserveWishImageUrls(
  response: WishListResponse,
  cached: WishListResponse | undefined,
): WishListResponse {
  if (!cached) return response;

  const cachedImages = new Map(
    cached.items.flatMap((wish) => wish.images.map((image) => [image.id, image] as const)),
  );

  return {
    items: response.items.map((wish) => ({
      ...wish,
      images: wish.images.map((image) => {
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
    })),
  };
}

/**
 * create wish mutation
 */
export function useCreateWishMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: (input: WishCreateInput) => createWish(accessToken ?? "", wishlistId, input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: wishQueryKeys.list(wishlistId) });

      const previousWishes = queryClient.getQueryData<WishListResponse>(wishQueryKeys.list(wishlistId));
      const timestamp = new Date().toISOString();
      const optimisticWish: Wish = {
        id: `optimistic-${timestamp}`,
        wishlist_id: wishlistId,
        title: input.title,
        description: input.description ?? null,
        url: input.url ?? null,
        priority: input.priority ?? 3,
        position: -1,
        price: input.price ?? null,
        currency: input.currency ?? null,
        status: "active",
        original_product_url: input.original_product_url ?? null,
        source_marketplace: input.source_marketplace ?? null,
        images: [],
        created_at: timestamp,
        updated_at: timestamp,
      };

      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
        items: [optimisticWish, ...(current?.items ?? [])],
      }));

      return { optimisticWishId: optimisticWish.id, previousWishes };
    },
    onError: (_error, _input, context) => {
      if (context?.previousWishes) {
        queryClient.setQueryData(wishQueryKeys.list(wishlistId), context.previousWishes);
      }
    },
    onSuccess: async (wish, _input, context) => {
      await queryClient.cancelQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
        items: [
          wish,
          ...(current?.items.filter((item) => item.id !== wish.id && item.id !== context?.optimisticWishId) ?? []),
        ],
      }));
      // only invalidate wishlist metadata (e.g. count), not the wishes list itself
      queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
    },
  });
}

/**
 * reorder wish mutation
 */
export function useReorderWishesMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationKey: ["reorderWishes", wishlistId],
    mutationFn: (input: WishReorderInput) => reorderWishes(accessToken ?? "", wishlistId, input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      const previousWishes = queryClient.getQueryData<WishListResponse>(wishQueryKeys.list(wishlistId));
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
        items: reorderWishItems(current?.items ?? [], input.wish_ids),
      }));
      return { previousWishes };
    },
    onError: (_error, _input, context) => {
      if (context?.previousWishes) {
        queryClient.setQueryData(wishQueryKeys.list(wishlistId), context.previousWishes);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(wishQueryKeys.list(wishlistId), data);
    },
  });
}

/**
 * reorder cached wishes
 */
export function reorderWishItems(items: WishListResponse["items"], wishIds: string[]) {
  const byId = new Map(items.map((wish) => [wish.id, wish]));
  const next = wishIds
    .map((id, position) => {
      const wish = byId.get(id);
      return wish ? { ...wish, position } : null;
    })
    .filter((wish): wish is WishListResponse["items"][number] => Boolean(wish));
  return next.length === items.length ? next : items;
}

/**
 * update wish mutation
 */
export function useUpdateWishMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: WishUpdateInput }) =>
      updateWish(accessToken ?? "", id, input),
    onSuccess: (data, variables) => {
      // Patch only the non-image fields so concurrent image uploads don't lose their
      // optimistic preview when this refetch returns with images=[] (upload still in-flight).
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => {
        if (!current) return current;
        return {
          items: current.items.map((item) =>
            item.id === variables.id ? { ...data, images: item.images } : item
          ),
        };
      });
      if (variables.input.wishlist_id && variables.input.wishlist_id !== wishlistId) {
        queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(variables.input.wishlist_id) });
        queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
      }
    },
  });
}

/**
 * delete wish mutation
 */
export function useDeleteWishMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: (id: string) => deleteWish(accessToken ?? "", id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      const previousWishes = queryClient.getQueryData<WishListResponse>(wishQueryKeys.list(wishlistId));
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
        items: (current?.items ?? []).filter((item) => item.id !== id),
      }));
      return { previousWishes };
    },
    onError: (_error, _id, context) => {
      if (context?.previousWishes) {
        queryClient.setQueryData(wishQueryKeys.list(wishlistId), context.previousWishes);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
    },
  });
}

/**
 * copy wish mutation
 */
export function useCopyWishMutation(sourceWishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);

  return useMutation({
    mutationFn: ({ wishId, wishlistId }: { wishId: string; wishlistId: string }) =>
      copyWish(accessToken ?? "", wishId, wishlistId),
    onSuccess: (_wish, variables) => {
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(variables.wishlistId) });
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(sourceWishlistId) });
      queryClient.invalidateQueries({ queryKey: wishlistQueryKeys.all(tgUserId) });
    },
  });
}

/**
 * upload wish image mutation
 */
export function useUploadWishImageMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: ({ wishId, file }: { wishId: string; file: File; previewUrl?: string }) =>
      uploadWishImage(accessToken ?? "", wishId, file),
    onMutate: async ({ wishId, previewUrl }) => {
      await queryClient.cancelQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      const previousWishes = queryClient.getQueryData<WishListResponse>(wishQueryKeys.list(wishlistId));
      const timestamp = new Date().toISOString();
      if (previewUrl) {
        queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
          items: (current?.items ?? []).map((item) =>
            item.id === wishId
              ? {
                  ...item,
                  images: [
                    {
                      id: `preview-${timestamp}`,
                      wish_id: wishId,
                      url: previewUrl,
                      thumbnail_url: previewUrl,
                      medium_url: previewUrl,
                      file_name: "preview",
                      content_type: "image/jpeg",
                      size_bytes: 0,
                      status: "ready",
                      created_at: timestamp,
                    },
                    ...item.images.filter((image) => !image.id.startsWith("preview-")),
                  ],
                }
              : item
          ),
        }));
      }
      return { previousWishes, previewUrl, wishId };
    },
    onError: (_error, _vars, context) => {
      if (context?.previousWishes) {
        queryClient.setQueryData(wishQueryKeys.list(wishlistId), context.previousWishes);
      }
    },
    onSuccess: async (image, variables, context) => {
      const displayedImage = context?.previewUrl
        ? {
            ...image,
            url: context.previewUrl,
            thumbnail_url: context.previewUrl,
            medium_url: context.previewUrl,
          }
        : image;
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
        items: (current?.items ?? []).map((item) =>
          item.id === variables.wishId
            ? {
                ...item,
                images: [
                  displayedImage,
                  ...item.images.filter((currentImage) => currentImage.id !== image.id && !currentImage.id.startsWith("preview-")),
                ],
              }
            : item
        ),
      }));
      await queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
    },
  });
}

/**
 * complete wish mutation (mark as fulfilled)
 */
export function useCompleteWishMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (wishId: string) => completeWish(accessToken ?? "", wishId),
    onSuccess: (data) => {
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => {
        if (!current) return current;
        return { items: current.items.map((item) => (item.id === data.id ? data : item)) };
      });
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      queryClient.invalidateQueries({ queryKey: reservationQueryKeys.status(data.id) });
      queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
    },
  });
}

/**
 * uncomplete wish mutation (restore to active)
 */
export function useUncompleteWishMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (wishId: string) => uncompleteWish(accessToken ?? "", wishId),
    onSuccess: (data) => {
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => {
        if (!current) return current;
        return { items: current.items.map((item) => (item.id === data.id ? data : item)) };
      });
      queryClient.invalidateQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      queryClient.invalidateQueries({ queryKey: reservationQueryKeys.status(data.id) });
      queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
    },
  });
}

/**
 * delete wish image mutation
 */
export function useDeleteWishImageMutation(wishlistId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: ({ wishId, imageId }: { wishId: string; imageId: string }) =>
      deleteWishImage(accessToken ?? "", wishId, imageId),
    onMutate: async ({ wishId, imageId }) => {
      await queryClient.cancelQueries({ queryKey: wishQueryKeys.list(wishlistId) });
      const previousWishes = queryClient.getQueryData<WishListResponse>(wishQueryKeys.list(wishlistId));
      queryClient.setQueryData<WishListResponse>(wishQueryKeys.list(wishlistId), (current) => ({
        items: (current?.items ?? []).map((item) =>
          item.id === wishId
            ? { ...item, images: item.images.filter((img) => img.id !== imageId) }
            : item
        ),
      }));
      return { previousWishes };
    },
    onError: (error, _vars, context) => {
      console.error("DELETE IMAGE ERROR", error);
      if (context?.previousWishes) {
        queryClient.setQueryData(wishQueryKeys.list(wishlistId), context.previousWishes);
      }
    },
  });
}
