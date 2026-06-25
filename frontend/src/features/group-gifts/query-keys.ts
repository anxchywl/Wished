export const groupGiftQueryKeys = {
  gift: (wishId: string) => ["group-gifts", "gift", wishId] as const,
  members: (groupGiftId: string) => ["group-gifts", "members", groupGiftId] as const,
};
