// users api client
import { apiClient } from "@/lib/api";

export type UserProfileResponse = {
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  birthday?: string | null;
  is_self: boolean;
  is_following: boolean;
};

export type FollowedUserResponse = UserProfileResponse & {
  followed_at: string;
};

export type FollowedUserListResponse = {
  items: FollowedUserResponse[];
};

/**
 * get user profile
 */
export function getUserProfile(accessToken: string, username: string, profileToken?: string | null) {
  const normalizedUsername = username.trim().replace(/^@/, "");
  const query = profileToken ? `?profile_token=${encodeURIComponent(profileToken)}` : "";
  return apiClient<UserProfileResponse>(`/users/${encodeURIComponent(normalizedUsername)}${query}`, {
    accessToken,
  });
}

/**
 * list followed users
 */
export function listFollowing(accessToken: string) {
  return apiClient<FollowedUserListResponse>("/users/following", { accessToken });
}

/**
 * follow user
 */
export function followUser(accessToken: string, username: string, profileToken?: string | null) {
  const normalizedUsername = username.trim().replace(/^@/, "");
  const query = profileToken ? `?profile_token=${encodeURIComponent(profileToken)}` : "";
  return apiClient<UserProfileResponse>(`/users/${encodeURIComponent(normalizedUsername)}/follow${query}`, {
    method: "POST",
    accessToken,
  });
}

/**
 * unfollow user
 */
export function unfollowUser(accessToken: string, username: string) {
  const normalizedUsername = username.trim().replace(/^@/, "");
  return apiClient<null>(`/users/${encodeURIComponent(normalizedUsername)}/follow`, {
    method: "DELETE",
    accessToken,
  });
}
