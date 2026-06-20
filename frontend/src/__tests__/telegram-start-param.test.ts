import { describe, expect, it } from "vitest";

import {
  decodeWishlistStartParam,
  encodeWishlistStartParam,
} from "@/lib/telegram/start-param";

describe("wishlist Telegram start parameter", () => {
  it("round-trips a wishlist target using Telegram-safe characters", () => {
    const encoded = encodeWishlistStartParam(
      "emkaept",
      "b86aa973-3d01-4c6a-98bb-dcf4e42d7cdf",
    );

    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(decodeWishlistStartParam(encoded)).toEqual({
      username: "emkaept",
      wishlistId: "b86aa973-3d01-4c6a-98bb-dcf4e42d7cdf",
    });
  });

  it("ignores legacy and invalid start parameters", () => {
    expect(decodeWishlistStartParam("legacy-profile-token")).toBeNull();
    expect(decodeWishlistStartParam("wl_invalid")).toBeNull();
  });
});
