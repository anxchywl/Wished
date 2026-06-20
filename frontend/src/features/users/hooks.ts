// users queries
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { followUser, getUserProfile, listFollowing, unfollowUser, type UserProfileResponse } from "@/features/users/api";
import { useAuthStore, useSyncTgUserId } from "@/stores/auth-store";

export const userQueryKeys = {
  all: ["users"] as const,
  profile: (username: string) => ["users", "profile", username] as const,
  following: (tgUserId: number | null) => ["users", "following", tgUserId] as const,
};

/**
 * load user profile
 */
export function useUserProfileQuery(username: string, profileToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);

  return useQuery({
    queryKey: [...userQueryKeys.profile(username), accessToken, profileToken] as const,
    queryFn: () => getUserProfile(accessToken ?? "", username, profileToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && username),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * load followed users
 */
export function useFollowingQuery() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const tgUserId = useSyncTgUserId();

  return useQuery({
    queryKey: userQueryKeys.following(tgUserId),
    queryFn: () => listFollowing(accessToken ?? ""),
    enabled: Boolean(authStatus === "authenticated" && accessToken),
    staleTime: 3 * 60 * 1000,
  });
}

/**
 * toggle follow state
 */
export function useFollowMutation(username: string, profileToken?: string | null) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useSyncTgUserId();

  return useMutation({
    mutationFn: (nextFollowing: boolean) =>
      nextFollowing
        ? followUser(accessToken ?? "", username, profileToken)
        : unfollowUser(accessToken ?? "", username),
    onMutate: async (nextFollowing) => {
      await queryClient.cancelQueries({ queryKey: userQueryKeys.profile(username) });
      const previous = queryClient.getQueriesData<UserProfileResponse>({ queryKey: userQueryKeys.profile(username) });
      queryClient.setQueriesData<UserProfileResponse>({ queryKey: userQueryKeys.profile(username) }, (current) =>
        current ? { ...current, is_following: nextFollowing } : current,
      );
      return { previous };
    },
    onError: (_error, _nextFollowing, context) => {
      context?.previous.forEach(([key, value]) => queryClient.setQueryData(key, value));
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.profile(username) });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.following(tgUserId) });
    },
  });
}
