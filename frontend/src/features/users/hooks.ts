// users queries
import { useQuery } from "@tanstack/react-query";

import { getUserProfile, searchUsers } from "@/features/users/api";
import { useAuthStore } from "@/stores/auth-store";

export const userQueryKeys = {
  all: ["users"] as const,
  search: (query: string) => ["users", "search", query] as const,
  profile: (username: string) => ["users", "profile", username] as const,
};

/**
 * search users
 */
export function useSearchUsersQuery(query: string) {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useQuery({
    queryKey: [...userQueryKeys.search(query), accessToken] as const,
    queryFn: () => searchUsers(accessToken ?? "", query),
    enabled: Boolean(accessToken && query.trim().length > 0),
  });
}

/**
 * load user profile
 */
export function useUserProfileQuery(username: string) {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useQuery({
    queryKey: [...userQueryKeys.profile(username), accessToken] as const,
    queryFn: () => getUserProfile(accessToken ?? "", username),
    enabled: Boolean(accessToken && username),
    staleTime: 30 * 1000,
  });
}
