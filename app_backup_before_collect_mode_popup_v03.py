"""
Correctr App Entry Point

Purpose:
    Starts Correctr.

Current behavior:
    1. User highlights text in another app.
    2. User presses the Correctr hotkey.
    3. Correctr copies the selected text.
    4. Correctr runs the controlled correction orchestrator.
    5. If collect mode is enabled, Correctr shows a popup before paste/save.
    6. If collect mode is disabled, Correctr pastes automatically and can
       optionally save an unreviewed raw event.

Current scope:
    Collect Mode Popup Review_v0.1.
"""

from __future__ import annotations

import threading
import time
from logging import Logger
from typing import Any

from correctr.collect_mode_dialog import CollectModeDecision, show_collect_mode_dialog
from correctr.clipboard_handler import ClipboardHandler, ClipboardOperationError
from correctr.config import AppConfig, get_default_config
from correctr.correction_orchestrator import correct_with_orchestration, get_event_source_for_result
from correctr.database import save_collect_mode_manual_correction, save_correction_event
from correctr.hotkey_runner import HotkeyRunner
from correctr.logging_utils import setup_logging


COLLECT_MODE_ACCEPTED_NOTE = "Accepted from collect mode."
COLLECT_MODE_REJECTED_NOTE = "Rejected from collect mode."
COLLECT_MODE_MANUAL_NOTE = "Manual correction from collect mode."
AUTO_MODE_UNREVIEWED_NOTE = "Saved from automatic hotkey workflow with collect mode off."


class CorrectrApp:
    """
    Coordinates the current Correctr hotkey correction workflow.

    The app delegates correction routing to correctr.correction_orchestrator.
    It stays responsible for clipboard IO and event logging policy.
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
        result = correct_with_orchestration(
            capture.selected_text,
            pipeline_mode=self.config.correction_pipeline_mode,
            ai_provider_mode=self.config.ai_provider,
        )

        if self.config.collect_mode_enabled:
            self._handle_collect_mode_result(
                result=result,
                original_clipboard_text=capture.original_clipboard_text,
            )
            return

        self._handle_auto_mode_result(
            result=result,
            original_clipboard_text=capture.original_clipboard_text,
        )

    def _handle_auto_mode_result(self, *, result: Any, original_clipboard_text: str) -> None:
        """
        Handles normal automatic paste behavior when collect mode is off.
        """
        self.clipboard_handler.paste_text(
            text_to_paste=result.corrected_text,
            original_clipboard_text=original_clipboard_text,
        )

        self.logger.info(
            "Correctr replacement pasted. Original length: %s chars. Corrected length: %s chars. Route: %s.",
            len(result.original_text),
            len(result.corrected_text),
            result.engine_version,
        )

        if not result.changed:
            self.logger.info("No correction event saved because final text did not change.")
            return

        if not self.config.save_events_when_collect_mode_off:
            self.logger.info(
                "No correction event saved because collect mode is off and automatic event saving is disabled."
            )
            return

        self._save_raw_unreviewed_correction_event(result, notes=AUTO_MODE_UNREVIEWED_NOTE)

    def _handle_collect_mode_result(self, *, result: Any, original_clipboard_text: str) -> None:
        """
        Handles trusted-data collection mode.

        In collect mode, Correctr does not paste or save until the user chooses
        to apply the proposed correction or manually edit it first. The popup
        path avoids forcing the user to switch to VS Code just to review data.
        """
        decision = self._get_collect_mode_decision(result)

        if decision.action == "apply":
            final_text = decision.corrected_text

            if final_text.strip() == "":
                self.logger.info("Collect mode apply ignored because corrected text was blank.")
                return

            if final_text == result.original_text:
                self.logger.info("Collect mode apply ignored because final text matched original text.")
                return

            time.sleep(self.config.after_collect_mode_dialog_close_delay_seconds)
            self.clipboard_handler.paste_text(
                text_to_paste=final_text,
                original_clipboard_text=original_clipboard_text,
            )

            if final_text == result.corrected_text and result.changed:
                event_id = self._save_accepted_collect_mode_event(result)
                self.logger.info("Applied proposed correction and saved trusted event ID %s.", event_id)
                return

            event_id = save_collect_mode_manual_correction(
                original_text=result.original_text,
                corrected_text=final_text,
                notes=COLLECT_MODE_MANUAL_NOTE,
            )
            self.logger.info("Applied edited correction and saved trusted manual event ID %s.", event_id)
            return

        if decision.action == "reject":
            if self.config.save_rejected_events_in_collect_mode and result.changed:
                event_id = self._save_rejected_collect_mode_event(result)
                self.logger.info("Rejected proposed correction and saved rejected raw event ID %s.", event_id)
                return

            self.logger.info("Collect mode correction rejected without saving.")
            return

        if decision.action == "skip":
            self.logger.info("Collect mode correction skipped without saving.")
            return

        self.logger.info("Collect mode correction quit/aborted without saving.")

    def _get_collect_mode_decision(self, result: Any) -> CollectModeDecision:
        """
        Gets the collect-mode review decision from popup or terminal UI.
        """
        if self.config.collect_mode_review_interface == "popup":
            return self._show_collect_mode_popup(result)

        self._print_collect_mode_review(result)
        choice = self._prompt_collect_mode_choice()

        if choice == "a":
            return CollectModeDecision(action="apply", corrected_text=result.corrected_text)

        if choice == "e":
            return CollectModeDecision(
                action="apply",
                corrected_text=self._prompt_manual_collect_mode_correction(),
            )

        if choice == "r":
            return CollectModeDecision(action="reject")

        if choice == "s":
            return CollectModeDecision(action="skip")

        return CollectModeDecision(action="quit")

    def _show_collect_mode_popup(self, result: Any) -> CollectModeDecision:
        """
        Shows the collect-mode popup and returns the user's decision.
        """
        return show_collect_mode_dialog(
            original_text=result.original_text,
            proposed_text=result.corrected_text,
            engine_version=result.engine_version,
            route_reasons=_collect_route_reasons(result.corrections),
            always_on_top=self.config.collect_mode_popup_always_on_top,
        )

    def _save_raw_unreviewed_correction_event(self, result: Any, *, notes: str) -> int:
        """
        Saves one changed correction event as unreviewed raw history.
        """
        try:
            source = get_event_source_for_result(result)
            event_id = save_correction_event(
                original_text=result.original_text,
                corrected_text=result.corrected_text,
                source=source,
                changed=result.changed,
                corrections=result.corrections,
                engine_version=result.engine_version,
                notes=notes,
                review_status="unreviewed",
            )
            self.logger.info("Raw correction event saved. Source: %s. Event id: %s", source, event_id)
            return event_id
        except Exception as error:
            self.logger.exception("Failed to save raw correction event: %s", error)
            raise

    def _save_accepted_collect_mode_event(self, result: Any) -> int:
        """
        Saves an accepted collect-mode correction as trusted.
        """
        try:
            source = get_event_source_for_result(result)
            event_id = save_correction_event(
                original_text=result.original_text,
                corrected_text=result.corrected_text,
                source=source,
                changed=result.changed,
                corrections=result.corrections,
                engine_version=result.engine_version,
                notes=COLLECT_MODE_ACCEPTED_NOTE,
                review_status="accepted",
                review_notes=COLLECT_MODE_ACCEPTED_NOTE,
            )
            self.logger.info("Collect mode accepted event saved. Source: %s. Event id: %s", source, event_id)
            return event_id
        except Exception as error:
            self.logger.exception("Failed to save collect mode accepted event: %s", error)
            raise

    def _save_rejected_collect_mode_event(self, result: Any) -> int:
        """
        Optionally saves a rejected collect-mode correction as rejected raw history.
        """
        try:
            source = get_event_source_for_result(result)
            event_id = save_correction_event(
                original_text=result.original_text,
                corrected_text=result.corrected_text,
                source=source,
                changed=result.changed,
                corrections=result.corrections,
                engine_version=result.engine_version,
                notes=COLLECT_MODE_REJECTED_NOTE,
                review_status="rejected",
                review_notes=COLLECT_MODE_REJECTED_NOTE,
            )
            self.logger.info("Collect mode rejected event saved. Source: %s. Event id: %s", source, event_id)
            return event_id
        except Exception as error:
            self.logger.exception("Failed to save collect mode rejected event: %s", error)
            raise

    @staticmethod
    def _print_collect_mode_review(result: Any) -> None:
        """
        Prints a compact terminal review prompt for collect mode.
        """
        print()
        print("=" * 72)
        print("Correctr collect mode review")
        print("=" * 72)
        print("Focus/click this terminal if your typing is still going into the other app.")
        print()
        print(f"Engine: {result.engine_version}")
        print(f"Changed: {result.changed}")
        print()
        print("Original:")
        print(result.original_text)
        print()
        print("Proposed correction:")
        print(result.corrected_text)
        print()

        route_reasons = _collect_route_reasons(result.corrections)
        if route_reasons:
            print("Route reasons:")
            for reason in route_reasons:
                print(f"- {reason}")
            print()

        print("Choose:")
        print("[A] accept proposed correction, paste it, save as trusted")
        print("[E] edit/fix correction, paste edited text, save as trusted manual")
        print("[R] reject proposed correction, do not paste")
        print("[S] skip, do not paste or save")
        print("[Q] quit this correction, do not paste or save")

    @staticmethod
    def _prompt_collect_mode_choice() -> str:
        """
        Prompts until the user enters a valid collect-mode command.
        """
        while True:
            choice = input("Choice: ").strip().lower()

            if choice in {"a", "e", "r", "s", "q"}:
                return choice

            print("Please enter A, E, R, S, or Q.")

    @staticmethod
    def _prompt_manual_collect_mode_correction() -> str:
        """
        Prompts for the intended correction.
        """
        print()
        print("Enter the intended corrected text.")
        print("Leave blank to cancel and save nothing.")
        return input("Intended correction: ").strip()


def _collect_route_reasons(corrections: list[dict[str, Any]]) -> list[str]:
    """
    Pulls unique route reason strings out of correction records for display.
    """
    route_reasons: list[str] = []

    for correction in corrections:
        raw_reasons = correction.get("route_reasons")

        if not isinstance(raw_reasons, list):
            continue

        for reason in raw_reasons:
            reason_text = str(reason)
            if reason_text not in route_reasons:
                route_reasons.append(reason_text)

    return route_reasons


def main() -> None:
    config = get_default_config()
    logger = setup_logging(config.log_level)

    logger.info("Starting Correctr Collect Mode Popup Review_v0.1.")
    logger.info("Activation hotkey: %s", config.activation_hotkey)
    logger.info("Stop hotkey: %s", config.stop_hotkey)
    logger.info("Correction pipeline mode: %s", config.correction_pipeline_mode)
    logger.info("AI provider mode: %s", config.ai_provider)
    logger.info("Collect mode enabled: %s", config.collect_mode_enabled)
    logger.info("Collect mode review interface: %s", config.collect_mode_review_interface)
    logger.info("Save events when collect mode off: %s", config.save_events_when_collect_mode_off)
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
