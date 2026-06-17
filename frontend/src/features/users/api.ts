// users api client
import { apiClient } from "@/lib/api";

export type UserSearchResponse = {
  id: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  birthday?: string | null;
};

export type UserProfileResponse = UserSearchResponse & {};

/**
 * search users by username
 */
export function searchUsers(accessToken: string, query: string) {
  return apiClient<UserSearchResponse[]>(`/users/search?q=${encodeURIComponent(query)}`, {
    accessToken,
  });
}

/**
 * get user profile
 */
export function getUserProfile(accessToken: string, username: string) {
  const normalizedUsername = username.trim().replace(/^@/, "");
  return apiClient<UserProfileResponse>(`/users/${encodeURIComponent(normalizedUsername)}`, {
    accessToken,
  });
}
