"""
NOWPayments Cryptocurrency Payment Gateway Engine
-------------------------------------------------
Handles:
- API connectivity to NOWPayments (https://api.nowpayments.io/v1)
- Generating hosted crypto payment invoices with 300+ coins (USDT TRC20/ERC20/BEP20, BTC, ETH, LTC, SOL, etc.)
- HMAC-SHA512 IPN (Instant Payment Notification) cryptographic signature verification
- Realtime payment status queries and blockchain confirmations
"""

import hashlib
import hmac
import json
import logging
import os
import requests
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_NOWPAYMENTS_API_KEY = "1W5AC5M-NYBM2NJ-NQN36B4-C338EH5"
DEFAULT_NOWPAYMENTS_IPN_SECRET = "c37ecbc1-6a5a-4e56-917b-3c77672a812b"
DEFAULT_NOWPAYMENTS_BASE_URL = "https://api.nowpayments.io/v1"


class NOWPaymentsGateway:
    """Gateway client for NOWPayments Crypto Processor."""

    @staticmethod
    def get_api_key() -> str:
        """Fetch NOWPayments API key."""
        return os.environ.get("NOWPAYMENTS_API_KEY") or DEFAULT_NOWPAYMENTS_API_KEY

    @staticmethod
    def get_ipn_secret() -> str:
        """Fetch NOWPayments IPN secret key for HMAC-SHA512 verification."""
        return os.environ.get("NOWPAYMENTS_IPN_SECRET") or os.environ.get("NOWPAYMENTS_PUBLIC_KEY") or DEFAULT_NOWPAYMENTS_IPN_SECRET

    @staticmethod
    def get_base_url() -> str:
        """Fetch NOWPayments API base URL."""
        return os.environ.get("NOWPAYMENTS_API_URL") or DEFAULT_NOWPAYMENTS_BASE_URL

    @classmethod
    def get_headers(cls) -> dict:
        """Standard HTTP request headers for NOWPayments API."""
        return {
            "x-api-key": cls.get_api_key(),
            "Content-Type": "application/json"
        }

    @classmethod
    def check_api_status(cls) -> bool:
        """Check if NOWPayments API is online and credentials are valid."""
        url = f"{cls.get_base_url()}/status"
        try:
            r = requests.get(url, headers=cls.get_headers(), timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"NOWPayments status check failed: {e}")
            return False

    @classmethod
    def create_invoice(
        cls,
        order_id: str,
        price_amount: float,
        price_currency: str = "usd",
        plan_name: str = "",
        callback_url: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Tuple[bool, dict]:
        """
        Create a hosted crypto invoice on NOWPayments.
        Customer can pay with any cryptocurrency (USDT, BTC, ETH, LTC, TRX, SOL, etc.).
        """
        url = f"{cls.get_base_url()}/invoice"
        description = f"TeleTips Pro - {plan_name or 'Subscription'} (${price_amount:.2f})"

        payload = {
            "price_amount": float(price_amount),
            "price_currency": price_currency.lower(),
            "order_id": order_id,
            "order_description": description,
            "ipn_callback_url": callback_url or "https://telegram-forwarder-pro.onrender.com/api/v1/payments/nowpayments-webhook",
            "success_url": success_url or "https://telegram-forwarder-pro.onrender.com/?payment=success",
            "cancel_url": cancel_url or "https://telegram-forwarder-pro.onrender.com/?payment=cancel",
        }

        try:
            logger.info(f"Creating NOWPayments invoice for order {order_id} (${price_amount})...")
            r = requests.post(url, headers=cls.get_headers(), json=payload, timeout=15)
            
            if r.status_code in (200, 201):
                data = r.json()
                logger.info(f"✅ NOWPayments invoice created successfully: ID {data.get('id')}, URL: {data.get('invoice_url')}")
                return True, {
                    "invoice_id": data.get("id"),
                    "invoice_url": data.get("invoice_url"),
                    "order_id": order_id,
                    "price_amount": data.get("price_amount"),
                    "price_currency": data.get("price_currency"),
                    "created_at": data.get("created_at"),
                }
            else:
                error_msg = r.text
                try:
                    err_json = r.json()
                    error_msg = err_json.get("message") or err_json.get("error") or r.text
                except Exception:
                    pass
                logger.error(f"❌ NOWPayments invoice creation failed ({r.status_code}): {error_msg}")
                return False, {"error": f"NOWPayments error ({r.status_code}): {error_msg}"}

        except Exception as e:
            logger.error(f"Exception creating NOWPayments invoice: {e}", exc_info=True)
            return False, {"error": f"Connection to NOWPayments failed: {str(e)}"}

    @classmethod
    def get_payment_status(cls, payment_id: str) -> Optional[dict]:
        """Query live payment status from NOWPayments."""
        url = f"{cls.get_base_url()}/payment/{payment_id}"
        try:
            r = requests.get(url, headers=cls.get_headers(), timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.error(f"Failed to fetch payment status for {payment_id}: {e}")
        return None

    @classmethod
    def verify_ipn_signature(cls, payload: dict, received_signature: str, secret: Optional[str] = None) -> bool:
        """
        Verify NOWPayments IPN signature (HMAC-SHA512 of sorted JSON payload).
        """
        if not received_signature:
            return False

        secret_key = (secret or cls.get_ipn_secret()).strip()
        if not secret_key:
            return False

        try:
            sorted_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            expected = hmac.new(
                secret_key.encode('utf-8'),
                sorted_json.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()

            return hmac.compare_digest(expected.lower(), received_signature.lower().strip())
        except Exception as e:
            logger.error(f"Error during NOWPayments signature verification: {e}")
            return False
