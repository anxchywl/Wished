import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  blockUser,
  fetchAdminMe,
  fetchAdminStats,
  fetchAdminUsers,
  fetchAdminWishlists,
  fetchAdminWishes,
  fetchAdminMedia,
  fetchAuditLogs,
  fetchModerationLogs,
  unblockUser,
} from "./api";
import { useAuthStore } from "@/stores/auth-store";

export function useAdminStatus() {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "me", accessToken],
    queryFn: () => fetchAdminMe(accessToken),
    enabled: Boolean(accessToken),
    retry: false,
    staleTime: 5 * 60 * 1000,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });
}

export function useAdminStats() {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: fetchAdminStats,
    enabled: Boolean(accessToken),
    staleTime: 60 * 1000,
  });
}

export function useAdminUsers(q?: string) {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "users", q],
    queryFn: () => fetchAdminUsers(q),
    enabled: Boolean(accessToken),
    staleTime: 30 * 1000,
  });
}

export function useAdminWishlists(visibility?: string) {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "wishlists", visibility],
    queryFn: () => fetchAdminWishlists(visibility),
    enabled: Boolean(accessToken),
    staleTime: 30 * 1000,
  });
}

export function useAdminWishes(wishStatus?: string) {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "wishes", wishStatus],
    queryFn: () => fetchAdminWishes(wishStatus),
    enabled: Boolean(accessToken),
    staleTime: 30 * 1000,
  });
}

export function useAdminMedia() {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "media"],
    queryFn: fetchAdminMedia,
    enabled: Boolean(accessToken),
    staleTime: 30 * 1000,
  });
}

export function useAuditLogs() {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "audit-logs"],
    queryFn: fetchAuditLogs,
    enabled: Boolean(accessToken),
    staleTime: 30 * 1000,
  });
}

export function useModerationLogs(userId: string) {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["admin", "moderation-logs", userId],
    queryFn: () => fetchModerationLogs(userId),
    enabled: Boolean(accessToken) && Boolean(userId),
    staleTime: 10 * 1000,
  });
}

export function useBlockUser(searchQuery?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, reason }: { userId: string; reason: string }) => blockUser(userId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users", searchQuery] });
    },
  });
}

export function useUnblockUser(searchQuery?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId }: { userId: string }) => unblockUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users", searchQuery] });
    },
  });
}
