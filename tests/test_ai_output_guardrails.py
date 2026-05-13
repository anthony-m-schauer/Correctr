from correctr.llm_engine import apply_basic_sentence_start_capitalization, clean_model_output, validate_model_output


def test_strips_here_is_the_corrected_text_prefix():
    output = "Here is the corrected text:\n\nThis here be the third practice testing sentence we have."
    assert clean_model_output(output) == "This here be the third practice testing sentence we have."


def test_strips_corrected_text_prefix():
    assert clean_model_output("Corrected text: Should this not also be able to fix this?") == "Should this not also be able to fix this?"


def test_strips_correction_prefix():
    assert clean_model_output("Correction: Should this not also be able to fix this?") == "Should this not also be able to fix this?"


def test_rejects_explanation_style_outputs():
    validation = validate_model_output(original_text="Thsi here be th ethird pracitve testing sentenc we habe.", candidate_text="I corrected the spelling mistakes in the sentence.")
    assert validation.is_acceptable is False
    assert "explain" in validation.reason.lower() or "appeared" in validation.reason.lower()


def test_rejects_empty_outputs():
    validation = validate_model_output(original_text="shiuld this not also be abl eto fix this?", candidate_text="")
    assert validation.is_acceptable is False
    assert "empty" in validation.reason.lower()


def test_rejects_markdown_code_fence_outputs():
    validation = validate_model_output(original_text="Thsi here be th ethird pracitve testing sentenc we habe.", candidate_text="```text\nThis here be the third practice testing sentence we have.\n```")
    assert validation.is_acceptable is False
    assert "markdown" in validation.reason.lower() or "code" in validation.reason.lower()


def test_rejects_multiple_paragraphs_when_original_was_one_sentence():
    validation = validate_model_output(original_text="Thsi here be th ethird pracitve testing sentenc we habe.", candidate_text="This here be the third practice testing sentence we have.\n\nI fixed the errors.")
    assert validation.is_acceptable is False
    assert "multiple paragraphs" in validation.reason.lower()


def test_rejects_much_longer_outputs():
    validation = validate_model_output(original_text="shiuld this work?", candidate_text="Should this work? This is a detailed explanation of every typo and why the correction was made, which is not acceptable for the Correctr app workflow.")
    assert validation.is_acceptable is False
    assert "much longer" in validation.reason.lower()


def test_accepts_plain_corrected_text():
    validation = validate_model_output(original_text="shiuld this not also be abl eto fix this?", candidate_text="Should this not also be able to fix this?")
    assert validation.is_acceptable is True


def test_sentence_start_capitalization_fix_for_observed_partial_output():
    corrected = apply_basic_sentence_start_capitalization("shiuld this not also be abl eto fix this?", "should this not also be able to fix this?")
    assert corrected == "Should this not also be able to fix this?"


def test_observed_snother_bad_output_is_not_reliably_detected_by_guardrail():
    validation = validate_model_output(original_text="Snother testin gexample.", candidate_text="snother testin' gexample.")
    assert validation.is_acceptable is True
