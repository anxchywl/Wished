import { useQuery } from "@tanstack/react-query";
import {
  fetchAdminMe,
  fetchAdminStats,
  fetchAdminUsers,
  fetchAdminWishlists,
  fetchAdminWishes,
  fetchAdminMedia,
  fetchAuditLogs,
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
