"""
Correctr Hotkey Runner

Purpose:
    Listens for global hotkeys and triggers the Correctr workflow.

Current scope:
    - Start listener.
    - Trigger callback when activation hotkey is pressed.
    - Stop listener when stop hotkey is pressed.

This module does not know anything about correction logic or clipboard logic.
"""

from __future__ import annotations

from collections.abc import Callable
from logging import Logger

from pynput import keyboard


class HotkeyRunner:
    """
    Small wrapper around pynput's global hotkey listener.
    """

    def __init__(
        self,
        activation_hotkey: str,
        stop_hotkey: str,
        on_activate: Callable[[], None],
        logger: Logger,
    ) -> None:
        self.activation_hotkey_text = activation_hotkey
        self.stop_hotkey_text = stop_hotkey
        self.on_activate = on_activate
        self.logger = logger

        self._listener: keyboard.Listener | None = None

        self._activation_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(activation_hotkey),
            self._handle_activation,
        )
        self._stop_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(stop_hotkey),
            self.stop,
        )

    def run(self) -> None:
        """
        Starts the global hotkey listener and blocks until stopped.
        """
        self.logger.info("Hotkey listener started.")
        self.logger.info("Press %s to run Correctr.", self.activation_hotkey_text)
        self.logger.info("Press %s to stop Correctr.", self.stop_hotkey_text)

        try:
            with keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            ) as listener:
                self._listener = listener
                listener.join()
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt received. Stopping Correctr.")
        finally:
            self.logger.info("Correctr hotkey listener stopped.")

    def stop(self) -> None:
        """
        Stops the listener.

        This can be triggered by the stop hotkey or by Ctrl+C in the terminal.
        """
        self.logger.info("Stop hotkey received.")
        if self._listener is not None:
            self._listener.stop()

    def _handle_activation(self) -> None:
        """
        Runs when the activation hotkey is detected.
        """
        self.logger.info("Activation hotkey received.")
        self.on_activate()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        canonical_key = self._canonical_key(key)
        self._activation_hotkey.press(canonical_key)
        self._stop_hotkey.press(canonical_key)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        canonical_key = self._canonical_key(key)
        self._activation_hotkey.release(canonical_key)
        self._stop_hotkey.release(canonical_key)

    def _canonical_key(self, key: keyboard.Key | keyboard.KeyCode) -> keyboard.Key | keyboard.KeyCode:
        """
        Normalizes left/right modifier keys so combinations like Ctrl+Alt+C
        are detected reliably.
        """
        if self._listener is None:
            return key

        return self._listener.canonical(key)
