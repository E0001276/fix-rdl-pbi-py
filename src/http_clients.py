import time
from urllib.parse import urljoin

import requests


class ApiClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.base_url, path_or_url.lstrip("/"))

    def get(self, path_or_url: str, params=None):
        response = self.session.get(self._url(path_or_url), params=params)
        response.raise_for_status()
        return response

    def post(self, path_or_url: str, json=None, params=None):
        response = self.session.post(
            self._url(path_or_url), json=json, params=params
        )
        response.raise_for_status()
        return response

    def get_json_lro_result(self, response, timeout_seconds: int = 300):
        """Return JSON for an immediate response or poll a Fabric LRO to completion."""
        if response.status_code != 202:
            return response.json()

        operation_id = response.headers.get("x-ms-operation-id")
        location = response.headers.get("Location")
        if not operation_id and not location:
            raise RuntimeError(
                "Fabric returned HTTP 202 without x-ms-operation-id or Location."
            )

        started = time.monotonic()
        retry_after = int(response.headers.get("Retry-After", "2"))

        while True:
            if time.monotonic() - started > timeout_seconds:
                raise TimeoutError(
                    f"Fabric operation did not finish within {timeout_seconds} seconds."
                )

            time.sleep(max(1, retry_after))
            state_url = location or f"operations/{operation_id}"
            state_response = self.get(state_url)
            state = state_response.json()
            status = state.get("status")

            if status == "Succeeded":
                result_url = state_response.headers.get("Location")
                if not result_url or not result_url.rstrip("/").endswith("/result"):
                    result_url = f"operations/{operation_id}/result"
                return self.get(result_url).json()

            if status in {"Failed", "Cancelled", "Canceled"}:
                raise RuntimeError(
                    f"Fabric operation {operation_id or ''} finished with status {status}: {state}"
                )

            retry_after = int(state_response.headers.get("Retry-After", "2"))
            location = state_response.headers.get("Location", location)
