import { describe, expect, it } from "vitest";

import {
  decodeProfileStartParam,
  decodeWishlistStartParam,
  encodeProfileStartParam,
} from "./start-param";

describe("profile start params", () => {
  it("encodes and decodes compact public profile payloads", () => {
    expect(encodeProfileStartParam("Max_472")).toBe("p_max_472");
    expect(decodeProfileStartParam("p_max_472")).toBe("max_472");
  });

  it("rejects invalid profile payloads without affecting wishlist payloads", () => {
    expect(encodeProfileStartParam("max-472")).toBeNull();
    expect(decodeProfileStartParam("p_max-472")).toBeNull();
    expect(decodeWishlistStartParam("p_max_472")).toBeNull();
  });
});
