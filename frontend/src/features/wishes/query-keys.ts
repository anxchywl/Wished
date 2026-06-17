export const wishQueryKeys = {
  list: (wishlistId: string) => ["wishes", wishlistId] as const,
};
