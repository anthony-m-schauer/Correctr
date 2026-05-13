"""
Smoke test for Correctr AI Context Correction_v0.3 Ollama provider.

Run from the project root:

    python scripts/ollama_provider_smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.config import get_default_config  # noqa: E402
from correctr.llm_engine import correct_with_ai_context  # noqa: E402

SAMPLE_TEXTS = [
    "shiuld this not also be abl eto fix this?",
    "These are testing mis takes for the app to hopefully fix. i ma making two sentences.",
]


def main() -> None:
    config = get_default_config()
    print("Correctr AI Context Correction_v0.3 Ollama Provider Smoke Test")
    print("----------------------------------------------------------------")
    print("Provider: ollama")
    print(f"Model: {config.ollama_model}")
    print(f"Base URL: {config.ollama_base_url}")
    print(f"Timeout seconds: {config.ollama_timeout_seconds}")
    print()
    for sample_text in SAMPLE_TEXTS:
        result = correct_with_ai_context(
            sample_text,
            provider_mode="ollama",
            ollama_base_url=config.ollama_base_url,
            ollama_model=config.ollama_model,
            ollama_timeout_seconds=config.ollama_timeout_seconds,
        )
        fallback_or_rejection = (
            result.engine_version.endswith(":fallback")
            or result.engine_version.endswith(":rejected")
            or any(record.get("reason") in {"ollama_fallback", "ai_output_rejected"} for record in result.corrections)
        )
        print("Original text:")
        print(result.original_text)
        print()
        print("Corrected text:")
        print(result.corrected_text)
        print()
        print("Changed:")
        print(result.changed)
        print()
        print("Engine version:")
        print(result.engine_version)
        print()
        print("Fallback or rejection happened:")
        print(fallback_or_rejection)
        print()
        print("Correction records:")
        if not result.corrections:
            print("No corrections made.")
        else:
            for record in result.corrections:
                print(f"- {record}")
        print("----------------------------------------------------------------")


if __name__ == "__main__":
    main()
