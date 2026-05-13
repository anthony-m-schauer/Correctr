"""
Local model evaluation script for Correctr.

Run from the project root:

    python scripts/local_model_evaluation.py

Default comparison models:
    - llama3.2:1b
    - llama3.2:3b
    - qwen2.5:3b

Optional:
    python scripts/local_model_evaluation.py --include-optional

Custom model list:
    python scripts/local_model_evaluation.py --models llama3.2:3b qwen2.5:3b

This script does not start the hotkey app and does not write to the database.
It runs fixed correction examples through local Ollama models using the current
Correctr AI provider interface, prompt contract, and output guardrails.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.config import get_default_config  # noqa: E402
from correctr.llm_engine import correct_with_ai_context  # noqa: E402


DEFAULT_MODELS = [
    "llama3.2:1b",
    "llama3.2:3b",
    "qwen2.5:3b",
]

OPTIONAL_MODELS = [
    "gemma3:4b",
]


@dataclass(frozen=True)
class EvaluationCase:
    """
    One model-quality test case.
    """

    label: str
    original: str
    ideal: str


EVALUATION_CASES = [
    EvaluationCase(
        label="A",
        original="shiuld this not also be abl eto fix this?",
        ideal="Should this not also be able to fix this?",
    ),
    EvaluationCase(
        label="B",
        original="Thsi here be th ethird pracitve testing sentenc we habe.",
        ideal="This here be the third practice testing sentence we have.",
    ),
    EvaluationCase(
        label="C",
        original="Snother testin gexample.",
        ideal="Another testing example.",
    ),
    EvaluationCase(
        label="D",
        original="These are testing mis takes for the app to hopefully fix. i ma making two sentences.",
        ideal="These are testing mistakes for the app to hopefully fix. I am making two sentences.",
    ),
    EvaluationCase(
        label="E",
        original="These are testig misakes for the app to hopfully fix. I am maknig two sentencs.",
        ideal="These are testing mistakes for the app to hopefully fix. I am making two sentences.",
    ),
    EvaluationCase(
        label="F",
        original="This is already correct.",
        ideal="This is already correct.",
    ),
]


def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Compare local Ollama models for Correctr typo correction quality.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Optional explicit model list, such as: --models llama3.2:3b qwen2.5:3b",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also evaluate optional models such as gemma3:4b.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Optional Ollama timeout override in seconds.",
    )
    return parser.parse_args()


def get_models_to_evaluate(args: argparse.Namespace) -> list[str]:
    """
    Resolves the model list for this evaluation run.
    """
    if args.models:
        return args.models

    models = list(DEFAULT_MODELS)

    if args.include_optional:
        models.extend(OPTIONAL_MODELS)

    return models


def main() -> None:
    args = parse_args()
    config = get_default_config()
    models = get_models_to_evaluate(args)
    timeout_seconds = args.timeout if args.timeout is not None else config.ollama_timeout_seconds

    print("Correctr Local Model Evaluation_v0.2")
    print("------------------------------------")
    print("Provider used for comparison: ollama")
    print(f"Ollama base URL: {config.ollama_base_url}")
    print(f"Timeout seconds: {timeout_seconds}")
    print("Models:")
    for model in models:
        print(f"- {model}")
    print()
    print("Rating guide:")
    print("GOOD = useful correction, meaning preserved, not too rewritten")
    print("PARTIAL = some fixes, but important mistakes remain")
    print("BAD = wrong, too rewritten, too slow, or not useful")
    print("FAIL = provider failed, fallback/rejection occurred, or model unavailable")
    print()

    for model in models:
        print("=" * 80)
        print(f"MODEL: {model}")
        print("=" * 80)

        for case_number, evaluation_case in enumerate(EVALUATION_CASES, start=1):
            start_time = time.perf_counter()
            result = correct_with_ai_context(
                evaluation_case.original,
                provider_mode="ollama",
                ollama_base_url=config.ollama_base_url,
                ollama_model=model,
                ollama_timeout_seconds=timeout_seconds,
            )
            elapsed_seconds = time.perf_counter() - start_time

            fallback_or_rejection = (
                result.engine_version.endswith(":fallback")
                or result.engine_version.endswith(":rejected")
                or any(
                    record.get("reason") in {"ollama_fallback", "ai_output_rejected"}
                    for record in result.corrections
                )
            )

            print(f"Case {evaluation_case.label} / {case_number}")
            print("Original:")
            print(evaluation_case.original)
            print()
            print("Ideal:")
            print(evaluation_case.ideal)
            print()
            print("Actual output:")
            print(result.corrected_text)
            print()
            print("Changed:")
            print(result.changed)
            print()
            print("Fallback/rejected:")
            print(fallback_or_rejection)
            print()
            print("Engine version:")
            print(result.engine_version)
            print()
            print("Elapsed seconds:")
            print(f"{elapsed_seconds:.3f}")
            print()
            print("Correction records:")
            if not result.corrections:
                print("No corrections made.")
            else:
                for record in result.corrections:
                    print(f"- {record}")
            print()
            print("Rating: ")
            print("Notes: ")
            print("-" * 80)

    print()
    print("Evaluation reminder:")
    print("- Choose the smallest model that gives acceptable correction quality and speed.")
    print("- Do not use a larger model just because it is larger.")
    print("- If a model is slow, over-rewrites, or ignores the prompt, it is not a good default.")
    print("- Do not make any model the permanent app default until quality and speed are acceptable.")


if __name__ == "__main__":
    main()
