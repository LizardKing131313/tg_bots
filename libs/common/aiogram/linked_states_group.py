from __future__ import annotations

from typing import ClassVar

from aiogram.fsm.state import State as AiogramState, StatesGroup


class SkippableState(AiogramState):
    def __init__(self, *, can_skip: bool = False) -> None:
        super().__init__()
        self.can_skip: bool = can_skip
        self.previous: SkippableState | None = None
        self.next: SkippableState | None = None
        self.order_number: int | None = None
        self.state_name: str | None = None


class LinkedStatesGroup(StatesGroup):

    _by_full: ClassVar[dict[str, SkippableState]]
    _by_short: ClassVar[dict[str, SkippableState]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        states: list[SkippableState] = []
        for _name, value in cls.__dict__.items():
            if isinstance(value, SkippableState):
                states.append(value)

        for i, st in enumerate(states):
            prev_st: SkippableState | None = states[i - 1] if i > 0 else None
            next_st: SkippableState | None = states[i + 1] if i + 1 < len(states) else None
            st.previous = prev_st
            st.next = next_st
            st.order_number = i + 1
            st.state_name = st.state.split(":")[1]

        cls._by_full = {st.state: st for st in states}
        cls._by_short = {st.state_name: st for st in states}

    @classmethod
    def from_value(cls, value: str | AiogramState | None) -> SkippableState | None:
        if value is None:
            return None
        if isinstance(value, SkippableState):
            return value
        if isinstance(value, AiogramState):
            return cls._by_full.get(value.state)
        return cls._by_full.get(value) or cls._by_short.get(value)

    @classmethod
    def states_count(cls) -> int:
        return len(cls.__all_states__)
