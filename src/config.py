from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class GatewayConfig:
    host: str
    port: int
    max_workers: int
    max_in_flight: int

    verl_timeout: float
    in_flight_timeout: float
    deadline_margin: float


@dataclass(frozen=True)
class OperationConfig:
    pool_size: int
    timeout: float


@dataclass(frozen=True)
class HttpStackConfig:
    allocate: OperationConfig
    release: OperationConfig
    navigate: OperationConfig
    screenshot: OperationConfig
    execute: OperationConfig
    # metadata: OperationConfig
    # ac_tree: OperationConfig
    # page_metadata: OperationConfig

    def get_pool_dit(self) -> dict[str, int]:
        return {
            "allocate": self.allocate.pool_size,
            "release": self.release.pool_size,
            "navigate": self.navigate.pool_size,
            "screenshot": self.screenshot.pool_size,
            "execute": self.execute.pool_size,
            "metadata": 0,
            "ac_tree": 0,
            "page_metadata": 0,
        }


@dataclass(frozen=True)
class WebGymConfig:
    httpstack_config: HttpStackConfig

    omnibox_host: str
    omnibox_port: int
    omnibox_api_key: str


@dataclass(frozen=True)
class OSWorldConfig:
    pass


class EnvType(Enum):
    WEB_GYM = "webgym"
    OS_WORLD = "osworld"


@dataclass(frozen=True)
class Config:
    env_type: EnvType
    gateway: GatewayConfig
    task_file_path: Path
    webgym: WebGymConfig | None = None
    osworld: OSWorldConfig | None = None


def load_config(path: Path) -> Config:
    config = json.loads(path.read_text())

    try:
        env_type = EnvType(config["env_type"])

        gateway_config = config["gateway"]
        gateway = GatewayConfig(
            host=gateway_config["host"],
            port=int(gateway_config["port"]),
            max_workers=int(gateway_config["max_workers"]),
            max_in_flight=int(gateway_config["max_in_flight"]),
            verl_timeout=float(gateway_config["verl_timeout"]),
            in_flight_timeout=float(gateway_config["in_flight_timeout"]),
            deadline_margin=float(gateway_config["deadline_margin"]),
        )

        task_file_path = Path(config["task_file_path"])

        if env_type == EnvType.WEB_GYM:
            webgym_data = config["webgym"]
            http_stack_data = webgym_data["http_stack"]

            def operation_config(name: str) -> OperationConfig:
                operation_data = http_stack_data[name]
                return OperationConfig(
                    pool_size=int(operation_data["pool_size"]),
                    timeout=float(operation_data["timeout"]),
                )

            webgym = WebGymConfig(
                omnibox_host=webgym_data["omnibox_host"],
                omnibox_port=int(webgym_data["omnibox_port"]),
                omnibox_api_key=webgym_data["omnibox_api_key"],
                httpstack_config=HttpStackConfig(
                    allocate=operation_config("allocate"),
                    release=operation_config("release"),
                    navigate=operation_config("navigate"),
                    screenshot=operation_config("screenshot"),
                    execute=operation_config("execute"),
                    # metadata=operation_config("metadata"),
                    # ac_tree=operation_config("ac_tree"),
                    # page_metadata=operation_config("page_metadata"),
                ),
            )
        elif env_type == EnvType.OS_WORLD:
            raise NotImplementedError("osworld is not supported yet")

        return Config(
            env_type=env_type,
            gateway=gateway,
            task_file_path=task_file_path,
            webgym=webgym,
            osworld=None,
        )
    except KeyError as exc:
        raise ValueError(f"Missing required config key: {exc.args[0]}") from exc


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="HTTP gateway for VERL-driven RL environments.")
    parser.add_argument("config_path", type=Path)
    args = parser.parse_args()
    return load_config(args.config_path)
