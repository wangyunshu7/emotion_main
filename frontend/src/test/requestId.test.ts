import { afterEach, expect, it, vi } from "vitest";
import { createRequestId } from "../utils/requestId";

afterEach(() => vi.unstubAllGlobals());

it("creates distinct v4 request IDs when randomUUID is unavailable on HTTP", () => {
  const getRandomValues = crypto.getRandomValues.bind(crypto);
  vi.stubGlobal("crypto", { getRandomValues });
  const ids = Array.from({ length: 100 }, () => createRequestId());
  expect(new Set(ids).size).toBe(100);
  for (const id of ids) {
    expect(id).toMatch(/^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/);
  }
});
