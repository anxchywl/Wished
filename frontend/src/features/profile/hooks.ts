// profile hooks
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getProfile, patchProfile, patchPrivacy } from "./api";
import { useAuthStore, useSyncTgUserId } from "@/stores/auth-store";
import { userQueryKeys } from "@/features/users/hooks";

/**
 * fetch current user profile
 */
export function useProfileQuery(accessToken: string | null) {
  const tgUserId = useSyncTgUserId();
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
  const tgUserId = useSyncTgUserId();
  return useMutation({
    mutationFn: ({ accessToken, birthday }: { accessToken: string; birthday: string | null }) =>
      patchProfile(accessToken, birthday),
    onSuccess: (profile) => {
      queryClient.setQueryData(["profile", tgUserId], profile);
    },
  });
}

/**
 * update privacy settings
 */
export function useUpdatePrivacyMutation() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state) => state.accessToken);
  const tgUserId = useSyncTgUserId();
  return useMutation({
    mutationFn: (privacy: {
      profile_visibility?: string;
      birthday_visibility?: string;
      wishlist_visibility?: string;
      booking_visibility?: string;
      group_gift_visibility?: string;
    }) => patchPrivacy(accessToken ?? "", privacy),
    onMutate: async (privacy) => {
      await queryClient.cancelQueries({ queryKey: ["profile", tgUserId] });
      const previousProfile = queryClient.getQueryData(["profile", tgUserId]);
      queryClient.setQueryData(["profile", tgUserId], (current: unknown) => {
        if (!current || typeof current !== "object" || !("privacy" in current)) {
          return current;
        }
        return {
          ...current,
          privacy: {
            ...(current as { privacy: Record<string, unknown> }).privacy,
            ...privacy,
          },
        };
      });
      return { previousProfile };
    },
    onError: (_error, _privacy, context) => {
      if (context?.previousProfile) {
        queryClient.setQueryData(["profile", tgUserId], context.previousProfile);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", tgUserId] });
      // refresh all screens that depend on visibility settings
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
      queryClient.invalidateQueries({ queryKey: ["wishes"] });
      queryClient.invalidateQueries({ queryKey: ["group-gifts"] });
    },
  });
}
