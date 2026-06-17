// auth state hooks
import { useMutation } from "@tanstack/react-query";

import { authenticateTelegram } from "./api";

/**
 * use telegram login mutation
 */
export function useTelegramLoginMutation() {
  return useMutation({
    mutationKey: ["telegramLogin"],
    mutationFn: (initData: string) => authenticateTelegram(initData),
  });
}
