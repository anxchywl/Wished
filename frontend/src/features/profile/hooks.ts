// profile hooks
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getProfile, patchProfile } from "./api";
import { useAuthStore } from "@/stores/auth-store";

/**
 * fetch current user profile
 */
export function useProfileQuery(accessToken: string | null) {
  const tgUserId = useAuthStore((state) => state.tgUserId);
  const authStatus = useAuthStore((state) => state.authStatus);
  return useQuery({
    queryKey: ["profile", tgUserId],
    queryFn: () => getProfile(accessToken!),
    enabled: Boolean(authStatus === "authenticated" && accessToken),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * update profile birthday
 */
export function useUpdateBirthdayMutation() {
  const queryClient = useQueryClient();
  const tgUserId = useAuthStore((state) => state.tgUserId);
  return useMutation({
    mutationFn: ({ accessToken, birthday }: { accessToken: string; birthday: string }) =>
      patchProfile(accessToken, birthday),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", tgUserId] });
    },
  });
}
