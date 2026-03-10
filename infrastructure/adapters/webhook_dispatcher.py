"""
WebhookDispatcher — Infrastructure adapter for asynchronous webhook delivery.

Architectural Intent:
    Dispatches webhook events to registered partner URLs when assessment
    status changes occur. Handles HMAC-SHA256 signing, retry with exponential
    backoff, and delivery logging.

    This adapter owns only the HTTP delivery mechanism. Event routing and
    webhook registration are managed by the partner API router and the
    application layer.

Design Decisions:
    - Uses httpx async client for non-blocking HTTP POST.
    - HMAC-SHA256 signature in ``X-Stratum-Signature`` header using the
      partner's shared secret. This allows partners to verify that webhooks
      originate from Stratum and have not been tampered with.
    - Retry with exponential backoff: 3 attempts with 2^n second delays.
    - Failed deliveries are logged but do not raise exceptions — webhook
      delivery is best-effort and must not block the assessment pipeline.
    - Payload structure: ``event_type``, ``timestamp``, ``assessment_id``,
      ``data`` (event-specific payload).
    - Content-Type: application/json.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds
_DELIVERY_TIMEOUT = 15.0  # seconds


@dataclass(frozen=True)
class WebhookEvent:
    """Immutable value object representing a webhook event to be delivered."""

    event_type: str  # assessment.started, assessment.completed, assessment.failed
    assessment_id: str
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class WebhookDispatcher:
    """Dispatches webhook events to registered partner endpoints.

    Args:
        timeout: HTTP request timeout in seconds for webhook delivery.
    """

    timeout: float = _DELIVERY_TIMEOUT

    async def dispatch(
        self,
        url: str,
        event: WebhookEvent,
        secret: str | None = None,
    ) -> bool:
        """Deliver a webhook event to a single URL with retry.

        Args:
            url: Target webhook endpoint URL.
            event: The webhook event to deliver.
            secret: Shared secret for HMAC-SHA256 signature. If ``None``,
                the ``X-Stratum-Signature`` header is omitted.

        Returns:
            ``True`` if the webhook was delivered successfully (2xx response),
            ``False`` if all retry attempts failed.
        """
        payload = self._build_payload(event)
        payload_bytes = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")

        headers = self._build_headers(payload_bytes, secret)

        for attempt in range(1, _MAX_RETRIES + 1):
            success = await self._attempt_delivery(
                url, payload_bytes, headers, attempt
            )
            if success:
                logger.info(
                    "Webhook delivered: event=%s assessment=%s url=%s attempt=%d",
                    event.event_type,
                    event.assessment_id,
                    url,
                    attempt,
                )
                return True

            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE ** attempt
                logger.info(
                    "Webhook delivery retry in %.1f seconds (attempt %d/%d)",
                    backoff,
                    attempt,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(backoff)

        logger.error(
            "Webhook delivery failed after %d attempts: event=%s assessment=%s url=%s",
            _MAX_RETRIES,
            event.event_type,
            event.assessment_id,
            url,
        )
        return False

    async def dispatch_to_many(
        self,
        targets: list[dict],
        event: WebhookEvent,
    ) -> dict[str, bool]:
        """Deliver a webhook event to multiple registered URLs concurrently.

        Args:
            targets: List of dicts with ``"url"`` and optional ``"secret"`` keys.
            event: The webhook event to deliver.

        Returns:
            Dict mapping each URL to its delivery success status.
        """
        tasks = [
            self.dispatch(
                url=target["url"],
                event=event,
                secret=target.get("secret"),
            )
            for target in targets
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        delivery_results: dict[str, bool] = {}
        for target, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.error(
                    "Unexpected error dispatching to %s: %s",
                    target["url"],
                    result,
                )
                delivery_results[target["url"]] = False
            else:
                delivery_results[target["url"]] = result

        return delivery_results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(event: WebhookEvent) -> dict:
        """Build the webhook JSON payload."""
        return {
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "assessment_id": event.assessment_id,
            "data": event.data,
        }

    @staticmethod
    def _build_headers(
        payload_bytes: bytes, secret: str | None
    ) -> dict[str, str]:
        """Build HTTP headers including HMAC signature if a secret is provided."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "Stratum-Webhook/1.0",
        }

        if secret:
            signature = hmac.new(
                key=secret.encode("utf-8"),
                msg=payload_bytes,
                digestmod=hashlib.sha256,
            ).hexdigest()
            headers["X-Stratum-Signature"] = f"sha256={signature}"

        return headers

    async def _attempt_delivery(
        self,
        url: str,
        payload_bytes: bytes,
        headers: dict[str, str],
        attempt: int,
    ) -> bool:
        """Attempt a single webhook delivery.

        Returns:
            ``True`` if the target responded with a 2xx status code.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    content=payload_bytes,
                    headers=headers,
                )

            if 200 <= response.status_code < 300:
                return True

            logger.warning(
                "Webhook target returned %d on attempt %d/%d for %s: %s",
                response.status_code,
                attempt,
                _MAX_RETRIES,
                url,
                response.text[:200],
            )
            return False

        except httpx.TimeoutException:
            logger.warning(
                "Webhook delivery timed out on attempt %d/%d for %s",
                attempt,
                _MAX_RETRIES,
                url,
            )
            return False

        except httpx.HTTPError as exc:
            logger.warning(
                "Webhook delivery HTTP error on attempt %d/%d for %s: %s",
                attempt,
                _MAX_RETRIES,
                url,
                exc,
            )
            return False
