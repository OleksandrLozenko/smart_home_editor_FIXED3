from __future__ import annotations
import json
from typing import Optional, Callable, List

class UndoManager:
    def __init__(self, on_change: Optional[Callable[[], None]] = None, autosave_path: str = "smarthome_autosave.json"):
        self._undo_stack: List[str] = []
        self._redo_stack: List[str] = []
        self.autosave_path = autosave_path
        self.on_change = on_change

    def push(self, snapshot: str):
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        self._autosave(snapshot)
        if self.on_change: self.on_change()

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 1

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> Optional[str]:
        if not self.can_undo():
            return None
        current = self._undo_stack.pop()
        self._redo_stack.append(current)
        return self._undo_stack[-1]

    def redo(self) -> Optional[str]:
        if not self.can_redo():
            return None
        snap = self._redo_stack.pop()
        self._undo_stack.append(snap)
        return snap

    def top(self) -> Optional[str]:
        return self._undo_stack[-1] if self._undo_stack else None

    def _autosave(self, snapshot: str):
        try:
            data = json.loads(snapshot)
            with open(self.autosave_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
