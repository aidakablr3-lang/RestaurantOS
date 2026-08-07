#!/usr/bin/env python3
"""Generates a local-only RS256 keypair for `docker compose up`.

Same output as generate-dev-keys.sh, for developers who don't have
openssl on PATH but do have Python (cryptography ships as a transitive
dependency of services/api's pyjwt[crypto] pin, so no extra install is
needed if you've already run `pip install -e ".[dev]"`).
"""

from __future__ import annotations

import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

DIR = Path(__file__).resolve().parent
PRIVATE_KEY_PATH = DIR / "private.pem"
PUBLIC_KEY_PATH = DIR / "public.pem"


def main() -> None:
    if PRIVATE_KEY_PATH.exists() or PUBLIC_KEY_PATH.exists():
        print(f"Dev JWT keypair already exists at {DIR}")
        print("Delete private.pem and public.pem first if you want to regenerate it.")
        return

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    PRIVATE_KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        PRIVATE_KEY_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # best-effort; not all filesystems support POSIX permissions

    PUBLIC_KEY_PATH.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    print(f"Generated a local-only dev JWT keypair at {DIR}")
    print("Never commit private.pem or public.pem -- .gitignore already excludes them.")


if __name__ == "__main__":
    main()
