// auth api client
import { apiClient } from "@/lib/api";

export type UserResponse = {
  id: string;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  language_code: string | null;
  is_premium: boolean | null;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  access_token_expires_at: string;
  refresh_token_expires_at: string;
  user: UserResponse;
};

/**
 * authenticate with telegram
 */
export function authenticateTelegram(initData: string) {
  return apiClient<TokenResponse>("/auth/telegram", {
    method: "POST",
    body: { init_data: initData },
  });
}
