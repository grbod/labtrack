"""Extraction providers for results-import PDFs."""

from __future__ import annotations

import base64
import json
import re
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, Optional

import requests

from app.config import settings


class ExtractionConfigurationError(RuntimeError):
    """Raised when extraction provider configuration is incomplete."""


class ExtractionProvider(ABC):
    """Provider interface for lab-result extraction."""

    @abstractmethod
    def extract(self, pdf_bytes: bytes, text: str, filename: str) -> Dict[str, Any]:
        """Return universal extraction JSON."""


class MockExtractionProvider(ExtractionProvider):
    """Deterministic local provider used in tests and development."""

    def extract(self, pdf_bytes: bytes, text: str, filename: str) -> Dict[str, Any]:
        source = f"{filename}\n{text}"
        identifiers = []
        for label, pattern in (
            (
                "reference_number",
                r"(?:ref(?:erence)?|sample)\s*[:#-]?\s*([A-Z0-9-]{4,})",
            ),
            ("lot_number", r"(?:lot|batch)\s*[:#-]?\s*([A-Z0-9-]{3,})"),
        ):
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                identifiers.append(
                    {"type": label, "value": match.group(1).upper(), "confidence": 0.9}
                )

        rows = []
        known_tests = [
            "Total Plate Count",
            "Yeast & Mold",
            "Escherichia coli",
            "Salmonella spp.",
            "Lead",
            "Arsenic",
            "Cadmium",
            "Mercury",
        ]
        for index, test_name in enumerate(known_tests, start=1):
            pattern = re.compile(
                rf"{re.escape(test_name)}[^\n\r:]*[:\s]\s*([<>]?\s?[A-Za-z0-9.,/ -]+)",
                re.IGNORECASE,
            )
            match = pattern.search(source)
            if not match:
                continue
            rows.append(
                {
                    "row_id": f"row-{index}",
                    "test_name_raw": test_name,
                    "result_value_raw": match.group(1).strip(),
                    "unit_raw": None,
                    "limit_raw": None,
                    "confidence": 0.88,
                    "metadata": {"provider": "mock"},
                }
            )

        return {
            "identifiers": identifiers,
            "lab_name": "Mock Lab",
            "date_tested": date.today().isoformat(),
            "report_date": date.today().isoformat(),
            "received_date": None,
            "rows": rows,
            "warnings": (
                [] if rows else ["No known result rows found in mock extraction"]
            ),
        }


class OpenRouterExtractionProvider(ExtractionProvider):
    """OpenRouter chat-completions provider with structured JSON output."""

    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def extract(self, pdf_bytes: bytes, text: str, filename: str) -> Dict[str, Any]:
        if not settings.openrouter_api_key:
            raise ExtractionConfigurationError(
                "OPENROUTER_API_KEY is required for results importer extraction"
            )

        try:
            return self._call_openrouter(pdf_bytes, text, filename, include_pdf=True)
        except requests.HTTPError as exc:
            if text.strip() and self._is_pdf_input_rejection(exc):
                return self._call_openrouter(
                    pdf_bytes, text, filename, include_pdf=False
                )
            raise

    def _call_openrouter(
        self,
        pdf_bytes: bytes,
        text: str,
        filename: str,
        include_pdf: bool,
    ) -> Dict[str, Any]:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Extract lab-result data from this PDF into the requested JSON "
                    "schema. Do not choose the authoritative app lot. Preserve printed "
                    "result text exactly, including commas and less-than signs. Include "
                    "row sample_id, reference_number, lot_number, sublot_number, or "
                    "batch_number fields when printed per row. For metals, preserve names like Pb/Lead, As/Arsenic, "
                    "Cd/Cadmium, and Hg/Mercury in test_name_raw. When a metals table "
                    "prints both a per-gram (micrograms/gram, ug/g) and a per-serving "
                    "(micrograms/serving, ug/srv) column, put the per-serving value in "
                    "per_serving and the per-gram value in result_value_raw/unit_raw. "
                    "Never drop <LOD, <LOQ, or other less-than values. Capture the "
                    "serving size text when present.\n\n"
                    f"Filename: {filename}\n\nExtracted text:\n{text[:20000]}"
                ),
            }
        ]
        if include_pdf:
            encoded = base64.b64encode(pdf_bytes).decode("ascii")
            content.append(
                {
                    "type": "file",
                    "file": {
                        "filename": filename,
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    },
                }
            )

        payload = {
            "model": settings.openrouter_model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "lab_result_extraction",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "identifiers": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "value": {"type": "string"},
                                        "confidence": {"type": "number"},
                                    },
                                    "required": ["type", "value", "confidence"],
                                    "additionalProperties": False,
                                },
                            },
                            "lab_name": {"type": ["string", "null"]},
                            "date_tested": {"type": ["string", "null"]},
                            "report_date": {"type": ["string", "null"]},
                            "received_date": {"type": ["string", "null"]},
                            "rows": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "row_id": {"type": "string"},
                                        "test_name_raw": {"type": "string"},
                                        "result_value_raw": {
                                            "type": ["string", "null"]
                                        },
                                        "unit_raw": {"type": ["string", "null"]},
                                        "limit_raw": {"type": ["string", "null"]},
                                        "sample_id": {"type": ["string", "null"]},
                                        "reference_number": {
                                            "type": ["string", "null"]
                                        },
                                        "lot_number": {"type": ["string", "null"]},
                                        "sublot_number": {"type": ["string", "null"]},
                                        "batch_number": {"type": ["string", "null"]},
                                        "per_serving": {"type": ["string", "null"]},
                                        "lod": {"type": ["string", "null"]},
                                        "loq": {"type": ["string", "null"]},
                                        "confidence": {"type": "number"},
                                    },
                                    "required": [
                                        "row_id",
                                        "test_name_raw",
                                        "result_value_raw",
                                        "unit_raw",
                                        "limit_raw",
                                        "confidence",
                                    ],
                                    "additionalProperties": True,
                                },
                            },
                            "warnings": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["identifiers", "lab_name", "rows", "warnings"],
                        "additionalProperties": False,
                    },
                },
            },
        }
        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://labtrack.bodytools.work",
                "X-Title": "LabTrack Results Importer",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content_text = data["choices"][0]["message"]["content"]
        parsed = json.loads(content_text)
        parsed["_usage_metadata"] = data.get("usage")
        parsed["_model"] = data.get("model") or settings.openrouter_model
        return parsed

    def _is_pdf_input_rejection(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        if response is None or response.status_code not in {400, 413, 415, 422}:
            return False
        body = (response.text or "").lower()
        return any(
            token in body for token in ["pdf", "file", "base64", "unsupported", "input"]
        )


def get_extraction_provider() -> ExtractionProvider:
    if settings.ai_provider.lower() == "mock":
        return MockExtractionProvider()
    return OpenRouterExtractionProvider()
