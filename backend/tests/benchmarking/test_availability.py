from app.benchmarking.availability import (
    check_faiss,
    check_ollama,
    check_sentence_transformers,
    full_report,
)


def test_check_ollama_never_raises_when_not_installed():
    result = check_ollama()
    assert isinstance(result.available, bool)
    assert result.detail


def test_full_report_includes_all_core_checks():
    report = full_report()
    assert {"sentence_transformers", "faiss", "ollama", "tesseract", "faster_whisper"} <= set(
        report
    )


def test_sentence_transformers_and_faiss_are_available_in_this_environment():
    # These are the two dependencies Phase 7 retrieval evaluation actually
    # needs; if this fails, retrieval evaluation cannot run at all and the
    # benchmark run should report NOT MEASURED rather than silently
    # skipping — this test documents that expectation.
    assert check_sentence_transformers().available
    assert check_faiss().available
