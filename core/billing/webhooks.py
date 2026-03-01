from __future__ import annotations
from typing import Dict, Any
from datetime import datetime
from enum import Enum
import logging


class WebhookEventType(Enum):
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    CHARGE_SUCCEEDED = "charge_succeeded"
    CHARGE_FAILED = "charge_failed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELED = "subscription.canceled"
    INVOICE_PAID = "invoice.paid"
    INVOICE_FAILED = "invoice.failed"


class WebhookHandler:

    def __init__(self, payment_service):
        self.payment_service = payment_service
        self.logger = logging.getLogger(__name__)

    async def handle_incoming(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Route incoming webhook based on provider and event type"""
        provider = self._detect_provider(payload, headers)
        event_type = self._parse_event_type(provider, payload)

        handler = self._get_handler(provider, event_type)
        if not handler:
            self.logger.warning(f"No handler for {provider} event: {event_type}")
            return False

        try:
            await handler(payload)
            return True
        except Exception as e:
            self.logger.error(f"Failed handling {event_type} webhook: {str(e)}")
            return False

    def _detect_provider(self, payload: Dict[str, Any], headers: Dict[str, str]) -> str:
        if "stripe-signature" in headers:
            return "stripe"
        if "paddle-signature" in headers:
            return "paddle"
        return "unknown"

    def _parse_event_type(self, provider: str, payload: Dict[str, Any]) -> str:
        if provider == "stripe":
            return payload["type"]
        elif provider == "paddle":
            return payload["alert_name"]
        return "unknown"

    async def _handle_stripe_event(self, payload: Dict[str, Any]) -> None:
        event_type = payload["type"]
        data = payload["data"]["object"]

        if event_type == WebhookEventType.INVOICE_PAID.value:
            await self._handle_invoice_paid(data)
        elif event_type == WebhookEventType.CHARGE_FAILED.value:
            await self._handle_charge_failed(data)

    async def _handle_invoice_paid(self, invoice: Dict[str, Any]) -> None:
        """Process successful invoice payment"""
        pass

    async def _handle_charge_failed(self, charge: Dict[str, Any]) -> None:
        """Handle failed payment attempt"""
        pass
