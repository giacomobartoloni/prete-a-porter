"""Password and optional invited Google authentication owned by this shell.

Accounts are operator-provisioned (``scripts/create_user.py``); Chainlit has no
stock signup. Invited Google users may create accounts at first login. The
bcrypt hash lives in the persisted user metadata (cost 10,
matching the legacy frontend) but is never returned on the session ``User``
or from the public data-layer getter — see
``data_layer.SerializedSQLAlchemyDataLayer.get_user_for_auth``.

The core has no user entity: the identifier is used for the per-user quota and
the boundary log line, nothing else.
"""

import asyncio
from typing import Any

import bcrypt
import chainlit as cl
from chainlit.data import get_data_layer

from prete_chat import config

BCRYPT_ROUNDS = 10
PASSWORD_METADATA_KEY = "password_hash"
NAME_METADATA_KEY = "name"
GOOGLE_ID_METADATA_KEY = "google_id"


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

    The returned ``User`` is what Chainlit puts in the session JWT, so it must
    never carry ``password_hash``. Credentials are loaded via
    ``get_user_for_auth`` because the public ``get_user`` is session-safe and
    strips the hash (Chainlit also reloads ``get_user`` for ``/user``).
    """
    layer = get_data_layer()
    if layer is None:
        return None
    get_user_for_auth = getattr(layer, "get_user_for_auth", None)
    if get_user_for_auth is None:
        return None
    persisted = await get_user_for_auth(normalize_identifier(username))
    if persisted is None:
        return None
    metadata = persisted.metadata or {}
    stored = metadata.get(PASSWORD_METADATA_KEY)
    if not isinstance(stored, str) or not await asyncio.to_thread(verify_password, password, stored):
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


async def google_oauth(
    provider_id: str,
    token: str,
    raw_user_data: dict[str, Any],
    default_user: cl.User,
) -> cl.User | None:
    """Accept invited Google identities from Chainlit's verified OAuth exchange.

    Google v2 userinfo supplies ``verified_email`` and ``id``. The access token
    and framework default metadata are deliberately absent from the returned
    session. Private credentials are preserved by the data layer on persistence.
    """
    if provider_id != "google" or raw_user_data.get("verified_email") is not True:
        return None
    email, subject = raw_user_data.get("email"), raw_user_data.get("id")
    if not isinstance(email, str) or not isinstance(subject, str) or not subject.strip():
        return None
    identifier = normalize_identifier(email)
    if identifier not in config.google_allowed_emails():
        return None
    layer = get_data_layer()
    if layer is None:
        return None
    existing = await layer.get_user(identifier)
    if existing is not None:
        bound_subject = (existing.metadata or {}).get(GOOGLE_ID_METADATA_KEY)
        if bound_subject is not None and bound_subject != subject:
            return None
    name = raw_user_data.get("name")
    name = name.strip() if isinstance(name, str) and name.strip() else identifier
    metadata = {NAME_METADATA_KEY: name, "provider": "google", GOOGLE_ID_METADATA_KEY: subject}
    picture = raw_user_data.get("picture")
    if isinstance(picture, str) and picture.startswith("https://"):
        metadata["image"] = picture
    user = cl.User(identifier=identifier, display_name=name, metadata=metadata)
    # Chainlit logs and ignores persistence errors in its post-callback login
    # handler. Bind here atomically and check success before returning a User,
    # so a conflict or unavailable database cannot yield an OAuth session.
    persisted = await layer.create_user(user)
    return user if persisted is not None else None
