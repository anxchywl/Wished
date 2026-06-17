export const wishlistQueryKeys = {
  all: (tgUserId: number | null) => ["wishlists", tgUserId] as const,
  detail: (wishlistId: string) => ["wishlists", "detail", wishlistId] as const,
  user: (username: string) => ["wishlists", "user", username] as const,
};

