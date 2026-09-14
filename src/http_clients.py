import time
from urllib.parse import urljoin

import requests


class ApiClient:
    def __init__(self, base_url: str, token: str, diagnostics=None, token_label: str = "ACCESS_TOKEN"):
        self.base_url = base_url.rstrip("/") + "/"
        self.diagnostics = diagnostics
        self.token_label = token_label
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

    @staticmethod
    def _raise_for_status_with_body(response):
        if response.ok:
            return

        try:
            body = response.json()
        except Exception:
            body = response.text

        raise requests.HTTPError(
            f"{response.status_code} {response.reason} for {response.url}; "
            f"response={body}",
            response=response,
        )

    def _log(self, method: str, url: str, request_json, response):
        if self.diagnostics is not None:
            self.diagnostics.log_http(
                method=method,
                url=url,
                request_headers=dict(self.session.headers),
                request_json=request_json,
                response=response,
                token_label=self.token_label,
            )

    def get(self, path_or_url: str, params=None):
        url = self._url(path_or_url)
        response = self.session.get(url, params=params)
        self._log("GET", url, None, response)
        self._raise_for_status_with_body(response)
        return response

    def post(self, path_or_url: str, json=None, params=None):
        url = self._url(path_or_url)
        response = self.session.post(url, json=json, params=params)
        self._log("POST", url, json, response)
        self._raise_for_status_with_body(response)
        return response

    @staticmethod
    def _fabric_operation_path(operation_id: str) -> str:
        return f"operations/{operation_id}"

    @staticmethod
    def _fabric_result_path(operation_id: str) -> str:
        return f"operations/{operation_id}/result"

    def wait_for_lro_completion(self, response, timeout_seconds: int = 300):
        if response.status_code != 202:
            return

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
            # Prefer the canonical Fabric API operation endpoint. Some Fabric responses
            # include a regional wabi-paas Location; using x-ms-operation-id keeps all
            # polling on https://api.fabric.microsoft.com/v1.
            state_ref = (
                self._fabric_operation_path(operation_id)
                if operation_id
                else location
            )
            state_response = self.get(state_ref)
            state = state_response.json()
            status = state.get("status")

            if status == "Succeeded":
                return

            if status in {"Failed", "Cancelled", "Canceled"}:
                raise RuntimeError(
                    f"Fabric operation {operation_id or ''} finished with status {status}: {state}"
                )

            retry_after = int(state_response.headers.get("Retry-After", "2"))

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
            state_ref = (
                self._fabric_operation_path(operation_id)
                if operation_id
                else location
            )
            state_response = self.get(state_ref)
            state = state_response.json()
            status = state.get("status")

            if status == "Succeeded":
                if operation_id:
                    return self.get(self._fabric_result_path(operation_id)).json()
                result_url = state_response.headers.get("Location")
                if not result_url:
                    raise RuntimeError(
                        "Fabric LRO succeeded but no operation id or result Location was available."
                    )
                return self.get(result_url).json()

            if status in {"Failed", "Cancelled", "Canceled"}:
                raise RuntimeError(
                    f"Fabric operation {operation_id or ''} finished with status {status}: {state}"
                )

            retry_after = int(state_response.headers.get("Retry-After", "2"))
