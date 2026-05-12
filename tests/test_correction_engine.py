from correctr.correction_engine import (
    CorrectionResult,
    ENGINE_VERSION,
    correct_text,
    correct_text_detailed,
    run_placeholder_correction,
)


def test_corrects_successful_sample_sentence():
    original = "These are testig misakes for the app to hopfully fix. I am maknig two sentencs."

    corrected = correct_text(original)

    assert corrected == "These are testing mistakes for the app to hopefully fix. I am making two sentences."


def test_no_change_sentence_stays_the_same():
    original = "These words are already correct."

    corrected = correct_text(original)

    assert corrected == original


def test_changed_flag_is_false_when_no_correction_is_made():
    original = "These words are already correct."

    result = correct_text_detailed(original)

    assert result.changed is False
    assert result.corrections == []
    assert result.original_text == original
    assert result.corrected_text == original


def test_changed_flag_is_true_when_corrections_are_made():
    original = "testig"

    result = correct_text_detailed(original)

    assert result.changed is True
    assert result.corrected_text == "testing"


def test_corrections_list_includes_expected_original_and_corrected_pairs():
    original = "testig misakes hopfully"

    result = correct_text_detailed(original)

    expected_pairs = [
        {"original": "testig", "corrected": "testing"},
        {"original": "misakes", "corrected": "mistakes"},
        {"original": "hopfully", "corrected": "hopefully"},
    ]

    actual_pairs = [
        {"original": record["original"], "corrected": record["corrected"]}
        for record in result.corrections
    ]

    assert actual_pairs == expected_pairs


def test_correction_records_include_reason_and_positions():
    original = "testig"

    result = correct_text_detailed(original)

    assert result.corrections == [
        {
            "original": "testig",
            "corrected": "testing",
            "start_index": 0,
            "end_index": 6,
            "reason": "known_typo_dictionary",
        }
    ]


def test_preserves_basic_punctuation():
    original = "Sentencs. Somehting, stamdard!"

    corrected = correct_text(original)

    assert corrected == "Sentences. Something, standard!"


def test_preserves_basic_capitalization():
    original = "Testig is corrected. TESTIG is also corrected."

    corrected = correct_text(original)

    assert corrected == "Testing is corrected. TESTING is also corrected."


def test_replaces_multiple_typos_in_one_sentence():
    original = "Somehting about nural contexr and hightlight behavior is stamdard."

    corrected = correct_text(original)

    assert corrected == "Something about neural context and highlight behavior is standard."


def test_expanded_typo_dictionary_entries():
    original = "This was implimented in the enviroment after a seperate issue occured."

    corrected = correct_text(original)

    assert corrected == "This was implemented in the environment after a separate issue occurred."


def test_recieve_is_corrected_to_receive():
    original = "I should recieve the update."

    corrected = correct_text(original)

    assert corrected == "I should receive the update."


def test_correct_text_still_returns_plain_string_for_app():
    result = correct_text("testig")

    assert isinstance(result, str)
    assert result == "testing"


def test_correct_text_detailed_returns_structured_correction_result():
    result = correct_text_detailed("testig")

    assert isinstance(result, CorrectionResult)
    assert result.original_text == "testig"
    assert result.corrected_text == "testing"
    assert result.changed is True
    assert result.engine_version == ENGINE_VERSION
    assert len(result.corrections) == 1


def test_older_placeholder_function_name_still_runs_local_corrections():
    original = "testig misakes"

    corrected = run_placeholder_correction(original)

    assert corrected == "testing mistakes"
