from __future__ import annotations

from types import SimpleNamespace

import app as app_module
from app import CorrectrApp
from correctr.collect_mode_dialog import CollectModeDecision


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class FakeClipboardHandler:
    def __init__(self):
        self.pasted = []

    def paste_text(self, *, text_to_paste: str, original_clipboard_text: str) -> None:
        self.pasted.append((text_to_paste, original_clipboard_text))


class FakeResult:
    original_text = "shiuld this not also be abl eto fix this?"
    corrected_text = "Should this not also be able to fix this?"
    changed = True
    corrections = [
        {
            "original": original_text,
            "corrected": corrected_text,
            "pipeline_stage": "ai_context",
            "route_reasons": ["dictionary_no_change_but_suspicious_pattern"],
        }
    ]
    engine_version = "orchestrator_v0.2:ai_context"


def make_app_for_unit_test(
    *,
    save_rejected_events_in_collect_mode: bool = False,
    collect_mode_review_interface: str = "popup",
):
    correctr_app = CorrectrApp.__new__(CorrectrApp)
    correctr_app.config = SimpleNamespace(
        save_rejected_events_in_collect_mode=save_rejected_events_in_collect_mode,
        save_events_when_collect_mode_off=False,
        collect_mode_review_interface=collect_mode_review_interface,
        collect_mode_popup_always_on_top=True,
        after_collect_mode_dialog_close_delay_seconds=0,
        collect_mode_enabled=True,
        collect_mode_proposal_pipeline_mode="dictionary_then_ai_always",
        correction_pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider="mock",
    )
    correctr_app.logger = FakeLogger()
    correctr_app.clipboard_handler = FakeClipboardHandler()
    return correctr_app


def test_popup_collect_mode_accept_pastes_and_saves_trusted_event(monkeypatch):
    correctr_app = make_app_for_unit_test()
    saved_calls = []

    monkeypatch.setattr(
        CorrectrApp,
        "_show_collect_mode_popup",
        lambda self, result: CollectModeDecision(action="apply", corrected_text=result.corrected_text),
    )

    def fake_save_correction_event(**kwargs):
        saved_calls.append(kwargs)
        return 101

    monkeypatch.setattr(app_module, "save_correction_event", fake_save_correction_event)

    correctr_app._handle_collect_mode_result(
        result=FakeResult(),
        original_clipboard_text="prior clipboard",
    )

    assert correctr_app.clipboard_handler.pasted == [
        ("Should this not also be able to fix this?", "prior clipboard")
    ]
    assert saved_calls[0]["review_status"] == "accepted"
    assert saved_calls[0]["review_notes"] == "Accepted from collect mode."
    assert saved_calls[0]["source"] == "ai_context"


def test_popup_collect_mode_edited_text_saves_manual_trusted_event(monkeypatch):
    correctr_app = make_app_for_unit_test()
    saved_calls = []

    monkeypatch.setattr(
        CorrectrApp,
        "_show_collect_mode_popup",
        lambda self, result: CollectModeDecision(
            action="apply",
            corrected_text="Should this not also be able to fix this today?",
        ),
    )

    def fake_save_collect_mode_manual_correction(**kwargs):
        saved_calls.append(kwargs)
        return 102

    monkeypatch.setattr(
        app_module,
        "save_collect_mode_manual_correction",
        fake_save_collect_mode_manual_correction,
    )

    correctr_app._handle_collect_mode_result(
        result=FakeResult(),
        original_clipboard_text="prior clipboard",
    )

    assert correctr_app.clipboard_handler.pasted == [
        ("Should this not also be able to fix this today?", "prior clipboard")
    ]
    assert saved_calls[0]["original_text"] == FakeResult.original_text
    assert saved_calls[0]["corrected_text"] == "Should this not also be able to fix this today?"


def test_popup_collect_mode_reject_does_not_paste_or_save_by_default(monkeypatch):
    correctr_app = make_app_for_unit_test(save_rejected_events_in_collect_mode=False)
    saved_calls = []

    monkeypatch.setattr(
        CorrectrApp,
        "_show_collect_mode_popup",
        lambda self, result: CollectModeDecision(action="reject"),
    )
    monkeypatch.setattr(app_module, "save_correction_event", lambda **kwargs: saved_calls.append(kwargs))

    correctr_app._handle_collect_mode_result(
        result=FakeResult(),
        original_clipboard_text="prior clipboard",
    )

    assert correctr_app.clipboard_handler.pasted == []
    assert saved_calls == []


def test_popup_collect_mode_skip_does_not_paste_or_save(monkeypatch):
    correctr_app = make_app_for_unit_test()
    saved_calls = []

    monkeypatch.setattr(
        CorrectrApp,
        "_show_collect_mode_popup",
        lambda self, result: CollectModeDecision(action="skip"),
    )
    monkeypatch.setattr(app_module, "save_correction_event", lambda **kwargs: saved_calls.append(kwargs))

    correctr_app._handle_collect_mode_result(
        result=FakeResult(),
        original_clipboard_text="prior clipboard",
    )

    assert correctr_app.clipboard_handler.pasted == []
    assert saved_calls == []


def test_terminal_collect_mode_still_available(monkeypatch):
    correctr_app = make_app_for_unit_test(collect_mode_review_interface="terminal")

    monkeypatch.setattr(CorrectrApp, "_print_collect_mode_review", lambda self, result: None)
    monkeypatch.setattr(CorrectrApp, "_prompt_collect_mode_choice", lambda self: "a")

    decision = correctr_app._get_collect_mode_decision(FakeResult())

    assert decision.action == "apply"
    assert decision.corrected_text == FakeResult.corrected_text


def test_collect_mode_uses_stronger_proposal_pipeline(monkeypatch):
    correctr_app = make_app_for_unit_test()
    calls = []

    def fake_correct_with_orchestration(text, *, pipeline_mode, ai_provider_mode):
        calls.append(
            {
                "text": text,
                "pipeline_mode": pipeline_mode,
                "ai_provider_mode": ai_provider_mode,
            }
        )
        return FakeResult()

    monkeypatch.setattr(app_module, "correct_with_orchestration", fake_correct_with_orchestration)

    result = correctr_app._run_correction_for_current_mode("yuet anothr normla eror")

    assert result.corrected_text == FakeResult.corrected_text
    assert calls == [
        {
            "text": "yuet anothr normla eror",
            "pipeline_mode": "dictionary_then_ai_always",
            "ai_provider_mode": "mock",
        }
    ]


def test_auto_mode_keeps_normal_conservative_pipeline(monkeypatch):
    correctr_app = make_app_for_unit_test()
    correctr_app.config.collect_mode_enabled = False
    calls = []

    def fake_correct_with_orchestration(text, *, pipeline_mode, ai_provider_mode):
        calls.append(
            {
                "text": text,
                "pipeline_mode": pipeline_mode,
                "ai_provider_mode": ai_provider_mode,
            }
        )
        return FakeResult()

    monkeypatch.setattr(app_module, "correct_with_orchestration", fake_correct_with_orchestration)

    correctr_app._run_correction_for_current_mode("clean-ish text")

    assert calls == [
        {
            "text": "clean-ish text",
            "pipeline_mode": "dictionary_then_ai_if_needed",
            "ai_provider_mode": "mock",
        }
    ]
