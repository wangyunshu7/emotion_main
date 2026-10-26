import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

export default function setup() {
  const url =
    process.env.E2E_DATABASE_URL ||
    "postgresql+psycopg://emotion:emotion@127.0.0.1:55432/emotion_test";
  if (!new URL(url).pathname.endsWith("_test"))
    throw new Error("E2E requires a dedicated _test database");
  const python = resolve(
    process.platform === "win32"
      ? "../backend/.venv/Scripts/python.exe"
      : "../backend/.venv/bin/python",
  );
  const env = {
    ...process.env,
    DATABASE_URL: url,
    APP_ENV: "test",
    AI_ENABLED: "true",
    AI_PROVIDER: "fake",
  };
  execFileSync(python, ["-m", "alembic", "upgrade", "head"], {
    cwd: resolve("../backend"),
    env,
  });
  execFileSync(
    python,
    [
      "-m",
      "app.cli.seed",
      "--demo",
      "--email",
      `fixture-${Date.now()}@example.com`,
      "--password",
      "fixture-local-password-123",
    ],
    { cwd: resolve("../backend"), env },
  );
}
