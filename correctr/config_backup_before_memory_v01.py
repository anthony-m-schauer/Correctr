"""
Correctr Configuration

Purpose:
    Holds simple runtime settings for Correctr.

Current scope:
    Adds controlled dictionary-first AI-if-needed routing configuration and
    collect-mode controls while preserving existing hotkey, clipboard,
    AI/context, and Ollama settings.

Do not put secrets, API keys, database credentials, or local model files here.
Those belong in environment variables, local config, or future setup docs.
"""

from __future__ import annotations

from dataclasses import dataclass


AI_PROVIDER = "ollama"
ALLOWED_AI_PROVIDERS = {"disabled", "mock", "ollama", "openai"}

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT_SECONDS = 10.0

CORRECTION_PIPELINE_MODE = "dictionary_then_ai_if_needed"

# Collect mode proposal pipeline controls the draft shown in the review popup.
# This can be more aggressive than normal mode because the user approves or edits
# before Correctr pastes/saves anything.
COLLECT_MODE_PROPOSAL_PIPELINE_MODE = "dictionary_then_ai_always"
ALLOWED_CORRECTION_PIPELINE_MODES = {
    "dictionary_only",
    "dictionary_then_ai_if_unchanged",
    "dictionary_then_ai_always",
    "dictionary_then_ai_if_needed",
}

# Collect mode is the safest data-building mode.
# When enabled, Correctr asks before pasting/saving the correction.
COLLECT_MODE_ENABLED = True

# popup = small tkinter confirmation window.
# terminal = older VS Code/terminal prompt flow.
COLLECT_MODE_REVIEW_INTERFACE = "popup"
ALLOWED_COLLECT_MODE_REVIEW_INTERFACES = {"popup", "terminal"}

# Keep the popup above normal windows so it is easy to find during collection.
COLLECT_MODE_POPUP_ALWAYS_ON_TOP = True

# Small delay after the popup closes so Windows can return focus to the app
# where the text was originally selected before Correctr sends Ctrl+V.
AFTER_COLLECT_MODE_DIALOG_CLOSE_DELAY_SECONDS = 0.35

# When collect mode is off, Correctr can still paste automatic corrections.
# This flag controls whether those automatic corrections are saved as raw,
# unreviewed history. Keep False to avoid collecting noisy data during normal use.
SAVE_EVENTS_WHEN_COLLECT_MODE_OFF = False

# If True, collect-mode rejections are saved as rejected raw events. The default
# is False because the current QA goal is reducing database waste/noise.
SAVE_REJECTED_EVENTS_IN_COLLECT_MODE = False


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
    collect_mode_proposal_pipeline_mode: str = COLLECT_MODE_PROPOSAL_PIPELINE_MODE

    ollama_base_url: str = OLLAMA_BASE_URL
    ollama_model: str = OLLAMA_MODEL
    ollama_timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS

    collect_mode_enabled: bool = COLLECT_MODE_ENABLED
    collect_mode_review_interface: str = COLLECT_MODE_REVIEW_INTERFACE
    collect_mode_popup_always_on_top: bool = COLLECT_MODE_POPUP_ALWAYS_ON_TOP
    after_collect_mode_dialog_close_delay_seconds: float = AFTER_COLLECT_MODE_DIALOG_CLOSE_DELAY_SECONDS
    save_events_when_collect_mode_off: bool = SAVE_EVENTS_WHEN_COLLECT_MODE_OFF
    save_rejected_events_in_collect_mode: bool = SAVE_REJECTED_EVENTS_IN_COLLECT_MODE

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


def validate_collect_mode_review_interface(interface: str) -> str:
    """
    Validates the collect-mode review interface.
    """
    if interface not in ALLOWED_COLLECT_MODE_REVIEW_INTERFACES:
        allowed = ", ".join(sorted(ALLOWED_COLLECT_MODE_REVIEW_INTERFACES))
        raise ValueError(
            f"Unsupported collect mode review interface: {interface!r}. "
            f"Allowed interfaces: {allowed}"
        )

    return interface
