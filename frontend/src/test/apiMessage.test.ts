import { expect, it } from "vitest";
import { ApiError, message } from "../api/client";

it("preserves the API error through repeated UI formatting", () => {
  const error = new ApiError(403, "CSRF_INVALID", "会话校验失败，请刷新页面");
  expect(message(message(error))).toBe(error.message);
});

it("preserves an existing connection error message", () => {
  expect(message("暂时无法连接服务")).toBe("暂时无法连接服务");
});

it("uses the fallback for missing or blank error details", () => {
  for (const value of [undefined, null, "", "   ", {}]) {
    expect(message(value)).toBe("操作未完成，请重试");
  }
});
