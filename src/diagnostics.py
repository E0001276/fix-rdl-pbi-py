import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


class TeeStream:
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file

    def write(self, text):
        self.original.write(text)
        self.log_file.write(text)
        self.log_file.flush()
        return len(text)

    def flush(self):
        self.original.flush()
        self.log_file.flush()

    def isatty(self):
        return getattr(self.original, "isatty", lambda: False)()

    @property
    def encoding(self):
        return getattr(self.original, "encoding", "utf-8")


class DiagnosticLogger:
    """Detailed, replay-oriented execution and HTTP diagnostics.

    Authorization values are intentionally never persisted. Each HTTP request gets
    a directory containing request/response metadata, a replayable curl command,
    JSON bodies when present, and decoded InlineBase64 definition parts.
    """

    def __init__(self, log_root: Path):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = log_root / f"postdeploy_{stamp}"
        self.http_dir = self.run_dir / "http"
        self.http_dir.mkdir(parents=True, exist_ok=True)
        self.rdl_dir = self.run_dir / "rdl"
        self.rdl_dir.mkdir(parents=True, exist_ok=True)
        self.rpt_dir = self.run_dir / "rpt"
        self.rpt_dir.mkdir(parents=True, exist_ok=True)
        self.sm_dir = self.run_dir / "sm"
        self.sm_dir.mkdir(parents=True, exist_ok=True)
        self.execution_path = self.run_dir / "execution.log"
        self._execution_file = self.execution_path.open("w", encoding="utf-8", buffering=1)
        self._counter = 0
        self._method_counts = {"GET": 0, "POST": 0}
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = TeeStream(sys.stdout, self._execution_file)
        sys.stderr = TeeStream(sys.stderr, self._execution_file)
        self.write_manifest()

    def write_manifest(self):
        manifest = {
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "notes": [
                "Bearer tokens are REDACTED and are never written to disk.",
                "curl.txt uses a redacted access-token placeholder appropriate to each API.",
                "request.json and response.json contain API payloads for diagnosis.",
                "decoded-parts contains decoded InlineBase64 Fabric definition parts when present.",
            ],
        }
        (self.run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def request_count(self) -> int:
        return self._counter

    @property
    def request_counts(self) -> dict:
        return dict(self._method_counts)

    def close(self):
        if sys.stdout is not self._original_stdout:
            sys.stdout = self._original_stdout
        if sys.stderr is not self._original_stderr:
            sys.stderr = self._original_stderr
        if not self._execution_file.closed:
            self._execution_file.flush()
            self._execution_file.close()

    @staticmethod
    def safe_name(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "request")
        return value.strip("._")[:100] or "request"

    @staticmethod
    def redact_headers(headers: dict) -> dict:
        result = {}
        for key, value in (headers or {}).items():
            if key.lower() in {"authorization", "proxy-authorization"}:
                result[key] = "Bearer <REDACTED>"
            else:
                result[key] = value
        return result

    @staticmethod
    def quote_powershell_value(value: str) -> str:
        # curl.exe command suitable for PowerShell. Single quotes are uncommon in URLs;
        # escape them in PowerShell-compatible form if they occur.
        return "'" + str(value).replace("'", "''") + "'"

    def extract_inline_parts(self, data, destination: Path):
        if not isinstance(data, dict):
            return
        definition = data.get("definition")
        if not isinstance(definition, dict):
            return
        parts = definition.get("parts")
        if not isinstance(parts, list):
            return

        destination.mkdir(parents=True, exist_ok=True)
        index = []
        for number, part in enumerate(parts, start=1):
            if not isinstance(part, dict) or part.get("payloadType") != "InlineBase64":
                continue
            encoded = part.get("payload")
            if not isinstance(encoded, str) or not encoded:
                continue
            path = str(part.get("path") or f"part_{number}.bin")
            try:
                raw = base64.b64decode(encoded)
            except Exception as exc:
                index.append({"path": path, "decoded": False, "error": str(exc)})
                continue

            # Keep each Fabric part in a flat but identifiable file to avoid unsafe paths.
            filename = f"{number:03d}_{self.safe_name(path)}"
            target = destination / filename
            target.write_bytes(raw)
            index.append(
                {
                    "path": path,
                    "decoded": True,
                    "file": target.name,
                    "bytes": len(raw),
                }
            )

        if index:
            (destination / "index.json").write_text(
                json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def log_rdl(self, report_name: str, report_id: str, stage: str, xml_text: str):
        filename = (
            f"{self.safe_name(report_name)}_{self.safe_name(report_id)}_"
            f"{self.safe_name(stage)}.rdl"
        )
        target = self.rdl_dir / filename
        target.write_text(xml_text, encoding="utf-8")
        print(f"[RDL] {stage}: {target}")

    @staticmethod
    def safe_part_path(path: str, fallback: str) -> Path:
        """Return a safe relative path for one Fabric definition part."""
        raw = str(path or fallback).replace("\\", "/")
        pieces = []
        for piece in raw.split("/"):
            if not piece or piece in {".", ".."}:
                continue
            pieces.append(DiagnosticLogger.safe_name(piece))
        return Path(*pieces) if pieces else Path(fallback)

    def log_item_definition(
        self,
        item_kind: str,
        item_name: str,
        item_id: str,
        definition_response: dict,
    ):
        """Persist all InlineBase64 definition parts in decoded form.

        Reports are written under ``rpt`` and semantic models under ``sm``.
        The original Fabric part hierarchy is preserved inside a directory per
        item so PBIR/TMDL definitions remain easy to inspect and compare.
        """
        destinations = {
            "Report": (self.rpt_dir, "RPT"),
            "SemanticModel": (self.sm_dir, "SM"),
        }
        destination_info = destinations.get(item_kind)
        if destination_info is None:
            return

        root_dir, label = destination_info
        item_dir = root_dir / (
            f"{self.safe_name(item_name)}_{self.safe_name(item_id)}"
        )
        item_dir.mkdir(parents=True, exist_ok=True)

        parts = definition_response.get("definition", {}).get("parts", [])
        index = []
        for number, part in enumerate(parts, start=1):
            if not isinstance(part, dict):
                continue

            original_path = str(part.get("path") or f"part_{number}.bin")
            payload = part.get("payload")
            payload_type = part.get("payloadType")

            try:
                if payload_type == "InlineBase64":
                    raw = base64.b64decode(payload or "")
                elif isinstance(payload, str):
                    raw = payload.encode("utf-8")
                else:
                    raise ValueError(
                        f"Unsupported payload type: {payload_type or '(empty)'}"
                    )

                relative_path = self.safe_part_path(
                    original_path, f"part_{number}.bin"
                )
                target = item_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                index.append(
                    {
                        "path": original_path,
                        "decoded": True,
                        "file": relative_path.as_posix(),
                        "bytes": len(raw),
                    }
                )
            except Exception as exc:
                index.append(
                    {
                        "path": original_path,
                        "decoded": False,
                        "error": str(exc),
                    }
                )

        (item_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[{label}] Definition: {item_dir}")

    def log_http(self, method: str, url: str, request_headers: dict, request_json, response, token_label: str = "ACCESS_TOKEN"):
        self._counter += 1
        method_key = method.upper()
        self._method_counts[method_key] = self._method_counts.get(method_key, 0) + 1
        parsed_name = self.safe_name(url.split("?", 1)[0].rstrip("/").split("/")[-1])
        request_dir = self.http_dir / f"{self._counter:04d}_{method.upper()}_{parsed_name}"
        request_dir.mkdir(parents=True, exist_ok=True)

        safe_request_headers = self.redact_headers(dict(request_headers or {}))
        response_headers = dict(response.headers or {})

        meta = {
            "sequence": self._counter,
            "timestampUtc": datetime.now(timezone.utc).isoformat(),
            "method": method.upper(),
            "url": response.request.url if getattr(response, "request", None) else url,
            "requestHeaders": safe_request_headers,
            "responseStatus": response.status_code,
            "responseReason": response.reason,
            "responseHeaders": response_headers,
            "elapsedSeconds": getattr(response.elapsed, "total_seconds", lambda: None)(),
        }
        (request_dir / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

        request_body_file = None
        if request_json is not None:
            request_body_file = request_dir / "request.json"
            request_body_file.write_text(
                json.dumps(request_json, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.extract_inline_parts(request_json, request_dir / "decoded-request-parts")

        response_text = response.text or ""
        (request_dir / "response.txt").write_text(response_text, encoding="utf-8")
        try:
            response_json = response.json()
        except Exception:
            response_json = None
        if response_json is not None:
            (request_dir / "response.json").write_text(
                json.dumps(response_json, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.extract_inline_parts(response_json, request_dir / "decoded-response-parts")

        curl_lines = [
            "# Replay with curl.exe from PowerShell.",
            "f"# Replace <{token_label}> with a fresh token. The real token is never logged.",
            f"curl.exe --request {method.upper()} `",
            f"  --url {self.quote_powershell_value(meta['url'])} `",
            f"  --header 'Authorization: Bearer <{token_label}>' `",
            "  --header 'Content-Type: application/json'",
        ]
        if request_body_file is not None:
            curl_lines[-1] += " `"
            curl_lines.append("  --data-binary '@request.json'")
        (request_dir / "curl.txt").write_text("\n".join(curl_lines) + "\n", encoding="utf-8")

        # A compact HTTP trace in the main execution log makes it easy to correlate
        # application steps with the full request artifacts.
        print(f"[HTTP {self._counter:04d}] {method.upper()} {meta['url']}")
        print(f"[HTTP {self._counter:04d}] -> HTTP {response.status_code} {response.reason}")
        print(f"[HTTP {self._counter:04d}] curl/artifacts: {request_dir}")


def start_diagnostics(project_root: Path) -> DiagnosticLogger:
    return DiagnosticLogger(project_root / "log")
