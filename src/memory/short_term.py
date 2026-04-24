from collections import deque
from typing import Literal


Role = Literal["user", "assistant", "system"]


class ShortTermMemory:
    """Sliding-window conversation buffer. Giữ N lượt gần nhất."""

    def __init__(self, max_turns: int = 8):
        self.max_turns = max_turns
        self._buf: deque[dict] = deque(maxlen=max_turns * 2)

    def add(self, role: Role, content: str) -> None:
        self._buf.append({"role": role, "content": content})

    def get_messages(self) -> list[dict]:
        return list(self._buf)

    def render(self) -> str:
        if not self._buf:
            return "(empty)"
        return "\n".join(f"{m['role']}: {m['content']}" for m in self._buf)

    def clear(self) -> None:
        self._buf.clear()
