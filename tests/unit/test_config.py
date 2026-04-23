import json
import sys
from pathlib import Path

import pytest

from src.config import EnvType, load_config, parse_args


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _config_payload(task_file_path: str) -> dict:
    return {
        "env_type": "webgym",
        "gateway": {
            "host": "127.0.0.1",
            "port": "18000",
            "max_workers": "4",
            "max_in_flight": "3",
            "verl_timeout": "60.0",
            "in_flight_timeout": "5.0",
            "deadline_margin": "2.0",
        },
        "task_file_path": task_file_path,
        "webgym": {
            "omnibox_host": "127.0.0.1",
            "omnibox_port": "7000",
            "omnibox_api_key": "default_key",
            "http_stack": {
                "allocate": {"pool_size": "4", "timeout": "20.0"},
                "release": {"pool_size": "4", "timeout": "10.0"},
                "metadata": {"pool_size": "2", "timeout": "5.0"},
                "navigate": {"pool_size": "4", "timeout": "20.0"},
                "screenshot": {"pool_size": "4", "timeout": "20.0"},
                "ac_tree": {"pool_size": "2", "timeout": "10.0"},
                "page_metadata": {"pool_size": "2", "timeout": "5.0"},
                "execute": {"pool_size": "8", "timeout": "10.0"},
            },
        },
    }


def test_load_config_parses_webgym_config(tmp_path):
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text("", encoding="utf-8")

    config_path = tmp_path / "config.json"
    _write_json(config_path, _config_payload(str(task_file)))

    config = load_config(config_path)

    assert config.env_type == EnvType.WEB_GYM
    assert config.gateway.host == "127.0.0.1"
    assert config.gateway.port == 18000
    assert config.gateway.max_workers == 4
    assert config.gateway.max_in_flight == 3
    assert config.gateway.verl_timeout == 60.0
    assert config.gateway.in_flight_timeout == 5.0
    assert config.gateway.deadline_margin == 2.0
    assert config.task_file_path == task_file

    assert config.webgym is not None
    assert config.webgym.omnibox_host == "127.0.0.1"
    assert config.webgym.omnibox_port == 7000
    assert config.webgym.omnibox_api_key == "default_key"
    assert config.webgym.httpstack_config.get_pool_dit() == {
        "allocate": 4,
        "release": 4,
        "metadata": 2,
        "navigate": 4,
        "screenshot": 4,
        "ac_tree": 2,
        "page_metadata": 2,
        "execute": 8,
    }


def test_load_config_raises_value_error_for_missing_required_key(tmp_path):
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text("", encoding="utf-8")

    payload = _config_payload(str(task_file))
    del payload["gateway"]["host"]

    config_path = tmp_path / "config.json"
    _write_json(config_path, payload)

    with pytest.raises(ValueError, match="Missing required config key: host"):
        load_config(config_path)


def test_load_config_raises_for_osworld(tmp_path):
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text("", encoding="utf-8")

    payload = _config_payload(str(task_file))
    payload["env_type"] = "osworld"

    config_path = tmp_path / "config.json"
    _write_json(config_path, payload)

    with pytest.raises(NotImplementedError, match="osworld is not supported yet"):
        load_config(config_path)


def test_parse_args_reads_config_path_from_cli(monkeypatch, tmp_path):
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text("", encoding="utf-8")

    config_path = tmp_path / "config.json"
    _write_json(config_path, _config_payload(str(task_file)))

    monkeypatch.setattr(sys, "argv", ["prog", str(config_path)])

    config = parse_args()

    assert config.env_type == EnvType.WEB_GYM
    assert config.task_file_path == task_file
    assert config.webgym is not None
    assert config.webgym.omnibox_port == 7000
