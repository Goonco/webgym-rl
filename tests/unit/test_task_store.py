import json

import pytest

from src.task_store import TaskStore, row_to_task


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path, rows) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )


def _task_row(**overrides):
    row = {
        "task_name": "Make the counter value 5.",
        "website": "http://127.0.0.1:8123/counter.html",
        "task_id": "counter-5",
        "evaluation": {
            "rules": [
                {
                    "selector": "#count",
                    "text": "5",
                    "match": "exact",
                }
            ]
        },
    }
    row.update(overrides)
    return row


def test_row_to_task_maps_required_fields():
    task = row_to_task(_task_row())

    assert task.instruction == "Make the counter value 5."
    assert task.website == "http://127.0.0.1:8123/counter.html"
    assert task.task_id == "counter-5"
    assert task.evaluation == {
        "rules": [
            {
                "selector": "#count",
                "text": "5",
                "match": "exact",
            }
        ]
    }


def test_row_to_task_normalizes_website_without_scheme():
    task = row_to_task(
        _task_row(
            website="example.com/counter.html",
            evaluation=None,
        )
    )

    assert task.website == "https://example.com/counter.html"


@pytest.mark.parametrize("evaluation_key", ["evaluation", "rule_evaluation", "evaluator"])
def test_row_to_task_uses_supported_evaluation_keys(evaluation_key):
    rule = {"selector": "#count", "text": "5", "match": "exact"}
    row = _task_row(evaluation=None, rule_evaluation=None, evaluator=None)
    row[evaluation_key] = {"rules": [rule]}

    task = row_to_task(row)

    assert task.evaluation == {"rules": [rule]}


def test_task_store_from_rows_indexes_by_string_task_id():
    store = TaskStore.from_rows(
        [
            _task_row(task_id=1),
            _task_row(task_id=2, website="http://127.0.0.1:8123/other.html"),
        ]
    )

    assert "1" in store
    assert "2" in store
    assert len(store) == 2
    assert store.ids() == ("1", "2")


def test_task_store_get_returns_deep_copy():
    store = TaskStore.from_rows([_task_row()])

    first = store.get("counter-5")
    first.evaluation["rules"][0]["text"] = "999"

    second = store.get("counter-5")

    assert second.evaluation["rules"][0]["text"] == "5"


def test_task_store_get_raises_for_unknown_task_id():
    store = TaskStore.from_rows([_task_row()])

    with pytest.raises(KeyError, match="Unknown task_id: missing-task"):
        store.get("missing-task")


def test_task_store_from_file_loads_json_array(tmp_path):
    path = tmp_path / "tasks.json"
    _write_json(
        path,
        [
            _task_row(task_id="counter-5"),
            _task_row(task_id="counter-6", website="http://127.0.0.1:8123/second.html"),
        ],
    )

    store = TaskStore.from_file(path)

    assert len(store) == 2
    assert store.get("counter-5").website == "http://127.0.0.1:8123/counter.html"
    assert store.get("counter-6").website == "http://127.0.0.1:8123/second.html"


def test_task_store_from_file_loads_jsonl(tmp_path):
    path = tmp_path / "tasks.jsonl"
    _write_jsonl(
        path,
        [
            _task_row(task_id="counter-5"),
            _task_row(task_id="counter-7", website="http://127.0.0.1:8123/third.html"),
        ],
    )

    store = TaskStore.from_file(path)

    assert len(store) == 2
    assert store.get("counter-7").website == "http://127.0.0.1:8123/third.html"


def test_task_store_from_file_accepts_dict_with_tasks_key(tmp_path):
    path = tmp_path / "tasks.json"
    _write_json(
        path,
        {
            "tasks": [
                _task_row(task_id="counter-5"),
                _task_row(task_id="counter-8"),
            ]
        },
    )

    store = TaskStore.from_file(path)

    assert len(store) == 2


def test_task_store_from_file_raises_for_missing_file(tmp_path):
    path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        TaskStore.from_file(path)


def test_task_store_from_file_raises_for_unsupported_suffix(tmp_path):
    path = tmp_path / "tasks.txt"
    path.write_text("not-used", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported task file type: .txt"):
        TaskStore.from_file(path)
