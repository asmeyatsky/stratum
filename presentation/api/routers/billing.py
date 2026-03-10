"""
Billing router — Stripe billing integration stubs.

Architectural Intent:
    Thin HTTP adapter for Stripe billing integration (Phase 2 wiring).
    Provides endpoints for pricing tiers, subscription management, usage
    tracking, and Stripe webhook handling.

    These are stubs that return realistic data structures matching the
    Stratum pricing model. In Phase 3, the Stripe SDK will be wired in
    to create actual Checkout Sessions, manage subscriptions, and process
    webhook events.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from presentation.api.dependencies import get_current_user
from presentation.api.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Pricing tier definitions
# ---------------------------------------------------------------------------

_PRICING_TIERS = [
    {
        "plan_id": "assessment",
        "name": "Assessment",
        "description": (
            "One-time codebase assessment. Ideal for M&A due diligence, "
            "vendor audits, and initial technology evaluations."
        ),
        "price_cents": 500_00,
        "currency": "usd",
        "billing_period": "one-time",
        "features": [
            "Single repository analysis",
            "15-dimension risk scoring",
            "AI-generated executive narrative",
            "PDF report export",
            "30-day report access",
        ],
        "limits": {
            "repositories": 1,
            "analyses_per_month": 1,
            "history_depth_months": 24,
        },
    },
    {
        "plan_id": "pro",
        "name": "Pro",
        "description": (
            "Continuous monitoring for engineering teams. Track codebase "
            "health over time with automated weekly scans."
        ),
        "price_cents": 299_00,
        "currency": "usd",
        "billing_period": "monthly",
        "features": [
            "Up to 10 repositories",
            "15-dimension risk scoring",
            "AI-generated executive narrative",
            "GitHub & Jira integration",
            "Weekly automated scans",
            "Trend analysis dashboard",
            "PDF & JSON report export",
            "Email alerts on risk changes",
        ],
        "limits": {
            "repositories": 10,
            "analyses_per_month": 50,
            "history_depth_months": 36,
        },
    },
    {
        "plan_id": "enterprise",
        "name": "Enterprise",
        "description": (
            "Full-platform access for large organisations. Unlimited "
            "repositories, custom scenarios, and dedicated support."
        ),
        "price_cents": 999_00,
        "currency": "usd",
        "billing_period": "monthly",
        "features": [
            "Unlimited repositories",
            "15-dimension risk scoring",
            "AI-generated executive narrative",
            "GitHub & Jira integration",
            "Daily automated scans",
            "Trend analysis dashboard",
            "Custom analysis scenarios",
            "SSO / SAML authentication",
            "Dedicated support channel",
            "SLA guarantees",
            "On-premise deployment option",
        ],
        "limits": {
            "repositories": -1,  # unlimited
            "analyses_per_month": -1,
            "history_depth_months": -1,
        },
    },
    {
        "plan_id": "partner",
        "name": "Partner",
        "description": (
            "White-label Stratum for consulting firms, PE/VC funds, and "
            "technology advisory practices. Includes API access and "
            "custom branding."
        ),
        "price_cents": 2499_00,
        "currency": "usd",
        "billing_period": "monthly",
        "features": [
            "Everything in Enterprise",
            "White-label reports with custom branding",
            "Multi-tenant client management",
            "Bulk analysis API",
            "Custom report templates",
            "Partner dashboard",
            "Revenue share programme",
            "Priority support with SLA",
        ],
        "limits": {
            "repositories": -1,
            "analyses_per_month": -1,
            "history_depth_months": -1,
        },
    },
]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    plan_id: str = Field(description="Plan identifier")
    name: str = Field(description="Plan display name")
    description: str = Field(description="Plan description")
    price_cents: int = Field(description="Price in cents (USD)")
    currency: str = Field(default="usd", description="Currency code")
    billing_period: str = Field(description="Billing period: one-time / monthly")
    features: list[str] = Field(description="List of included features")
    limits: dict[str, int] = Field(description="Plan limits")


class PlanListResponse(BaseModel):
    plans: list[PlanResponse] = Field(description="Available pricing plans")


class SubscribeRequest(BaseModel):
    plan_id: str = Field(description="Plan to subscribe to")
    success_url: str = Field(
        default="https://app.stratum.dev/billing/success",
        description="Redirect URL after successful payment",
    )
    cancel_url: str = Field(
        default="https://app.stratum.dev/billing/cancel",
        description="Redirect URL if payment is cancelled",
    )


class SubscribeResponse(BaseModel):
    checkout_session_id: str = Field(description="Stripe Checkout Session ID (stub)")
    checkout_url: str = Field(description="URL to redirect user for payment")
    plan_id: str = Field(description="Selected plan")
    message: str = Field(default="", description="Status message")


class UsageResponse(BaseModel):
    user_id: str = Field(description="User identifier")
    plan_id: str = Field(description="Current plan")
    billing_period_start: str = Field(description="Current billing period start")
    billing_period_end: str = Field(description="Current billing period end")
    repositories_used: int = Field(description="Repositories currently tracked")
    repositories_limit: int = Field(description="Repository limit (-1 = unlimited)")
    analyses_this_period: int = Field(description="Analyses run this billing period")
    analyses_limit: int = Field(description="Analysis limit per period (-1 = unlimited)")


class WebhookResponse(BaseModel):
    received: bool = Field(description="Whether the webhook was processed")
    event_type: str = Field(default="", description="Stripe event type")
    message: str = Field(default="", description="Processing result")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    response_model=PlanListResponse,
    summary="List pricing plans",
    description="Return the available Stratum pricing tiers.",
)
async def list_plans() -> PlanListResponse:
    """Return all available pricing plans."""
    plans = [PlanResponse(**tier) for tier in _PRICING_TIERS]
    return PlanListResponse(plans=plans)


@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    summary="Create subscription",
    description=(
        "Create a Stripe Checkout Session for the selected plan. "
        "Returns a checkout URL to redirect the user for payment. "
        "(Stub — Stripe SDK not yet wired.)"
    ),
)
async def subscribe(
    body: SubscribeRequest,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> SubscribeResponse:
    """Create a Stripe Checkout Session stub for the selected plan."""
    # Validate plan exists
    valid_plan_ids = {tier["plan_id"] for tier in _PRICING_TIERS}
    if body.plan_id not in valid_plan_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id: {body.plan_id}. Valid plans: {', '.join(sorted(valid_plan_ids))}",
        )

    # Stub checkout session — in production this calls stripe.checkout.Session.create()
    stub_session_id = f"cs_stub_{body.plan_id}_{current_user.user_id}"
    stub_checkout_url = (
        f"https://checkout.stripe.com/c/pay/{stub_session_id}"
        f"?success_url={body.success_url}&cancel_url={body.cancel_url}"
    )

    logger.info(
        "Stripe checkout session stub created: user=%s plan=%s session=%s",
        current_user.user_id, body.plan_id, stub_session_id,
    )

    return SubscribeResponse(
        checkout_session_id=stub_session_id,
        checkout_url=stub_checkout_url,
        plan_id=body.plan_id,
        message=(
            "Checkout session created (stub). In production, redirect the user "
            "to checkout_url to complete payment via Stripe."
        ),
    )


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Current usage statistics",
    description="Return current usage stats for the authenticated user's subscription.",
)
async def get_usage(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> UsageResponse:
    """Return current usage statistics (stub with placeholder data)."""
    now = datetime.now(UTC)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate end of month
    if now.month == 12:
        period_end = period_start.replace(year=now.year + 1, month=1)
    else:
        period_end = period_start.replace(month=now.month + 1)

    return UsageResponse(
        user_id=current_user.user_id,
        plan_id="pro",  # stub default
        billing_period_start=period_start.isoformat(),
        billing_period_end=period_end.isoformat(),
        repositories_used=3,
        repositories_limit=10,
        analyses_this_period=7,
        analyses_limit=50,
    )


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Stripe webhook handler",
    description=(
        "Receive and process Stripe webhook events (checkout.session.completed, "
        "invoice.paid, customer.subscription.updated, etc.). "
        "(Stub — logs the event type without processing.)"
    ),
)
async def stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> WebhookResponse:
    """Handle incoming Stripe webhook events (stub).

    In production, this endpoint will:
    1. Verify the webhook signature using the Stripe signing secret.
    2. Parse the event payload.
    3. Update subscription status, usage records, and access controls.
    """
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body",
        )

    # In production: verify signature with stripe.Webhook.construct_event()
    if not stripe_signature:
        logger.warning("Stripe webhook received without signature header")

    # Attempt to parse event type from JSON body
    event_type = "unknown"
    try:
        import json
        payload = json.loads(body_str)
        event_type = payload.get("type", "unknown")
    except (json.JSONDecodeError, AttributeError):
        pass

    logger.info("Stripe webhook received: type=%s", event_type)

    return WebhookResponse(
        received=True,
        event_type=event_type,
        message=(
            f"Webhook event '{event_type}' received and logged. "
            "Full processing will be implemented when Stripe SDK is wired."
        ),
    )
