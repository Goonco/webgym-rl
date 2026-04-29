import base64
import io
import time
from typing import Any

from PIL import Image, UnidentifiedImageError

from environment.webgym.webgym.misc import is_white_image
from src.schemas.omnibox import OmniboxInstance
from src.webgym.client import MasterClient
from src.webgym.error import OmniboxBusyError, OmniboxInvalidScreenshotError


def navigate(host, port, api_key, instance: OmniboxInstance, url: str):
    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.execute(instance, {"visit_page": {"url": url}})

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        else:
            raise Exception(f"Error: {response.status_code} - {response.text}")

    return response.json()


def allocate_instance(host, port, api_key) -> OmniboxInstance:
    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.get_instance(45)

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        else:
            raise Exception(f"Error: {response.status_code} - {response.text}")

    return response.json()


def reset_instance(host, port, api_key, instance: OmniboxInstance) -> dict[str, Any]:
    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.reset(instance)

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")

    return response.json()


def execute_browser_command(
    host,
    port,
    api_key,
    instance: OmniboxInstance,
    command: dict[str, Any],
) -> dict[str, Any]:
    if "sleep" in command:
        time.sleep(float(command["sleep"].get("duration", 1.0)))
        return {"status": "success"}

    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.execute(instance, command)

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")

    return response.json()


def screenshot(
    host,
    port,
    api_key,
    instance,
) -> str:
    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.screenshot(instance)

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")

    try:
        image = Image.open(io.BytesIO(response.content))
        image.load()
    except UnidentifiedImageError as exc:
        raise OmniboxInvalidScreenshotError("Screenshot response is not a valid image") from exc

    if is_white_image(image):
        raise OmniboxInvalidScreenshotError("Screenshot is blank")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def get_page_snapshot(
    host: str,
    port: int,
    api_key: str,
    instance: OmniboxInstance,
    selectors: list[str] | None = None,
    include_html: bool = False,
) -> dict[str, Any]:
    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.execute(
        instance,
        {
            "get_page_snapshot": {
                "selectors": selectors or [],
                "include_html": include_html,
            }
        },
    )

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")

    return response.json()


def get_interactive_tree(
    host: str,
    port: int,
    api_key: str,
    instance: OmniboxInstance,
) -> str:
    master_client = MasterClient(host=host, port=port, api_key=api_key)
    response = master_client.execute(instance, {"get_interactive_rects": {}})

    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")

    payload: dict[str, Any] = response.json()
    return _format_interactive_regions(payload)


def _format_interactive_regions(payload: dict[str, Any]) -> str:
    lines: list[str] = []

    mouse_position = payload.get("mouse_position")
    if isinstance(mouse_position, dict):
        x = mouse_position.get("x")
        y = mouse_position.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            lines.append(f"mouse_position: ({int(x)}, {int(y)})")

    regions = payload.get("regions", {})
    for _, region in regions.items():
        text = region.get("aria_name") or region.get("aria-name") or ""
        tag = region.get("tag_name", "")
        role = region.get("role", "")
        rects = region.get("rects", [])

        if not rects:
            continue

        coords = []
        for rect in rects:
            x = int((rect.get("left", 0) + rect.get("right", 0)) / 2)
            y = int((rect.get("top", 0) + rect.get("bottom", 0)) / 2)
            coords.append(f"({x}, {y})")

        lines.append(f"tag: {tag}, role: {role}, text: {text}, coords: {', '.join(coords)}")

    return "\n".join(lines)
