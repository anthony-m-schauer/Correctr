"""
Correctr Collect Mode Popup Dialog

Purpose:
    Provides a small local popup used by collect mode so the user can review,
    edit, apply, or reject a correction without switching back to VS Code.

Current scope:
    Collect Mode Popup Review_v0.1.

This module uses tkinter from the Python standard library. It does not add a
polished GUI, tray app, or suggestion UI. It is a practical confirmation dialog
for building cleaner trusted correction data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CollectModeAction = Literal["apply", "reject", "skip", "quit"]


@dataclass(frozen=True)
class CollectModeDecision:
    """
    User decision from the collect-mode popup.

    action:
        apply, reject, skip, or quit.
    corrected_text:
        Text to paste/save when action is apply. This can be the proposed
        correction unchanged or a user-edited manual correction.
    """

    action: CollectModeAction
    corrected_text: str = ""


def show_collect_mode_dialog(
    *,
    original_text: str,
    proposed_text: str,
    engine_version: str = "",
    route_reasons: list[str] | None = None,
    always_on_top: bool = True,
) -> CollectModeDecision:
    """
    Shows a modal local popup for collect-mode review.

    The proposed correction is editable. If the user edits it and clicks
    Apply & Save, app.py will save the result as a trusted manual correction.

    Returns:
        CollectModeDecision describing what the user chose.
    """
    # Import tkinter inside the function so tests and non-GUI contexts can
    # import this module without immediately requiring a display.
    import tkinter as tk
    from tkinter import ttk

    route_reasons = route_reasons or []
    decision: dict[str, CollectModeDecision] = {
        "value": CollectModeDecision(action="skip", corrected_text="")
    }

    root = tk.Tk()
    root.title("Correctr collect mode review")
    root.geometry("780x620")
    root.minsize(640, 480)

    if always_on_top:
        root.attributes("-topmost", True)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(3, weight=1)
    root.rowconfigure(5, weight=1)

    header = ttk.Label(
        root,
        text="Review the correction before Correctr pastes or saves it.",
        font=("Segoe UI", 12, "bold"),
    )
    header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

    subheader_parts = []
    if engine_version:
        subheader_parts.append(f"Engine: {engine_version}")
    if route_reasons:
        subheader_parts.append("Route: " + ", ".join(route_reasons[:4]))

    subheader_text = " | ".join(subheader_parts) if subheader_parts else "Correctr collect mode"
    subheader = ttk.Label(root, text=subheader_text, wraplength=740)
    subheader.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

    original_label = ttk.Label(root, text="Original selected text")
    original_label.grid(row=2, column=0, sticky="w", padx=12)

    original_box = tk.Text(root, height=7, wrap="word", undo=False)
    original_box.grid(row=3, column=0, sticky="nsew", padx=12, pady=(2, 10))
    original_box.insert("1.0", original_text)
    original_box.configure(state="disabled")

    proposed_label = ttk.Label(
        root,
        text="Correction to apply (editable before saving)",
    )
    proposed_label.grid(row=4, column=0, sticky="w", padx=12)

    proposed_box = tk.Text(root, height=8, wrap="word", undo=True)
    proposed_box.grid(row=5, column=0, sticky="nsew", padx=12, pady=(2, 10))
    proposed_box.insert("1.0", proposed_text)
    proposed_box.focus_set()

    help_text = ttk.Label(
        root,
        text=(
            "Apply & Save closes this popup, returns focus to the original app, "
            "pastes the text, and saves a trusted event. Reject/Skip do not paste."
        ),
        wraplength=740,
    )
    help_text.grid(row=6, column=0, sticky="w", padx=12, pady=(0, 8))

    button_frame = ttk.Frame(root)
    button_frame.grid(row=7, column=0, sticky="e", padx=12, pady=(0, 12))

    def get_candidate_text() -> str:
        return proposed_box.get("1.0", "end-1c")

    def choose(action: CollectModeAction) -> None:
        corrected_text = get_candidate_text() if action == "apply" else ""
        decision["value"] = CollectModeDecision(
            action=action,
            corrected_text=corrected_text,
        )
        root.destroy()

    apply_button = ttk.Button(
        button_frame,
        text="Apply && Save",
        command=lambda: choose("apply"),
    )
    apply_button.grid(row=0, column=0, padx=(0, 8))

    reject_button = ttk.Button(
        button_frame,
        text="Reject",
        command=lambda: choose("reject"),
    )
    reject_button.grid(row=0, column=1, padx=(0, 8))

    skip_button = ttk.Button(
        button_frame,
        text="Skip",
        command=lambda: choose("skip"),
    )
    skip_button.grid(row=0, column=2, padx=(0, 8))

    quit_button = ttk.Button(
        button_frame,
        text="Quit correction",
        command=lambda: choose("quit"),
    )
    quit_button.grid(row=0, column=3)

    root.bind("<Control-Return>", lambda _event: choose("apply"))
    root.bind("<Escape>", lambda _event: choose("skip"))
    root.protocol("WM_DELETE_WINDOW", lambda: choose("skip"))

    root.mainloop()
    return decision["value"]
