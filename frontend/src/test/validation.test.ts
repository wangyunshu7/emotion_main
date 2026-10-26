import { describe, expect, it } from "vitest";
import { DateTime } from "luxon";
import { clearPrivateStorage, message } from "../api/client";

describe("private browser state and time conversion", () => {
  it("clears all account drafts while preserving unrelated application keys", () => {
    sessionStorage.setItem("emotion-draft:a:new", "private a");
    sessionStorage.setItem("emotion-draft:b:1", "private b");
    sessionStorage.setItem("unrelated", "keep");
    clearPrivateStorage();
    expect(sessionStorage.getItem("emotion-draft:a:new")).toBeNull();
    expect(sessionStorage.getItem("emotion-draft:b:1")).toBeNull();
    expect(sessionStorage.getItem("unrelated")).toBe("keep");
  });
  it("uses IANA offsets rather than a fixed timezone offset", () => {
    const winter = DateTime.fromISO("2026-01-01T12:00", {
      zone: "America/New_York",
    }).toUTC();
    const summer = DateTime.fromISO("2026-07-01T12:00", {
      zone: "America/New_York",
    }).toUTC();
    expect(winter.hour).toBe(17);
    expect(summer.hour).toBe(16);
  });
  it("provides a readable fallback for failed operations", () => {
    expect(message(new Error("没有保存"))).toBe("没有保存");
    expect(message(null)).toBe("操作未完成，请重试");
  });
});
