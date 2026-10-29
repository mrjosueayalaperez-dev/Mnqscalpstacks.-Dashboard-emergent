"""Env-driven Temporal client config. No secrets are hard-coded."""
import os
from typing import Optional

from temporalio.client import Client
from temporalio.service import TLSConfig

TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "mnq-birthcell-main")


def _tls() -> Optional[TLSConfig]:
    if os.environ.get("TEMPORAL_TLS", "false").lower() not in ("1", "true", "yes"):
        return None
    cert = os.environ.get("TEMPORAL_TLS_CERT_PATH")
    key = os.environ.get("TEMPORAL_TLS_KEY_PATH")
    if cert and key:
        with open(cert, "rb") as c, open(key, "rb") as k:
            return TLSConfig(client_cert=c.read(), client_private_key=k.read())
    return TLSConfig()


async def connect() -> Client:
    return await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        tls=_tls() or False,
        api_key=os.environ.get("TEMPORAL_API_KEY") or None,
    )
