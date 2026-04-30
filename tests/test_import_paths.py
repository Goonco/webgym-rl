from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT_DIR / "src" / "main.py"
APP_PATH = ROOT_DIR / "src" / "gateway" / "app.py"
SERVICE_PATH = ROOT_DIR / "src" / "gateway" / "service.py"
REQUEST_PATH = ROOT_DIR / "src" / "gateway" / "protocol" / "request.py"
HTTP_FUNCTIONS_PATH = ROOT_DIR / "src" / "gateway" / "http_functions.py"
MASTER_CLIENT_PATH = ROOT_DIR / "src" / "gateway" / "omnibox_master_client.py"
PROCESS_ISOLATOR_PATH = (
    ROOT_DIR / "environment" / "webgym" / "webgym" / "environment" / "process_isolator.py"
)
TASK_STORE_SHIM_PATH = ROOT_DIR / "src" / "task_store.py"
WEBGYM_ERROR_SHIM_PATH = ROOT_DIR / "src" / "webgym" / "error.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ImportPathRegressionTests(unittest.TestCase):
    def test_main_uses_package_relative_imports(self) -> None:
        source = _read(MAIN_PATH)

        self.assertIn("from .gateway.app import launch", source)
        self.assertIn("from .gateway.error import ConfigError, WebGymRLError", source)
        self.assertIn("from .util.config import Config", source)
        self.assertIn("from .util.log import runtime_logger", source)
        self.assertNotIn("from gateway.error import", source)
        self.assertNotIn("from src.gateway.app import", source)

    def test_gateway_modules_use_local_relative_imports(self) -> None:
        app_source = _read(APP_PATH)
        self.assertIn("from .service import WebGym", app_source)
        self.assertIn("from ..util.config import Config", app_source)
        self.assertIn("from ..util.task_store import TaskStore", app_source)
        self.assertNotIn("from service import WebGym", app_source)
        self.assertNotIn("from util.config import", app_source)
        self.assertNotIn("from src.task_store import", app_source)

        service_source = _read(SERVICE_PATH)
        self.assertIn("from .http_functions import", service_source)
        self.assertIn("from .protocol.computer13 import", service_source)
        self.assertIn("from ..omnibox.omnibox import OmniboxInstance", service_source)
        self.assertIn("from ..util.config import HttpStackConfig, OmniboxConfig", service_source)
        self.assertIn("from ..util.task_store import TaskStore", service_source)
        self.assertNotIn("from gateway.http_functions import", service_source)
        self.assertNotIn("from omnibox.omnibox import", service_source)
        self.assertNotIn("from util.config import", service_source)

        request_source = _read(REQUEST_PATH)
        self.assertIn("from .computer13 import Computer13", request_source)
        self.assertNotIn("from gateway.protocol.computer13 import", request_source)

        http_functions_source = _read(HTTP_FUNCTIONS_PATH)
        self.assertIn("from ..omnibox.omnibox import OmniboxInstance", http_functions_source)
        self.assertNotIn("from omnibox.omnibox import", http_functions_source)

        master_client_source = _read(MASTER_CLIENT_PATH)
        self.assertIn("from ..omnibox.omnibox import OmniboxInstance", master_client_source)
        self.assertNotIn("from omnibox.omnibox import", master_client_source)

    def test_external_importers_have_compatibility_shims(self) -> None:
        self.assertTrue(TASK_STORE_SHIM_PATH.is_file())
        self.assertTrue(WEBGYM_ERROR_SHIM_PATH.is_file())

        task_store_source = _read(TASK_STORE_SHIM_PATH)
        self.assertIn("from .util.task_store import *", task_store_source)

        webgym_error_source = _read(WEBGYM_ERROR_SHIM_PATH)
        self.assertIn("from ..gateway.error import *", webgym_error_source)

        process_isolator_source = _read(PROCESS_ISOLATOR_PATH)
        self.assertIn("from src.webgym.error import HttpStackOperationTimeoutError", process_isolator_source)


if __name__ == "__main__":
    unittest.main()
