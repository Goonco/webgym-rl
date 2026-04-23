from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass
class Task:
    instruction: str
    website: str
    task_id: str
    evaluation: dict[str, Any] | list[Any] | None = None


class TaskStore:
    """Preloaded lookup table for WebGym tasks rows keyed by dataset task_id."""

    def __init__(self, tasks_by_id: Mapping[str, Task]) -> None:
        self._tasks_by_id = dict(tasks_by_id)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
    ) -> "TaskStore":
        rows = _load_task_rows(Path(path))
        return cls.from_rows(rows)

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Mapping[str, Any]],
    ) -> "TaskStore":
        tasks_by_id: dict[str, Task] = {}
        for row in rows:
            task = row_to_task(row)
            tasks_by_id[task.task_id] = task
        return cls(tasks_by_id)

    def get(self, task_id: str | int) -> Task:
        key = str(task_id)
        if key not in self._tasks_by_id:
            raise KeyError(f"Unknown task_id: {key}")
        return copy.deepcopy(self._tasks_by_id[key])

    def __contains__(self, task_id: object) -> bool:
        return str(task_id) in self._tasks_by_id

    def __len__(self) -> int:
        return len(self._tasks_by_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._tasks_by_id.keys())


def row_to_task(row: Mapping[str, Any]) -> Task:
    task_data = dict(row)
    # [TODO] KeyError handling needed
    return Task(
        instruction=task_data["task_name"],
        website=_normalize_website(task_data["website"]),
        task_id=str(task_data["task_id"]),
        evaluation=_extract_evaluation(task_data),
    )


def _load_task_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return _load_json_rows(path)
    # if suffix == ".csv":
    #     return _load_pandas_rows(path, "csv")
    # if suffix in {".parquet", ".pq"}:
    #     return _load_pandas_rows(path, "parquet")

    raise ValueError(f"Unsupported task file type: {path.suffix}")


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    if isinstance(data, list):
        return [dict(row) for row in data]
    if isinstance(data, dict) and isinstance(data.get("tasks"), list):
        return [dict(row) for row in data["tasks"]]
    if isinstance(data, dict):
        return [dict(data)]

    raise ValueError(f"Unsupported JSON task payload in {path}")


# def _load_pandas_rows(path: Path, file_type: str) -> list[dict[str, Any]]:
#     try:
#         import pandas as pd
#     except ModuleNotFoundError as exc:
#         raise ModuleNotFoundError(
#             f"pandas is required to load {path.suffix} task files"
#         ) from exc

#     if file_type == "csv":
#         frame = pd.read_csv(path)
#     elif file_type == "parquet":
#         frame = pd.read_parquet(path)
#     else:
#         raise ValueError(f"Unsupported pandas task file type: {file_type}")

#     return frame.to_dict("records")


def _normalize_website(website: Any) -> str:
    website_str = str(website)
    if website_str.startswith("http"):
        return website_str
    return f"https://{website_str}"


def _extract_evaluation(task_data: Mapping[str, Any]) -> dict[str, Any] | list[Any] | None:
    evaluation = task_data.get("evaluation")
    if evaluation is None:
        evaluation = task_data.get("rule_evaluation")
    if evaluation is None:
        evaluation = task_data.get("evaluator")
    if isinstance(evaluation, (dict, list)):
        return copy.deepcopy(evaluation)
    return None
