import asyncio
import logging
import random
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("websync-worker.transport")


class TransportError(Exception):
    """Temporary networking or server error that may be retried."""
    pass


class AuthenticationError(Exception):
    """Fatal authentication failure (invalid credentials or token revoked)."""
    pass


class RegistrationError(Exception):
    """Validation or configuration error during registration."""
    pass


def calculate_backoff(attempt: int, base: float = 1.0, max_cap: float = 30.0) -> float:
    """Calculate exponential backoff with jitter."""
    delay = min(max_cap, base * (2 ** attempt))
    # Full jitter
    return random.uniform(0.5, delay)


class CoordinatorTransport:
    """Outbound HTTP transport client communicating with the WebSync AI Coordinator."""

    def __init__(self, base_url: str, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "CoordinatorTransport":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            headers={"User-Agent": "WebSync-Worker-Agent/0.3.0"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Transport client is not open. Use 'async with' context.")
        return self._client

    async def register(
        self, payload: Dict[str, Any], pre_shared_token: str
    ) -> Dict[str, Any]:
        """Submit worker registration request to coordinator."""
        url = "/api/v1/workers/register"
        headers = {
            "Content-Type": "application/json",
            "X-Worker-Auth-Token": pre_shared_token,
        }

        try:
            response = await self.client.post(url, json=payload, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            raise TransportError(f"Failed to connect to coordinator at {self.base_url}: {str(e)}") from e

        if response.status_code == 201:
            return response.json()
        elif response.status_code in (401, 403):
            raise AuthenticationError(
                f"Registration rejected (HTTP {response.status_code}): {response.text}"
            )
        elif response.status_code == 409:
            raise RegistrationError(
                f"Worker ID conflict (HTTP 409): {response.text}"
            )
        elif response.status_code == 422:
            raise RegistrationError(
                f"Registration payload validation failed (HTTP 422): {response.text}"
            )
        else:
            raise TransportError(
                f"Coordinator returned unexpected HTTP {response.status_code}: {response.text}"
            )

    async def send_heartbeat(
        self, payload: Dict[str, Any], worker_jwt: str
    ) -> Dict[str, Any]:
        """Submit periodic hardware telemetry heartbeat."""
        url = "/api/v1/workers/heartbeat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {worker_jwt}",
        }

        try:
            response = await self.client.post(url, json=payload, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            raise TransportError(f"Heartbeat network delivery failed: {str(e)}") from e

        if response.status_code == 200:
            return response.json()
        elif response.status_code in (401, 403):
            raise AuthenticationError(
                f"Worker session expired or revoked (HTTP {response.status_code}): {response.text}"
            )
        elif response.status_code == 404:
            raise RegistrationError(
                f"Worker not found on coordinator (HTTP 404). Re-registration required."
            )
        else:
            raise TransportError(
                f"Heartbeat rejected with HTTP {response.status_code}: {response.text}"
            )

    async def disconnect(self, worker_id: str, worker_jwt: Optional[str] = None) -> None:
        """Notify coordinator of voluntary worker disconnection."""
        url = f"/api/v1/workers/{worker_id}/disconnect"
        headers = {}
        if worker_jwt:
            headers["Authorization"] = f"Bearer {worker_jwt}"

        try:
            await self.client.post(url, headers=headers)
            logger.info("Sent clean disconnection notice to coordinator.")
        except Exception as e:
            logger.debug("Failed to send disconnect notice (non-fatal): %s", str(e))
