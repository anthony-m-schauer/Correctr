"""
Correctr App Entry Point

Purpose:
    Starts Correctr.

Current behavior:
    1. User highlights text in another app.
    2. User presses the Correctr hotkey.
    3. Correctr copies the selected text.
    4. Correctr applies local deterministic typo corrections.
    5. Correctr pastes the corrected result over the selected text.
    6. If the text changed, Correctr saves a dictionary correction event.

Current scope:
    Correction Event Integration_v0.1.
"""

from __future__ import annotations

import threading
import time
from logging import Logger

from correctr.clipboard_handler import ClipboardHandler, ClipboardOperationError
from correctr.config import AppConfig, get_default_config
from correctr.correction_engine import correct_text_detailed
from correctr.database import save_correction_event
from correctr.hotkey_runner import HotkeyRunner
from correctr.logging_utils import setup_logging


class CorrectrApp:
    """
    Coordinates the current Correctr hotkey correction workflow.

    The app uses the structured CorrectionResult internally so changed
    dictionary corrections can be saved to SQLite, while the user-facing
    behavior still only pastes corrected text.
    """

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger
        self.clipboard_handler = ClipboardHandler(config=config, logger=logger)
        self._workflow_lock = threading.Lock()

    def handle_hotkey_activation(self) -> None:
        """
        Starts the correction workflow in a separate thread.

        The hotkey listener should not be blocked by clipboard/paste/database work.
        A lock prevents multiple correction workflows from running at once.
        """
        workflow_thread = threading.Thread(
            target=self._run_workflow_safely,
            name="CorrectrWorkflowThread",
            daemon=True,
        )
        workflow_thread.start()

    def _run_workflow_safely(self) -> None:
        """
        Runs one correction attempt and catches errors so the hotkey listener
        can keep running after a failed attempt.
        """
        if not self._workflow_lock.acquire(blocking=False):
            self.logger.warning("Correction already in progress. Ignoring duplicate hotkey press.")
            return

        try:
            self._run_single_correction_workflow()
        except ClipboardOperationError as error:
            self.logger.error("Clipboard workflow failed: %s", error)
        except Exception as error:
            self.logger.exception("Unexpected Correctr workflow error: %s", error)
        finally:
            self._workflow_lock.release()

    def _run_single_correction_workflow(self) -> None:
        """
        Executes one correction workflow.
        """
        time.sleep(self.config.hotkey_release_delay_seconds)

        capture = self.clipboard_handler.copy_selected_text()
        result = correct_text_detailed(capture.selected_text)

        self.clipboard_handler.paste_text(
            text_to_paste=result.corrected_text,
            original_clipboard_text=capture.original_clipboard_text,
        )

        self.logger.info(
            "Correctr replacement pasted. Original length: %s chars. Corrected length: %s chars.",
            len(result.original_text),
            len(result.corrected_text),
        )

        if result.changed:
            self._save_dictionary_event(result)
        else:
            self.logger.info("No dictionary correction event saved because text did not change.")

    def _save_dictionary_event(self, result) -> None:
        """
        Saves a changed dictionary correction event.

        Database errors are logged but do not crash the hotkey listener.
        """
        try:
            event_id = save_correction_event(
                original_text=result.original_text,
                corrected_text=result.corrected_text,
                source="dictionary",
                changed=result.changed,
                corrections=result.corrections,
                engine_version=result.engine_version,
                notes="Saved from hotkey app workflow.",
            )
            self.logger.info("Dictionary correction event saved. Event id: %s", event_id)
        except Exception as error:
            self.logger.exception("Failed to save dictionary correction event: %s", error)


def main() -> None:
    config = get_default_config()
    logger = setup_logging(config.log_level)

    logger.info("Starting Correctr Correction Event Integration_v0.1.")
    logger.info("Activation hotkey: %s", config.activation_hotkey)
    logger.info("Stop hotkey: %s", config.stop_hotkey)
    logger.info("Test first in Notepad with simple highlighted text.")

    app = CorrectrApp(config=config, logger=logger)

    runner = HotkeyRunner(
        activation_hotkey=config.activation_hotkey,
        stop_hotkey=config.stop_hotkey,
        on_activate=app.handle_hotkey_activation,
        logger=logger,
    )

    runner.run()


if __name__ == "__main__":
    main()
