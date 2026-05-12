"""
Correctr Configuration

Purpose:
    Holds simple runtime settings for Correctr.

Current scope:
    Adds controlled correction pipeline routing configuration while preserving
    existing hotkey, clipboard, and AI/context provider settings.

Do not put secrets, API keys, database credentials, or local model files here.
Those belong in environment variables, local config, or future setup docs.
"""

from __future__ import annotations

from dataclasses import dataclass


AI_PROVIDER = "mock"
ALLOWED_AI_PROVIDERS = {"disabled", "mock", "ollama", "openai"}

CORRECTION_PIPELINE_MODE = "dictionary_then_ai_if_unchanged"
ALLOWED_CORRECTION_PIPELINE_MODES = {
    "dictionary_only",
    "dictionary_then_ai_if_unchanged",
    "dictionary_then_ai_always",
}


@dataclass(frozen=True)
class AppConfig:
    """
    Runtime settings for Correctr.

    Hotkey format follows pynput's HotKey syntax.
    Examples:
        <ctrl>+<alt>+c
        <ctrl>+<shift>+space
    """

    activation_hotkey: str = "<ctrl>+<alt>+c"
    stop_hotkey: str = "<ctrl>+<alt>+q"

    hotkey_release_delay_seconds: float = 0.35

    clipboard_poll_timeout_seconds: float = 1.5
    clipboard_poll_interval_seconds: float = 0.05

    before_copy_delay_seconds: float = 0.05
    before_paste_delay_seconds: float = 0.05
    after_paste_delay_seconds: float = 0.25

    restore_original_clipboard_after_paste: bool = True

    ai_provider: str = AI_PROVIDER
    correction_pipeline_mode: str = CORRECTION_PIPELINE_MODE

    log_level: str = "INFO"


def get_default_config() -> AppConfig:
    """
    Returns the default config for Correctr.

    This function exists so later versions can load from a config file,
    environment variables, or a settings UI without changing app.py.
    """
    return AppConfig()


def validate_ai_provider(provider: str) -> str:
    """
    Validates the configured AI/context provider.

    The current implemented providers are mock and disabled. Other values are
    reserved for future work and should not be called until implemented.
    """
    if provider not in ALLOWED_AI_PROVIDERS:
        allowed = ", ".join(sorted(ALLOWED_AI_PROVIDERS))
        raise ValueError(f"Unsupported AI provider: {provider!r}. Allowed providers: {allowed}")

    return provider


def validate_correction_pipeline_mode(mode: str) -> str:
    """
    Validates the configured correction pipeline mode.
    """
    if mode not in ALLOWED_CORRECTION_PIPELINE_MODES:
        allowed = ", ".join(sorted(ALLOWED_CORRECTION_PIPELINE_MODES))
        raise ValueError(f"Unsupported correction pipeline mode: {mode!r}. Allowed modes: {allowed}")

    return mode
