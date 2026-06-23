// users queries
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { followUser, followUserById, getUserProfile, getUserProfileById, getUserWishlistsById, listFollowing, unfollowUser, unfollowUserById, type UserProfileResponse } from "@/features/users/api";
import { useAuthStore, useSyncTgUserId } from "@/stores/auth-store";

export const userQueryKeys = {
  all: ["users"] as const,
  profile: (username: string) => ["users", "profile", username] as const,
  profileById: (userId: string) => ["users", "profile-id", userId] as const,
  wishlistsById: (userId: string) => ["users", "wishlists-id", userId] as const,
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
 * load user profile by internal UUID
 */
export function useUserProfileByIdQuery(userId: string | null, profileToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);

  return useQuery({
    queryKey: [...userQueryKeys.profileById(userId ?? ""), accessToken, profileToken] as const,
    queryFn: () => getUserProfileById(accessToken ?? "", userId ?? "", profileToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && userId),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * load user wishlists by internal UUID
 */
export function useUserWishlistsByIdQuery(userId: string | null, profileToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);

  return useQuery({
    queryKey: [...userQueryKeys.wishlistsById(userId ?? ""), accessToken, profileToken] as const,
    queryFn: () => getUserWishlistsById(accessToken ?? "", userId ?? "", profileToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && userId),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * toggle follow state by internal UUID
 */
export function useFollowByIdMutation(userId: string, profileToken?: string | null) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useSyncTgUserId();

  return useMutation({
    mutationFn: (nextFollowing: boolean) =>
      nextFollowing
        ? followUserById(accessToken ?? "", userId, profileToken)
        : unfollowUserById(accessToken ?? "", userId),
    onMutate: async (nextFollowing) => {
      await queryClient.cancelQueries({ queryKey: userQueryKeys.profileById(userId) });
      const previous = queryClient.getQueriesData<UserProfileResponse>({ queryKey: userQueryKeys.profileById(userId) });
      queryClient.setQueriesData<UserProfileResponse>({ queryKey: userQueryKeys.profileById(userId) }, (current) =>
        current ? { ...current, is_following: nextFollowing } : current,
      );
      return { previous };
    },
    onError: (_error, _nextFollowing, context) => {
      context?.previous.forEach(([key, value]) => queryClient.setQueryData(key, value));
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.profileById(userId) });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.following(tgUserId) });
    },
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
