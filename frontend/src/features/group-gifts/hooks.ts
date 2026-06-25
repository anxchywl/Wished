// group gifts queries and mutations
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ContributionSummary,
  type GroupGiftCreatePayload,
  type GroupGiftResponse,
  cancelGroupGift,
  createGroupGift,
  getGiftMembers,
  getGroupGift,
  joinGroupGift,
  leaveGroupGift,
  reportTransfer,
} from "@/features/group-gifts/api";
import { groupGiftQueryKeys } from "@/features/group-gifts/query-keys";
import { useAuthStore } from "@/stores/auth-store";

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
    staleTime: 30_000,
    refetchInterval: 30_000,
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
    mutationFn: () => cancelGroupGift(accessToken, groupGiftId),
    onSuccess: () => {
      queryClient.setQueryData(groupGiftQueryKeys.gift(wishId), null);
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
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
          return {
            ...current,
            is_contributor: true,
            my_contribution: result,
            contributor_count: current.contributor_count + 1,
          };
        },
      );
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
      queryClient.invalidateQueries({ queryKey: groupGiftQueryKeys.gift(wishId) });
    },
  });
}

export function useGiftMembersQuery(groupGiftId: string | null | undefined) {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useQuery({
    queryKey: groupGiftQueryKeys.members(groupGiftId ?? ""),
    queryFn: () => getGiftMembers(accessToken, groupGiftId!),
    enabled: !!groupGiftId,
  });
}
