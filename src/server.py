from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from src.config import Config, EnvType, parse_args
from src.schemas.request import parse_request_base
from src.schemas.response import ErrorResponse, ErrorType, Response
from src.task_store import TaskStore
from src.webgym.service import WebGym

logger = logging.getLogger(__name__)


def create_app(config: Config):
    # Set up for parrallel execution
    executor = ThreadPoolExecutor(max_workers=config.gateway.max_workers)
    in_flight = asyncio.Semaphore(config.gateway.max_in_flight)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            env.open()
            yield
        finally:
            env.close()
            executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(
        title="CUA RL Gym",
        description="Protocol gateway for VERL-driven WebGym and OSWorld environments.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Set up for RL Environment
    if config.env_type == EnvType.WEB_GYM:
        assert config.webgym is not None
        task_store = TaskStore.from_file(config.task_file_path)
        env = WebGym(task_store=task_store, config=config.webgym)

    if config.env_type == EnvType.OS_WORLD:
        assert config.osworld is not None
        raise NotImplementedError("osworld not supported yet")

    # Open Endpoints
    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "config": config}

    @app.post("/v1/env")
    async def handle_request(payload: dict[str, Any]) -> Response:
        request_started_at = time.monotonic()

        try:
            request = parse_request_base(payload)
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Invalid request payload",
                    "errors": e.errors(),
                },
            ) from e

        try:
            await asyncio.wait_for(
                in_flight.acquire(),
                timeout=config.gateway.in_flight_timeout,
            )
        except asyncio.TimeoutError:
            return ErrorResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=ErrorType.GATEWAY_BUSY,
                message="Timed out waiting for gateway in-flight capacity.",
            )

        gateway_deadline = request_started_at + (
            config.gateway.verl_timeout - config.gateway.deadline_margin
        )
        try:
            if time.monotonic() >= gateway_deadline:
                return ErrorResponse(
                    session_id=request.session_id,
                    task_id=request.task_id,
                    error_type=ErrorType.GATEWAY_BUSY,
                    message="No operation budget remains after gateway admission.",
                )

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                executor, env.handle_request, request, gateway_deadline
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to handle environment request",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            ) from exc
        finally:
            in_flight.release()

    return app


def validate_config(config: Config) -> None:
    gateway_config = config.gateway
    if gateway_config.max_workers < gateway_config.max_in_flight:
        logger.warning(
            "Gateway max_workers (%s) is smaller than max_in_flight (%s). "
            "Requests may acquire in-flight slots faster than executor workers "
            "can process them, which can lead to queued HTTP sessions timing out. "
            "Consider setting max_workers >= max_in_flight.",
            gateway_config.max_workers,
            gateway_config.max_in_flight,
        )


def main() -> None:
    config = parse_args()
    validate_config(config)
    uvicorn.run(create_app(config), host=config.gateway.host, port=config.gateway.port)


if __name__ == "__main__":
    main()
