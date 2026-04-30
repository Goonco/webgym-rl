import argparse
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from .gateway.app import launch
from .gateway.error import ConfigError, WebGymRLError
from .util.config import Config
from .util.log import runtime_logger


def _validate_config(config: Config) -> None:
    gateway_config = config.gateway
    if gateway_config.max_workers < gateway_config.max_in_flight:
        runtime_logger.warning(
            "Gateway max_workers (%s) is smaller than max_in_flight (%s). "
            "Requests may acquire in-flight slots faster than executor workers "
            "can process them, which can lead to queued HTTP sessions timing out. "
            "Consider setting max_workers >= max_in_flight.",
            gateway_config.max_workers,
            gateway_config.max_in_flight,
        )


def _load_config(config_path: Path) -> Config:
    if not config_path.is_file():
        raise ConfigError(f"configuration file required but not found in {config_path}")

    try:
        config = Config.model_validate_json(config_path.read_text())
    except ValidationError as exc:
        raise ConfigError(f"{config_path} is invalid\n{exc}")

    _validate_config(config)

    return config


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    args = parser.parse_args()
    return args


def main() -> None:
    try:
        args = _parse_args()
        config = _load_config(args.config_path)
        uvicorn.run(launch(config), host=config.gateway.host, port=config.gateway.port)
    except WebGymRLError as exc:
        runtime_logger.error(exc)
        raise SystemExit(1)
    except Exception as exc:
        raise RuntimeError(f"[unexpected error] {exc}") from exc


if __name__ == "__main__":
    main()
