from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class GatewayConfig(FrozenBaseModel):
    host: str
    port: int
    max_workers: int
    max_in_flight: int

    verl_timeout: float
    in_flight_timeout: float
    deadline_margin: float


class OperationConfig(FrozenBaseModel):
    pool_size: int
    timeout: float


class HttpStackConfig(FrozenBaseModel):
    allocate: OperationConfig
    release: OperationConfig
    navigate: OperationConfig
    screenshot: OperationConfig
    execute: OperationConfig

    ################
    # Unused Pools #
    ################

    # metadata: OperationConfig
    # ac_tree: OperationConfig
    # page_metadata: OperationConfig

    def get_pool_dict(self) -> dict[str, int]:
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


class OmniboxConfig(FrozenBaseModel):
    host: str
    master_port: int
    node_port: int
    instance_start_port: int
    api_key: str
    redis_port: int
    instances: int
    master_workers: int
    node_workers: int


class Config(FrozenBaseModel):
    gateway: GatewayConfig
    task_file_path: Path
    log_path: Path

    omnibox_config: OmniboxConfig = Field(alias="omnibox")
    httpstack_config: HttpStackConfig = Field(alias="httpstack")
