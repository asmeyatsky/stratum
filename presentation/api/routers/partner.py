"""
Partner API router — white-label assessment and webhook management.

Architectural Intent:
    Provides the partner-facing REST API for the Stratum platform. Partners
    (consultancies, tooling vendors) use these endpoints to create assessments,
    retrieve results, and register webhooks for asynchronous status callbacks.

    This is a thin HTTP adapter — no domain logic lives here. The router
    validates input via Pydantic schemas, manages in-memory stores (MVP),
    and returns serialised responses.

    In production, the in-memory stores will be replaced by BigQuery or
    a relational database.

Design Decisions:
    - Partner authentication is separate from analyst auth — uses
      X-Partner-Key header (MVP: env var, Phase 4: partner-scoped JWT).
    - Assessment creation is a white-label operation: the partner_id is
      embedded in the request, and the assessment is scoped to that partner.
    - Webhook registration stores URLs per partner; events are dispatched
      asynchronously via the WebhookDispatcher adapter.
    - Webhook events: assessment.started, assessment.completed, assessment.failed.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/partner", tags=["partner"])


# ---------------------------------------------------------------------------
# Pydantic schemas (partner-specific)
# ---------------------------------------------------------------------------

class AssessmentCreateRequest(BaseModel):
    partner_id: str = Field(
        min_length=1,
        max_length=100,
        description="Partner identifier for white-label scoping",
    )
    project_name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable project name",
    )
    repository_url: str = Field(
        min_length=1,
        max_length=500,
        description="Git repository URL to analyse",
    )
    scenario: str = Field(
        default="cto_onboarding",
        description="Analysis scenario (ma_due_diligence, vendor_audit, etc.)",
    )
    callback_url: str | None = Field(
        default=None,
        description="Optional one-time webhook URL for this assessment's status callbacks",
    )


class AssessmentResponse(BaseModel):
    assessment_id: str = Field(description="Unique assessment identifier")
    partner_id: str = Field(description="Partner identifier")
    project_name: str = Field(description="Project name")
    repository_url: str = Field(description="Repository URL")
    scenario: str = Field(description="Analysis scenario")
    status: str = Field(description="Assessment status: pending, running, completed, failed")
    created_at: str = Field(description="Creation timestamp ISO-8601")
    updated_at: str = Field(description="Last update timestamp ISO-8601")
    overall_health_score: float | None = Field(
        default=None,
        description="Health score (null until analysis completes)",
    )
    results: dict | None = Field(
        default=None,
        description="Full assessment results (null until analysis completes)",
    )


class AssessmentListResponse(BaseModel):
    assessments: list[AssessmentResponse] = Field(description="List of assessments")
    total: int = Field(description="Total assessment count")


class WebhookRegisterRequest(BaseModel):
    partner_id: str = Field(
        min_length=1,
        max_length=100,
        description="Partner identifier",
    )
    url: str = Field(
        min_length=1,
        max_length=500,
        description="Webhook endpoint URL (must be HTTPS in production)",
    )
    events: list[str] = Field(
        default=["assessment.started", "assessment.completed", "assessment.failed"],
        description="List of event types to subscribe to",
    )
    secret: str | None = Field(
        default=None,
        description="Shared secret for HMAC-SHA256 signature verification",
    )


class WebhookResponse(BaseModel):
    webhook_id: str = Field(description="Unique webhook registration identifier")
    partner_id: str = Field(description="Partner identifier")
    url: str = Field(description="Registered webhook URL")
    events: list[str] = Field(description="Subscribed event types")
    created_at: str = Field(description="Registration timestamp ISO-8601")


# ---------------------------------------------------------------------------
# In-memory stores (MVP — replaced by persistent storage in production)
# ---------------------------------------------------------------------------

_assessments: dict[str, dict] = {}
_webhooks: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Partner authentication
# ---------------------------------------------------------------------------

_MVP_PARTNER_KEY: str | None = os.environ.get("STRATUM_PARTNER_KEY")


async def verify_partner_key(
    x_partner_key: Annotated[str | None, Header()] = None,
) -> str:
    """Validate the partner API key.

    - If ``STRATUM_PARTNER_KEY`` env var is set, the request must provide
      a matching ``X-Partner-Key`` header.
    - If the env var is not set and ``STRATUM_DEV_MODE=true``, open access
      is allowed (development mode only).
    - If the env var is not set and dev mode is off, return 503 — the
      partner API is not configured.
    - In Phase 4 this will be replaced with partner-scoped JWT validation.

    Returns:
        The partner key string (used for audit logging).
    """
    expected_key = _MVP_PARTNER_KEY or os.environ.get("STRATUM_PARTNER_KEY")

    if expected_key:
        if not x_partner_key or x_partner_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing partner API key. Provide X-Partner-Key header.",
                headers={"WWW-Authenticate": "PartnerKey"},
            )
        return x_partner_key

    # No partner key configured
    if os.environ.get("STRATUM_DEV_MODE", "").lower() == "true":
        logger.warning(
            "Partner API open access — STRATUM_PARTNER_KEY not set and STRATUM_DEV_MODE=true. "
            "Do NOT use this in production."
        )
        return x_partner_key or "dev_partner"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Partner API not configured",
    )


# ---------------------------------------------------------------------------
# Assessment endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assessment",
    description=(
        "Create a white-label assessment for a partner. Accepts a partner_id, "
        "project details, and optional callback URL. The assessment is queued "
        "for asynchronous processing."
    ),
)
async def create_assessment(
    body: AssessmentCreateRequest,
    partner_key: Annotated[str, Depends(verify_partner_key)],
) -> AssessmentResponse:
    """Create a new white-label assessment."""
    now = datetime.now(UTC).isoformat()
    assessment_id = f"asmt_{uuid.uuid4().hex[:12]}"

    assessment_data = {
        "assessment_id": assessment_id,
        "partner_id": body.partner_id,
        "project_name": body.project_name,
        "repository_url": body.repository_url,
        "scenario": body.scenario,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "overall_health_score": None,
        "results": None,
        "callback_url": body.callback_url,
    }
    _assessments[assessment_id] = assessment_data

    return _assessment_to_response(assessment_data)


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentResponse,
    summary="Get assessment status and results",
    description="Retrieve the current status and results (when complete) of an assessment.",
)
async def get_assessment(
    assessment_id: str,
    partner_key: Annotated[str, Depends(verify_partner_key)],
) -> AssessmentResponse:
    """Get assessment by ID."""
    assessment = _assessments.get(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found.",
        )
    return _assessment_to_response(assessment)


@router.get(
    "/assessments",
    response_model=AssessmentListResponse,
    summary="List all assessments for a partner",
    description="Retrieve all assessments, optionally filtered by partner_id query parameter.",
)
async def list_assessments(
    partner_key: Annotated[str, Depends(verify_partner_key)],
    partner_id: str | None = None,
) -> AssessmentListResponse:
    """List all assessments, optionally filtered by partner_id."""
    assessments = list(_assessments.values())

    if partner_id:
        assessments = [a for a in assessments if a["partner_id"] == partner_id]

    # Most recently updated first
    assessments.sort(key=lambda a: a["updated_at"], reverse=True)

    return AssessmentListResponse(
        assessments=[_assessment_to_response(a) for a in assessments],
        total=len(assessments),
    )


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a webhook URL",
    description=(
        "Register a webhook endpoint to receive status callbacks for assessment "
        "events. Supported events: assessment.started, assessment.completed, "
        "assessment.failed."
    ),
)
async def register_webhook(
    body: WebhookRegisterRequest,
    partner_key: Annotated[str, Depends(verify_partner_key)],
) -> WebhookResponse:
    """Register a webhook URL for a partner."""
    now = datetime.now(UTC).isoformat()
    webhook_id = f"whk_{uuid.uuid4().hex[:12]}"

    # Validate event types
    valid_events = {"assessment.started", "assessment.completed", "assessment.failed"}
    invalid_events = set(body.events) - valid_events
    if invalid_events:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event types: {', '.join(sorted(invalid_events))}. "
                   f"Valid events: {', '.join(sorted(valid_events))}",
        )

    webhook_data = {
        "webhook_id": webhook_id,
        "partner_id": body.partner_id,
        "url": body.url,
        "events": body.events,
        "secret": body.secret,
        "created_at": now,
    }
    _webhooks[webhook_id] = webhook_data

    return WebhookResponse(
        webhook_id=webhook_id,
        partner_id=body.partner_id,
        url=body.url,
        events=body.events,
        created_at=now,
    )


class WebhookListResponse(BaseModel):
    webhooks: list[WebhookResponse] = Field(description="List of registered webhooks")
    total: int = Field(description="Total webhook count")


@router.get(
    "/webhooks",
    response_model=WebhookListResponse,
    summary="List registered webhooks",
    description="Retrieve all registered webhooks, optionally filtered by partner_id.",
)
async def list_webhooks(
    partner_key: Annotated[str, Depends(verify_partner_key)],
    partner_id: str | None = None,
) -> WebhookListResponse:
    """List all registered webhooks, optionally filtered by partner_id."""
    webhooks = list(_webhooks.values())

    if partner_id:
        webhooks = [w for w in webhooks if w["partner_id"] == partner_id]

    return WebhookListResponse(
        webhooks=[
            WebhookResponse(
                webhook_id=w["webhook_id"],
                partner_id=w["partner_id"],
                url=w["url"],
                events=w["events"],
                created_at=w["created_at"],
            )
            for w in webhooks
        ],
        total=len(webhooks),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assessment_to_response(data: dict) -> AssessmentResponse:
    """Map internal dict to response schema."""
    return AssessmentResponse(
        assessment_id=data["assessment_id"],
        partner_id=data["partner_id"],
        project_name=data["project_name"],
        repository_url=data["repository_url"],
        scenario=data["scenario"],
        status=data["status"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        overall_health_score=data.get("overall_health_score"),
        results=data.get("results"),
    )
