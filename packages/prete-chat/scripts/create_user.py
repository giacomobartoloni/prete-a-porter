"""Operator CLI: create or update a Chainlit user.

Chainlit has no stock signup (plan §17), so accounts are provisioned here with a
bcrypt hash in the user metadata. Idempotent: re-running updates the metadata
(name and password) of an existing identifier.

    uv run python scripts/create_user.py --email don@example.com --name "Don Mario"

Without ``--password`` the password is read from the prompt, so it never lands in
the shell history. Requires ``DATABASE_URL=postgresql+asyncpg://…``.
"""

import argparse
import asyncio
import getpass

import chainlit as cl

from prete_chat import auth, data_layer


async def upsert_user(email: str, name: str, password: str) -> str:
    """Create the account or update its metadata; returns what happened."""
    layer = data_layer.build()
    if layer is None:
        raise SystemExit("DATABASE_URL=postgresql+asyncpg://… is required to provision users.")
    identifier = auth.normalize_identifier(email)
    existing = await layer.get_user(identifier)
    await layer.create_user(
        cl.User(
            identifier=identifier,
            display_name=name,
            metadata={
                auth.NAME_METADATA_KEY: name,
                auth.PASSWORD_METADATA_KEY: auth.hash_password(password),
            },
        )
    )
    await layer.close()
    return "updated" if existing else "created"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a Prête-à-Porter chat user.")
    parser.add_argument("--email", required=True, help="login identifier (stored lowercased)")
    parser.add_argument("--name", required=True, help="display name")
    parser.add_argument("--password", help="omit to be prompted")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if not password:
        raise SystemExit("Password must not be empty.")
    action = asyncio.run(upsert_user(args.email, args.name, password))
    print(f"User {auth.normalize_identifier(args.email)} {action}.")


if __name__ == "__main__":
    main()
