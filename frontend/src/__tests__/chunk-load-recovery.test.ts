import { beforeEach, describe, expect, it, vi } from "vitest";

import { recoverFromChunkLoadError } from "@/lib/errors/chunk-load-recovery";

describe("recoverFromChunkLoadError", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("ignores unrelated errors", () => {
    expect(recoverFromChunkLoadError(new Error("network unavailable"))).toBe(false);
  });

  it("marks a chunk failure for one bounded reload", () => {
    expect(recoverFromChunkLoadError(new Error("Loading chunk 361 failed"))).toBe(true);
    expect(window.sessionStorage.getItem("wished/chunk-reload")).not.toBeNull();
    expect(recoverFromChunkLoadError(new Error("Loading chunk 361 failed"))).toBe(false);
  });
});
