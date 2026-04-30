from __future__ import annotations

import argparse
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import Body, FastAPI

from log import file_logger, runtime_logger, setup_logging
from server import WebGym
from src.schemas import (
    Config,
    ErrorResponse,
    ErrorType,
    Request,
    Response,
    WebGymRLError,
    load_config,
)
from src.task_store import TaskStore


def create_app(config: Config):
    executor = ThreadPoolExecutor(max_workers=config.gateway.max_workers)
    in_flight = asyncio.Semaphore(config.gateway.max_in_flight)
    task_store = TaskStore.from_file(config.task_file_path)
    webgym = WebGym(
        task_store=task_store,
        httpstack_config=config.httpstack_config,
        omnibox_config=config.omnibox_config,
    )
    setup_logging(config.log_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            webgym.open()
            yield
        finally:
            webgym.close()
            executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "config": config}

    @app.post("/")
    async def handle_request(
        request: Annotated[Request, Body(discriminator="op")],
    ) -> Response:
        request_started_at = time.monotonic()

        try:
            await asyncio.wait_for(
                in_flight.acquire(),
                timeout=config.gateway.in_flight_timeout,
            )
        except asyncio.TimeoutError:
            return ErrorResponse.from_type(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=ErrorType.GATEWAY_BUSY,
            )

        try:
            loop = asyncio.get_running_loop()
            gateway_deadline = request_started_at + (
                config.gateway.verl_timeout - config.gateway.deadline_margin
            )
            return await loop.run_in_executor(
                executor, webgym.handle_request, request, gateway_deadline
            )
        except Exception:
            file_logger.exception("Failed while handling %s", request)
            return ErrorResponse.from_type(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=ErrorType.FAIL_REQUEST_HANDLE,
            )
        finally:
            in_flight.release()

    return app


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    args = parser.parse_args()
    return args


def main() -> None:
    try:
        args = _parse_args()
        config = load_config(args.config_path)
        uvicorn.run(create_app(config), host=config.gateway.host, port=config.gateway.port)
    except WebGymRLError as exc:
        runtime_logger.error(exc)
        raise SystemExit(1)
    except Exception as exc:
        raise RuntimeError(f"[unexpected error] {exc}") from exc


if __name__ == "__main__":
    main()
