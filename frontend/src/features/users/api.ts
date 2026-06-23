// users api client
import { apiClient } from "@/lib/api";
import type { WishlistListResponse } from "@/features/wishlists/types";

export type UserProfileResponse = {
  user_id: string;
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
 * get user profile by internal UUID
 */
export function getUserProfileById(accessToken: string, userId: string, profileToken?: string | null) {
  const query = profileToken ? `?profile_token=${encodeURIComponent(profileToken)}` : "";
  return apiClient<UserProfileResponse>(`/users/id/${encodeURIComponent(userId)}${query}`, {
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
 * follow user by internal UUID
 */
export function followUserById(accessToken: string, userId: string, profileToken?: string | null) {
  const query = profileToken ? `?profile_token=${encodeURIComponent(profileToken)}` : "";
  return apiClient<UserProfileResponse>(`/users/id/${encodeURIComponent(userId)}/follow${query}`, {
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

/**
 * unfollow user by internal UUID
 */
export function unfollowUserById(accessToken: string, userId: string) {
  return apiClient<null>(`/users/id/${encodeURIComponent(userId)}/follow`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * list user wishlists by internal UUID
 */
export function getUserWishlistsById(accessToken: string, userId: string, profileToken?: string | null) {
  const query = profileToken ? `?profile_token=${encodeURIComponent(profileToken)}` : "";
  return apiClient<WishlistListResponse>(`/users/id/${encodeURIComponent(userId)}/wishlists${query}`, {
    accessToken,
  });
}
