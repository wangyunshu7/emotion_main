"""Create local configuration without overwriting existing secrets."""

import argparse
import base64
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--database-url",
    default="postgresql+psycopg://emotion:emotion@localhost:5432/emotion",
)
args = parser.parse_args()
target = root / ".env"
if target.exists():
    print(".env already exists; no changes made.")
else:
    value = (root / ".env.example").read_text(encoding="utf-8")
    value = value.replace("CHANGE_ME_SESSION_SECRET", secrets.token_urlsafe(48))
    value = value.replace(
        "CHANGE_ME_LEDGER_KEY",
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    )
    value = value.replace(
        "postgresql+psycopg://emotion:emotion@localhost:5432/emotion", args.database_url
    )
    target.write_text(value, encoding="utf-8")
    print("Created .env with new local secrets. Keep this file private.")
