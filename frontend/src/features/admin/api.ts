import { apiClient } from "@/lib/api/api-client";
import { useAuthStore } from "@/stores/auth-store";

function getToken(): string | null {
  return useAuthStore.getState().accessToken;
}

export type AdminStatsResponse = {
  total_users: number;
  active_users: number;
  total_wishlists: number;
  total_wishes: number;
  active_wishes: number;
  total_reservations: number;
  total_media: number;
  total_follows: number;
};

export type AdminUserItem = {
  id: string;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  created_at: string;
  last_login_at: string | null;
  wishlist_count: number;
  wish_count: number;
  is_blocked: boolean;
  blocked_at: string | null;
  blocked_reason: string | null;
  is_admin: boolean;
};

export type ModerationLogItem = {
  id: string;
  user_id: string;
  action: string;
  reason: string | null;
  performed_by: string;
  created_at: string;
};

export type AdminWishlistItem = {
  id: string;
  owner_telegram_id: number;
  owner_username: string | null;
  title: string;
  visibility: string;
  wish_count: number;
  created_at: string;
};

export type AdminWishItem = {
  id: string;
  wishlist_id: string;
  owner_telegram_id: number;
  owner_username: string | null;
  title: string;
  status: string;
  created_at: string;
  has_reservation: boolean;
  image_count: number;
};

export type AdminMediaItem = {
  id: string;
  wish_id: string;
  owner_telegram_id: number;
  object_name: string;
  status: string;
  created_at: string;
};

export type AuditLogItem = {
  id: number;
  actor_user_id: string | null;
  actor_telegram_id: number | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  metadata_json: unknown | null;
  created_at: string;
};

export type AdminMeResponse = {
  is_admin: boolean;
  telegram_id: number;
};

export async function fetchAdminMe(accessToken?: string | null): Promise<AdminMeResponse> {
  const token = accessToken ?? getToken();
  if (!token) throw new Error("No access token");
  return apiClient<AdminMeResponse>("/admin/me", { accessToken: token });
}

export async function fetchAdminStats(): Promise<AdminStatsResponse> {
  return apiClient<AdminStatsResponse>("/admin/stats", { accessToken: getToken() });
}

export async function fetchAdminUsers(q?: string): Promise<AdminUserItem[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (q) params.set("q", q);
  return apiClient<AdminUserItem[]>(`/admin/users?${params}`, { accessToken: getToken() });
}

export async function fetchAdminWishlists(visibility?: string): Promise<AdminWishlistItem[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (visibility) params.set("visibility", visibility);
  return apiClient<AdminWishlistItem[]>(`/admin/wishlists?${params}`, { accessToken: getToken() });
}

export async function fetchAdminWishes(status?: string): Promise<AdminWishItem[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (status) params.set("wish_status", status);
  return apiClient<AdminWishItem[]>(`/admin/wishes?${params}`, { accessToken: getToken() });
}

export async function fetchAdminMedia(): Promise<AdminMediaItem[]> {
  return apiClient<AdminMediaItem[]>("/admin/media?limit=200", { accessToken: getToken() });
}

export async function fetchAuditLogs(): Promise<AuditLogItem[]> {
  return apiClient<AuditLogItem[]>("/admin/audit-logs?limit=100", { accessToken: getToken() });
}

export async function blockUser(userId: string, reason: string): Promise<void> {
  return apiClient<void>(`/admin/users/${userId}/block`, {
    method: "POST",
    body: { reason },
    accessToken: getToken(),
  });
}

export async function unblockUser(userId: string): Promise<void> {
  return apiClient<void>(`/admin/users/${userId}/unblock`, {
    method: "POST",
    accessToken: getToken(),
  });
}

export async function fetchModerationLogs(userId: string): Promise<ModerationLogItem[]> {
  return apiClient<ModerationLogItem[]>(`/admin/users/${userId}/moderation-logs`, { accessToken: getToken() });
}
