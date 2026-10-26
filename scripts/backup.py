"""Create an encrypted PostgreSQL dump through the project's Docker Compose service.

Requires an independently stored BACKUP_ENCRYPTION_KEY (Fernet key). Does not restore data.
"""

import argparse
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=root / ".runtime" / "backups")
parser.add_argument("--retention-days", type=int, default=7)
args = parser.parse_args()
if args.retention_days < 1:
    raise SystemExit("Retention must be at least one day")
key = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
if not key:
    raise SystemExit(
        "Set BACKUP_ENCRYPTION_KEY; keep the key separate from backup files"
    )
cipher = Fernet(key.encode())
compose = [
    "docker",
    "compose",
    "--env-file",
    str(root / ".env"),
    "-f",
    str(root / "infra" / "compose.yml"),
    "exec",
    "-T",
    "db",
]
dump = subprocess.run(
    compose + ["pg_dump", "-U", "emotion", "-d", "emotion", "-Fc"],
    capture_output=True,
    check=True,
).stdout
subprocess.run(
    compose + ["pg_restore", "--list"], input=dump, capture_output=True, check=True
)
directory = args.output.resolve()
directory.mkdir(parents=True, exist_ok=True)
target = directory / f"emotion-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.dump.enc"
temporary = target.with_suffix(".tmp")
with open(temporary, "xb") as stream:
    stream.write(cipher.encrypt(dump))
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temporary, target)
threshold = datetime.now(UTC) - timedelta(days=args.retention_days)
for old in directory.glob("emotion-*.dump.enc"):
    if old.resolve().parent != directory or old.is_symlink():
        continue
    if datetime.fromtimestamp(old.stat().st_mtime, UTC) < threshold:
        old.unlink()
print(f"Created encrypted archive: {target.name}; PostgreSQL archive listing verified")
