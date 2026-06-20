// profile hooks
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getProfile, patchProfile, patchPrivacy } from "./api";
import { useAuthStore } from "@/stores/auth-store";
import { userQueryKeys } from "@/features/users/hooks";

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
    mutationFn: ({ accessToken, birthday }: { accessToken: string; birthday: string | null }) =>
      patchProfile(accessToken, birthday),
    onSuccess: (profile) => {
      queryClient.setQueryData(["profile", tgUserId], profile);
      queryClient.invalidateQueries({ queryKey: userQueryKeys.all });
    },
  });
}

/**
 * update privacy settings
 */
export function useUpdatePrivacyMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useAuthStore((state) => state.tgUserId);
  return useMutation({
    mutationFn: (privacy: {
      profile_visibility?: string;
      birthday_visibility?: string;
      wishlist_visibility?: string;
      booking_visibility?: string;
    }) => patchPrivacy(accessToken ?? "", privacy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", tgUserId] });
    },
  });
}
