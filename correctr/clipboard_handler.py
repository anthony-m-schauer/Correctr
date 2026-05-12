"""
Correctr Clipboard Handler

Purpose:
    Handles the physical selected-text copy and paste-back workflow.

Current proof-of-concept behavior:
    - Save current text clipboard content.
    - Temporarily place a sentinel value on the clipboard.
    - Send Ctrl+C to copy selected text.
    - Read copied selected text from the clipboard.
    - Place corrected text on the clipboard.
    - Send Ctrl+V to paste over the active selection.
    - Restore the original text clipboard content when possible.

Limitations:
    - Text clipboard only.
    - Restore is best-effort.
    - Clipboard timing may vary by app.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from logging import Logger

import pyautogui
import pyperclip

from correctr.config import AppConfig


class ClipboardOperationError(RuntimeError):
    """
    Raised when Correctr cannot safely complete the clipboard operation.
    """


@dataclass(frozen=True)
class ClipboardCapture:
    """
    Selected text captured from the active app, plus the original clipboard text.
    """

    selected_text: str
    original_clipboard_text: str


class ClipboardHandler:
    """
    Copies selected text and pastes replacement text.

    This class intentionally avoids any correction logic. It only handles
    clipboard and keyboard automation.
    """

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger

        # pyautogui's failsafe raises an exception if the mouse is moved to
        # the upper-left corner. Keeping it enabled is safer during testing.
        pyautogui.FAILSAFE = True

    def copy_selected_text(self) -> ClipboardCapture:
        """
        Copies the currently highlighted text from the active app.

        Returns:
            ClipboardCapture containing the selected text and original clipboard text.

        Raises:
            ClipboardOperationError if selected text cannot be captured.
        """
        original_clipboard_text = self._read_clipboard_text_safely()

        sentinel = self._make_clipboard_sentinel()
        self._write_clipboard_text_safely(sentinel)

        time.sleep(self.config.before_copy_delay_seconds)

        self.logger.info("Sending Ctrl+C to copy selected text.")
        pyautogui.hotkey("ctrl", "c")

        selected_text = self._wait_for_clipboard_change(sentinel=sentinel)

        if selected_text == "":
            self._restore_original_clipboard(original_clipboard_text)
            raise ClipboardOperationError(
                "No selected text was copied. Make sure text is highlighted before pressing the hotkey."
            )

        if selected_text == sentinel:
            self._restore_original_clipboard(original_clipboard_text)
            raise ClipboardOperationError(
                "Clipboard did not change after Ctrl+C. The active app may not allow copying, or no text was selected."
            )

        self.logger.info("Selected text captured. Length: %s chars.", len(selected_text))

        return ClipboardCapture(
            selected_text=selected_text,
            original_clipboard_text=original_clipboard_text,
        )

    def paste_text(self, text_to_paste: str, original_clipboard_text: str) -> None:
        """
        Pastes replacement text over the currently selected text.

        Args:
            text_to_paste:
                The corrected or placeholder text to paste.
            original_clipboard_text:
                The text clipboard content from before Correctr started.
        """
        if text_to_paste == "":
            raise ClipboardOperationError("Refusing to paste empty replacement text.")

        self._write_clipboard_text_safely(text_to_paste)

        time.sleep(self.config.before_paste_delay_seconds)

        self.logger.info("Sending Ctrl+V to paste replacement text.")
        pyautogui.hotkey("ctrl", "v")

        time.sleep(self.config.after_paste_delay_seconds)

        if self.config.restore_original_clipboard_after_paste:
            self._restore_original_clipboard(original_clipboard_text)

    def _wait_for_clipboard_change(self, sentinel: str) -> str:
        """
        Polls the clipboard until it changes away from the sentinel or times out.
        """
        deadline = time.monotonic() + self.config.clipboard_poll_timeout_seconds

        while time.monotonic() < deadline:
            current_text = self._read_clipboard_text_safely()

            if current_text != sentinel:
                return current_text

            time.sleep(self.config.clipboard_poll_interval_seconds)

        return sentinel

    def _restore_original_clipboard(self, original_clipboard_text: str) -> None:
        """
        Best-effort restoration of the original text clipboard.
        """
        try:
            self._write_clipboard_text_safely(original_clipboard_text)
            self.logger.info("Original text clipboard restored.")
        except ClipboardOperationError as error:
            self.logger.warning("Could not restore original clipboard text: %s", error)

    @staticmethod
    def _make_clipboard_sentinel() -> str:
        """
        Creates a unique marker used to detect whether Ctrl+C changed the clipboard.
        """
        return f"__CORRECTR_CLIPBOARD_SENTINEL_{uuid.uuid4()}__"

    @staticmethod
    def _read_clipboard_text_safely() -> str:
        """
        Reads text from the clipboard.

        pyperclip only handles text clipboard content. If the clipboard contains
        non-text content, this may return an empty string or raise an error.
        """
        try:
            clipboard_text = pyperclip.paste()
        except pyperclip.PyperclipException as error:
            raise ClipboardOperationError(f"Could not read clipboard text: {error}") from error

        if clipboard_text is None:
            return ""

        return str(clipboard_text)

    @staticmethod
    def _write_clipboard_text_safely(text: str) -> None:
        """
        Writes text to the clipboard.
        """
        try:
            pyperclip.copy(text)
        except pyperclip.PyperclipException as error:
            raise ClipboardOperationError(f"Could not write clipboard text: {error}") from error
