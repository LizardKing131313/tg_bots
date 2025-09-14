from __future__ import annotations

from typing import Any

import pytest
from aiogram.fsm.state import State as AiogramState

from libs.common.aiogram.linked_states_group import LinkedStatesGroup, SkippableState


class Survey(LinkedStatesGroup):
    name = SkippableState()
    age = SkippableState(can_skip=False)
    city = SkippableState(can_skip=True)


def test_skippable_state_basic_attrs() -> None:
    st = SkippableState(can_skip=True)
    assert isinstance(st.can_skip, bool)
    assert st.can_skip is True
    assert st.previous is None
    assert st.next is None
    assert st.order_number is None
    assert st.state_name is None


def test_linking_prev_next_and_order_and_state_name() -> None:
    assert Survey.name.previous is None
    assert Survey.name.next is Survey.age
    assert Survey.name.order_number == 1
    assert Survey.name.state_name == "name"
    assert Survey.name.state.endswith(":name")

    assert Survey.age.previous is Survey.name
    assert Survey.age.next is Survey.city
    assert Survey.age.order_number == 2
    assert Survey.age.state_name == "age"
    assert Survey.age.state.endswith(":age")

    assert Survey.city.previous is Survey.age
    assert Survey.city.next is None
    assert Survey.city.order_number == 3
    assert Survey.city.state_name == "city"
    assert Survey.city.state.endswith(":city")


def test_internal_maps_full_and_short() -> None:
    full_keys = set(Survey._by_full.keys())
    short_keys = set(Survey._by_short.keys())

    assert full_keys == {Survey.name.state, Survey.age.state, Survey.city.state}
    assert short_keys == {"name", "age", "city"}

    assert Survey._by_full[Survey.city.state] is Survey.city
    assert Survey._by_short["age"] is Survey.age


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (Survey.name, Survey.name),
        ("Survey:age", Survey.age),
        ("city", Survey.city),
        ("unknown", None),
    ],
)
def test_from_value_various_inputs(
    value: Any, expected: SkippableState | None  # noqa: ANN401
) -> None:
    assert Survey.from_value(value) is expected


def test_from_value_with_plain_aiogram_state_branch() -> None:
    other = AiogramState()
    assert Survey.from_value(other) is None


def test_states_count_matches_all_states() -> None:
    assert Survey.states_count() == len(Survey.__all_states__) == 3


# noinspection PyTypeChecker
def test_from_value_with_garbage_inputs() -> None:
    class Dummy:
        state = "xxx"

    assert Survey.from_value(42) is None
    assert Survey.from_value(Dummy()) is None
