from types import SimpleNamespace

from app.routers.study_refactored import calculate_study_state, summarize_rounds


def record(record_id, word_id, round_number, correct):
    return SimpleNamespace(
        id=record_id,
        word_id=word_id,
        round=round_number,
        correct=correct,
    )


def test_partial_round_returns_only_unanswered_words():
    state = calculate_study_state(
        [1, 2, 3],
        [record(1, 1, 1, True), record(2, 2, 1, False)],
    )

    assert state.current_round == 1
    assert state.target_word_ids == [1, 2, 3]
    assert state.remaining_word_ids == [3]
    assert state.wrong_word_ids == [2]
    assert not state.round_complete


def test_next_round_contains_only_previous_wrong_words():
    records = [
        record(1, 1, 1, True),
        record(2, 2, 1, False),
        record(3, 3, 1, True),
    ]
    state = calculate_study_state([1, 2, 3], records)

    assert state.current_round == 2
    assert state.target_word_ids == [2]
    assert state.remaining_word_ids == [2]

    records.append(record(4, 2, 2, True))
    completed = calculate_study_state([1, 2, 3], records)
    assert completed.phase_complete
    assert completed.current_round == 2


def test_latest_duplicate_is_canonical_for_legacy_data():
    records = [
        record(1, 1, 1, False),
        record(2, 1, 1, True),
        record(3, 2, 1, True),
    ]

    state = calculate_study_state([1, 2], records)
    rounds = summarize_rounds([1, 2], records)

    assert state.phase_complete
    assert rounds[1] == {
        "correct": 2,
        "wrong": 0,
        "total": 2,
        "expected": 2,
        "remaining": 0,
    }
