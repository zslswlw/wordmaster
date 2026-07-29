"""Pure study-round state engine shared by new, enhance, and review modes."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


VALID_STUDY_TYPES = {"new", "enhance", "review"}


@dataclass(frozen=True)
class CanonicalAnswer:
    word_id: int
    round: int
    correct: bool
    record_id: int


@dataclass(frozen=True)
class StudyState:
    current_round: int
    target_word_ids: List[int]
    answered_word_ids: List[int]
    remaining_word_ids: List[int]
    wrong_word_ids: List[int]
    round_complete: bool
    phase_complete: bool


def _record_id(record: object, fallback: int) -> int:
    value = getattr(record, "id", None)
    return int(value) if value is not None else fallback


def canonical_answers(records: Iterable[object]) -> Dict[tuple[int, int], CanonicalAnswer]:
    """Keep the latest result for each round/word pair."""
    latest: Dict[tuple[int, int], CanonicalAnswer] = {}
    for index, record in enumerate(records, 1):
        answer = CanonicalAnswer(
            word_id=int(getattr(record, "word_id")),
            round=int(getattr(record, "round")),
            correct=bool(getattr(record, "correct")),
            record_id=_record_id(record, index),
        )
        key = (answer.round, answer.word_id)
        previous = latest.get(key)
        if previous is None or answer.record_id > previous.record_id:
            latest[key] = answer
    return latest


def _state_for_round(
    round_number: int,
    target_word_ids: List[int],
    answers: Dict[tuple[int, int], CanonicalAnswer],
) -> StudyState:
    target_set = set(target_word_ids)
    round_answers = {
        word_id: answer
        for (answer_round, word_id), answer in answers.items()
        if answer_round == round_number and word_id in target_set
    }
    answered = [word_id for word_id in target_word_ids if word_id in round_answers]
    remaining = [word_id for word_id in target_word_ids if word_id not in round_answers]
    wrong = [
        word_id
        for word_id in target_word_ids
        if word_id in round_answers and not round_answers[word_id].correct
    ]
    round_complete = bool(target_word_ids) and not remaining
    return StudyState(
        current_round=round_number,
        target_word_ids=list(target_word_ids),
        answered_word_ids=answered,
        remaining_word_ids=remaining,
        wrong_word_ids=wrong,
        round_complete=round_complete,
        phase_complete=round_complete and not wrong,
    )


def calculate_study_state(all_word_ids: Iterable[int], records: Iterable[object]) -> StudyState:
    ordered_word_ids = list(dict.fromkeys(int(word_id) for word_id in all_word_ids))
    if not ordered_word_ids:
        return StudyState(1, [], [], [], [], False, False)

    answers = canonical_answers(records)
    target_word_ids = ordered_word_ids
    round_number = 1

    while True:
        state = _state_for_round(round_number, target_word_ids, answers)
        if not state.round_complete or state.phase_complete:
            return state
        target_word_ids = state.wrong_word_ids
        round_number += 1


def get_round_state(
    all_word_ids: Iterable[int],
    records: Iterable[object],
    round_number: int,
) -> Optional[StudyState]:
    if round_number < 1:
        return None

    ordered_word_ids = list(dict.fromkeys(int(word_id) for word_id in all_word_ids))
    if not ordered_word_ids:
        return None

    answers = canonical_answers(records)
    target_word_ids = ordered_word_ids
    for current_round in range(1, round_number + 1):
        state = _state_for_round(current_round, target_word_ids, answers)
        if current_round == round_number:
            return state
        if not state.round_complete or not state.wrong_word_ids:
            return None
        target_word_ids = state.wrong_word_ids
    return None


def summarize_rounds(all_word_ids: Iterable[int], records: Iterable[object]) -> dict[int, dict]:
    ordered_word_ids = list(dict.fromkeys(int(word_id) for word_id in all_word_ids))
    answers = canonical_answers(records)
    result: dict[int, dict] = {}
    target_word_ids = ordered_word_ids
    round_number = 1

    while target_word_ids:
        state = _state_for_round(round_number, target_word_ids, answers)
        result[round_number] = {
            "correct": len(state.answered_word_ids) - len(state.wrong_word_ids),
            "wrong": len(state.wrong_word_ids),
            "total": len(state.answered_word_ids),
            "expected": len(state.target_word_ids),
            "remaining": len(state.remaining_word_ids),
        }
        if not state.round_complete or not state.wrong_word_ids:
            break
        target_word_ids = state.wrong_word_ids
        round_number += 1

    return result


def get_study_words(
    all_word_ids: List[int],
    existing_records: list,
    study_type: str,
) -> tuple[List[int], int, bool]:
    """Compatibility wrapper for the original helper API."""
    if study_type not in VALID_STUDY_TYPES:
        raise ValueError(f"Unsupported study type: {study_type}")
    state = calculate_study_state(all_word_ids, existing_records)
    return state.remaining_word_ids, state.current_round, state.phase_complete
