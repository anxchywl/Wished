// group gifts queries and mutations
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ContributionSummary,
  type GroupGiftCreatePayload,
  type GroupGiftPaymentDetailsPayload,
  type GroupGiftResponse,
  cancelGroupGift,
  createGroupGift,
  getGiftMembers,
  getGroupGift,
  joinGroupGift,
  leaveGroupGift,
  markGroupGiftPurchased,
  organizerRemoveContribution,
  reportTransfer,
  toggleGroupGiftApproval,
  updateGroupGiftPaymentDetails,
} from "@/features/group-gifts/api";
import { bookedWishesQueryKey } from "@/features/reservations/hooks";
import { groupGiftQueryKeys } from "@/features/group-gifts/query-keys";
import { useAuthStore } from "@/stores/auth-store";
import type { WishListResponse } from "@/features/wishes/types";

function clearCancelledGroupGift(
  queryClient: ReturnType<typeof useQueryClient>,
  wishId: string,
) {
  queryClient.setQueriesData({ queryKey: groupGiftQueryKeys.gift(wishId) }, null);
  queryClient.removeQueries({ queryKey: ["group-gifts", "members"] });
  queryClient.setQueriesData<WishListResponse>(
    { queryKey: ["wishes"] },
    (current) => {
      if (!current) return current;
      return {
        items: current.items.map((wish) =>
          wish.id === wishId ? { ...wish, group_gift: null } : wish,
        ),
      };
    },
  );
  queryClient.invalidateQueries({ queryKey: ["wishes"] });
  queryClient.invalidateQueries({ queryKey: ["reservations"] });
  queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
}

export function useGroupGiftQuery(wishId: string, shareToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const queryKey = shareToken
    ? ([...groupGiftQueryKeys.gift(wishId), shareToken] as const)
    : groupGiftQueryKeys.gift(wishId);

  return useQuery({
    queryKey,
    queryFn: () => getGroupGift(accessToken, wishId, shareToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && wishId),
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}

export function useCreateGroupGiftMutation(wishId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (payload: GroupGiftCreatePayload) => createGroupGift(accessToken, wishId, payload),
    onSuccess: (result) => {
      queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), result);
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
    },
  });
}

export function useCancelGroupGiftMutation(wishId: string, groupGiftId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: () => toggleGroupGiftApproval(accessToken, groupGiftId, "cancel"),
    onSuccess: (result) => {
      if (result === null) {
        clearCancelledGroupGift(queryClient, wishId);
      } else {
        queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), result);
        queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
      }
    },
  });
}

export function useToggleGroupGiftApprovalMutation(wishId: string, groupGiftId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (approvalType: "cancel" | "unbook") =>
      toggleGroupGiftApproval(accessToken, groupGiftId, approvalType),
    onMutate: async (approvalType: "cancel" | "unbook") => {
      await queryClient.cancelQueries({ queryKey: groupGiftQueryKeys.gift(wishId) });
      const previous = queryClient.getQueryData<GroupGiftResponse | null>(groupGiftQueryKeys.gift(wishId));
      if (previous) {
        queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), {
          ...previous,
          ...(approvalType === "cancel"
            ? { my_cancel_approval: !previous.my_cancel_approval }
            : { my_unbook_approval: !previous.my_unbook_approval }),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), context.previous);
      }
    },
    onSuccess: (result) => {
      if (result === null) {
        clearCancelledGroupGift(queryClient, wishId);
      } else {
        queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), result);
        queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
      }
    },
  });
}

export function useUpdateGroupGiftPaymentDetailsMutation(wishId: string, groupGiftId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (payload: GroupGiftPaymentDetailsPayload) => (
      updateGroupGiftPaymentDetails(accessToken, groupGiftId, payload)
    ),
    onSuccess: (result) => {
      queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), result);
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
    },
  });
}

export function useMarkGroupGiftPurchasedMutation(wishId: string, groupGiftId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: () => markGroupGiftPurchased(accessToken, groupGiftId),
    onSuccess: (result) => {
      queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), result);
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
      queryClient.invalidateQueries({ queryKey: bookedWishesQueryKey });
    },
  });
}

export function useJoinGroupGiftMutation(wishId: string, groupGiftId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (amount: number) => joinGroupGift(accessToken, groupGiftId, amount),
    onSuccess: (result) => {
      queryClient.setQueryData<GroupGiftResponse | null>(
        groupGiftQueryKeys.gift(wishId),
        (current) => {
          if (!current) return current;
          const nextCollected = current.collection_type === "commit"
            ? String(Math.min(
                Number(current.total_amount ?? Number.MAX_SAFE_INTEGER),
                Number(current.collected_amount) + Number(result.amount),
              ))
            : current.collected_amount;
          const nextRemaining = current.remaining_amount
            ? String(Math.max(0, Number(current.remaining_amount) - Number(result.amount)))
            : current.remaining_amount;
          const nextPercent = current.collection_type === "commit" && current.total_amount
            ? Math.min(100, Math.trunc((Number(nextCollected) / Number(current.total_amount)) * 100))
            : current.percent_complete;
          return {
            ...current,
            collected_amount: nextCollected,
            remaining_amount: nextRemaining,
            percent_complete: nextPercent,
            is_contributor: true,
            my_contribution: result,
            contributor_count: current.contributor_count + 1,
          };
        },
      );
      queryClient.invalidateQueries({ queryKey: ["group-gifts", "members"] });
      queryClient.invalidateQueries({ queryKey: groupGiftQueryKeys.gift(wishId) });
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
    },
  });
}

export function useReportTransferMutation(wishId: string, contributionId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: () => reportTransfer(accessToken, contributionId),
    onSuccess: (result) => {
      queryClient.setQueryData<GroupGiftResponse | null>(
        groupGiftQueryKeys.gift(wishId),
        (current) => {
          if (!current) return current;
          return { ...current, my_contribution: result };
        },
      );
    },
  });
}

export function useLeaveGroupGiftMutation(wishId: string, contributionId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: () => leaveGroupGift(accessToken, contributionId),
    onSuccess: () => {
      queryClient.setQueryData<GroupGiftResponse | null>(
        groupGiftQueryKeys.gift(wishId),
        (current) => {
          if (!current) return current;
          return {
            ...current,
            my_contribution: null,
            is_contributor: false,
            contributor_count: Math.max(0, current.contributor_count - 1),
          };
        },
      );
      queryClient.invalidateQueries({ queryKey: ["group-gifts", "members"] });
      queryClient.invalidateQueries({ queryKey: groupGiftQueryKeys.gift(wishId) });
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
    },
  });
}

export function useOrganizerRemoveContributionMutation(wishId: string, groupGiftId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);

  return useMutation({
    mutationFn: (contributionId: string) => (
      organizerRemoveContribution(accessToken, groupGiftId, contributionId)
    ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["group-gifts", "members"] });
      queryClient.invalidateQueries({ queryKey: groupGiftQueryKeys.gift(wishId) });
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
    },
  });
}

export function useGiftMembersQuery(groupGiftId: string | null | undefined, enabled = true) {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useQuery({
    queryKey: groupGiftQueryKeys.members(groupGiftId ?? ""),
    queryFn: () => getGiftMembers(accessToken, groupGiftId!),
    enabled: Boolean(groupGiftId && enabled),
  });
}
