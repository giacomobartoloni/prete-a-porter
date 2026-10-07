"""Password authentication owned by this shell (plan §17).

Accounts are operator-provisioned (``scripts/create_user.py``); Chainlit has no
stock signup. The bcrypt hash lives in the persisted user metadata (cost 10,
matching the legacy frontend) but is never returned on the session ``User`` —
see ``data_layer.SerializedSQLAlchemyDataLayer.create_user``.

The core has no user entity: the identifier is used for the per-user quota and
the boundary log line, nothing else.
"""

import bcrypt
import chainlit as cl
from chainlit.data import get_data_layer

BCRYPT_ROUNDS = 10
PASSWORD_METADATA_KEY = "password_hash"
NAME_METADATA_KEY = "name"


def normalize_identifier(username: str) -> str:
    """Normalise the login identifier; the email is the account key."""
    return username.strip().lower()


def hash_password(password: str) -> str:
    """Hash a password for storage in the Chainlit user metadata."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against a stored hash; malformed hashes never match."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


async def password_auth(username: str, password: str) -> cl.User | None:
    """Chainlit password callback: verify against the persisted bcrypt hash.

    Returns ``None`` for every failure (unknown user, wrong password, no data
    layer) so the login page cannot be used to enumerate accounts.

    The returned ``User`` is what Chainlit puts in the session JWT and exposes
    via ``/user``, so it must never carry ``password_hash``. The custom data
    layer re-injects the hash only on the persistence path when Chainlit calls
    ``create_user`` after a successful login.
    """
    layer = get_data_layer()
    if layer is None:
        return None
    persisted = await layer.get_user(normalize_identifier(username))
    if persisted is None:
        return None
    metadata = persisted.metadata or {}
    stored = metadata.get(PASSWORD_METADATA_KEY)
    if not isinstance(stored, str) or not verify_password(password, stored):
        return None
    name = metadata.get(NAME_METADATA_KEY)
    client_metadata: dict[str, str] = {}
    if isinstance(name, str):
        client_metadata[NAME_METADATA_KEY] = name
    return cl.User(
        identifier=persisted.identifier,
        display_name=name or persisted.identifier,
        metadata=client_metadata,
    )
