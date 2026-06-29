// users queries
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  followUser,
  followUserById,
  getUserProfile,
  getUserProfileById,
  getUserProfileByPublicUsername,
  getUserWishlistsById,
  listFollowing,
  reorderFollowing,
  unfollowUser,
  unfollowUserById,
  type FollowedUserListResponse,
  type UserProfileResponse,
} from "@/features/users/api";
import { useAuthStore, useSyncTgUserId } from "@/stores/auth-store";

export const userQueryKeys = {
  all: ["users"] as const,
  profile: (username: string) => ["users", "profile", username] as const,
  profileByPublicUsername: (publicUsername: string) => ["users", "profile-public", publicUsername] as const,
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

  const queryKey = profileToken
    ? ([...userQueryKeys.profile(username), profileToken] as const)
    : userQueryKeys.profile(username);

  return useQuery({
    queryKey,
    queryFn: () => getUserProfile(accessToken ?? "", username, profileToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && username),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * load user profile by public Wished username
 */
export function useUserProfileByPublicUsernameQuery(
  publicUsername: string | null,
  profileToken?: string | null,
) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const normalizedUsername = publicUsername?.trim().replace(/^@/, "").toLowerCase() ?? "";

  const queryKey = profileToken
    ? ([...userQueryKeys.profileByPublicUsername(normalizedUsername), profileToken] as const)
    : userQueryKeys.profileByPublicUsername(normalizedUsername);

  return useQuery({
    queryKey,
    queryFn: () => getUserProfileByPublicUsername(accessToken ?? "", normalizedUsername, profileToken),
    enabled: Boolean(authStatus === "authenticated" && accessToken && normalizedUsername),
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
 * reorder followed users mutation
 */
export function useReorderFollowingMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useSyncTgUserId();

  return useMutation({
    mutationKey: ["reorderFollowing"],
    mutationFn: (input: { user_ids: string[] }) => reorderFollowing(accessToken ?? "", input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: userQueryKeys.following(tgUserId) });
      const previousFollowing = queryClient.getQueryData<FollowedUserListResponse>(
        userQueryKeys.following(tgUserId),
      );
      queryClient.setQueryData<FollowedUserListResponse>(userQueryKeys.following(tgUserId), (current) => ({
        items: reorderFollowedUserItems(current?.items ?? [], input.user_ids),
      }));
      return { previousFollowing };
    },
    onError: (_error, _input, context) => {
      if (context?.previousFollowing) {
        queryClient.setQueryData(userQueryKeys.following(tgUserId), context.previousFollowing);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(userQueryKeys.following(tgUserId), data);
    },
  });
}

/**
 * reorder cached followed users
 */
export function reorderFollowedUserItems(
  items: FollowedUserListResponse["items"],
  userIds: string[],
) {
  const byId = new Map(items.map((user) => [user.user_id, user]));
  const next = userIds
    .map((id, position) => {
      const user = byId.get(id);
      return user ? { ...user, position } : null;
    })
    .filter((user): user is FollowedUserListResponse["items"][number] => Boolean(user));
  return next.length === items.length ? next : items;
}

/**
 * load user profile by internal UUID
 */
export function useUserProfileByIdQuery(userId: string | null, profileToken?: string | null) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);

  const profileByIdKey = profileToken
    ? ([...userQueryKeys.profileById(userId ?? ""), profileToken] as const)
    : userQueryKeys.profileById(userId ?? "");

  return useQuery({
    queryKey: profileByIdKey,
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

  const wishlistsByIdKey = profileToken
    ? ([...userQueryKeys.wishlistsById(userId ?? ""), profileToken] as const)
    : userQueryKeys.wishlistsById(userId ?? "");

  return useQuery({
    queryKey: wishlistsByIdKey,
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
      const baseKey = userQueryKeys.profileById(userId);
      await queryClient.cancelQueries({ queryKey: baseKey });
      const previous = queryClient.getQueriesData<UserProfileResponse>({ queryKey: baseKey });
      queryClient.setQueriesData<UserProfileResponse>({ queryKey: baseKey }, (current) =>
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
      const baseKey = userQueryKeys.profile(username);
      await queryClient.cancelQueries({ queryKey: baseKey });
      const previous = queryClient.getQueriesData<UserProfileResponse>({ queryKey: baseKey });
      queryClient.setQueriesData<UserProfileResponse>({ queryKey: baseKey }, (current) =>
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
