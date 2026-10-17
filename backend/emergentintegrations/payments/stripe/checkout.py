"""Drop-in replacement for Emergent's Stripe checkout wrapper.

Backed directly by the official ``stripe`` SDK (already a project
dependency). The checkout routes stay dormant unless a ``STRIPE_API_KEY``
is configured — which matches the free-community mission: no payments
are processed unless the operator deliberately enables them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, Optional

import stripe


def _resolve_key(passed: Optional[str]) -> str:
    key = (passed or "").strip() or os.environ.get("STRIPE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Stripe not configured: set the STRIPE_API_KEY environment variable."
        )
    return key


@dataclass
class CheckoutSessionRequest:
    amount: int  # in cents
    currency: str = "usd"
    success_url: str = ""
    cancel_url: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


class StripeCheckout:
    """Same shape as Emergent's wrapper; talks to Stripe directly."""

    def __init__(self, api_key: Optional[str] = None, webhook_url: str = "") -> None:
        self._passed_key = api_key
        self.webhook_url = webhook_url

    async def create_checkout_session(
        self, req: CheckoutSessionRequest
    ) -> SimpleNamespace:
        key = _resolve_key(self._passed_key)
        product_name = (req.metadata or {}).get("product", "MNQ Scalp Stacks")
        session = stripe.checkout.Session.create(
            api_key=key,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": req.currency or "usd",
                        "product_data": {"name": product_name},
                        "unit_amount": int(req.amount),
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            metadata=req.metadata or {},
        )
        return SimpleNamespace(session_id=session.id, url=session.url)

    async def get_checkout_status(self, session_id: str) -> SimpleNamespace:
        key = _resolve_key(self._passed_key)
        s = stripe.checkout.Session.retrieve(session_id, api_key=key)
        return SimpleNamespace(
            session_id=s.id,
            status=s.status,
            payment_status=s.payment_status,
            amount_total=s.amount_total,
            currency=s.currency,
            metadata=dict(s.metadata or {}),
        )
