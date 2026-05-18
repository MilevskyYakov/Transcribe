import { describe, expect, it } from "vitest";
import { formatBytes, formatSeconds } from "./format";

describe("format helpers", () => {
  it("formats seconds as transcript timestamps", () => {
    expect(formatSeconds(0)).toBe("00:00.0");
    expect(formatSeconds(64.25)).toBe("01:04.3");
  });

  it("formats artifact sizes", () => {
    expect(formatBytes(12)).toBe("12 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
  });
});
