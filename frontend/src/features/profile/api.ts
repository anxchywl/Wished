// profile api client
import { apiClient } from "@/lib/api";

export type ProfileResponse = {
  id: string;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  birthday: string | null;
  language_code: string | null;
  is_premium: boolean | null;
  privacy: {
    profile_visibility: string;
    birthday_visibility: string;
    wishlist_visibility: string;
  };
};

/**
 * fetch current profile
 */
export function getProfile(accessToken: string) {
  return apiClient<ProfileResponse>("/me", { accessToken });
}

/**
 * update profile birthday
 */
export function patchProfile(accessToken: string, birthday: string) {
  return apiClient<ProfileResponse>("/me", {
    method: "PATCH",
    accessToken,
    body: { birthday },
  });
}
