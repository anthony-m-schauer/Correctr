"""
Correctr Configuration

Purpose:
    Holds simple runtime settings for Correctr.

Current scope:
    Adds controlled AI/context provider configuration while preserving the
    existing hotkey and clipboard settings.

Do not put secrets, API keys, database credentials, or local model files here.
Those belong in environment variables, local config, or future setup docs.
"""

from __future__ import annotations

from dataclasses import dataclass


AI_PROVIDER = "mock"
ALLOWED_AI_PROVIDERS = {"disabled", "mock", "ollama", "openai"}


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

    The current implemented provider is mock. Other values are reserved for
    future work and should not be called until implemented.
    """
    if provider not in ALLOWED_AI_PROVIDERS:
        allowed = ", ".join(sorted(ALLOWED_AI_PROVIDERS))
        raise ValueError(f"Unsupported AI provider: {provider!r}. Allowed providers: {allowed}")

    return provider
