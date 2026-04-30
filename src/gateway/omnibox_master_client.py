from typing import Any

import requests

from ..omnibox.omnibox import OmniboxInstance
from .error import OmniBoxTransportError


class _RequestsProxy:
    def post(self, *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return requests.post(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise OmniBoxTransportError(f"requests.post failed: {exc}") from exc

    def get(self, *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return requests.get(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise OmniBoxTransportError(f"requests.get failed: {exc}") from exc


_requests = _RequestsProxy()


class MasterClient:
    def __init__(self, host, port, api_key):
        self.host = host
        self.port = port
        self.output = None
        self.instance = None
        self.api_key = api_key

    def _get_base_url(self):
        """Get the base URL with appropriate protocol (HTTPS for port 443, HTTP otherwise)"""
        protocol = "https" if self.port == 443 else "http"
        return f"{protocol}://{self.host}:{self.port}"

    def get_instance(self, lifetime_mins=120):
        url = f"{self._get_base_url()}/get"
        return _requests.post(
            url,
            params={"lifetime_mins": lifetime_mins},
            headers={"x-api-key": self.api_key},
            verify=False,
        )

    def reset(self, instance: OmniboxInstance):
        return _requests.post(
            f"{self._get_base_url()}/reset",
            params=instance,
            headers={"x-api-key": self.api_key},
            verify=False,
        )

    def execute(self, instance: OmniboxInstance, command):
        return _requests.post(
            f"{self._get_base_url()}/execute",
            json=dict(command, **instance),
            headers={"x-api-key": self.api_key},
            verify=False,
        )

    def screenshot(self, instance: OmniboxInstance):
        return _requests.get(
            f"{self._get_base_url()}/screenshot",
            params=dict(instance, **{"interaction_mode": "coordinate"}),
            headers={"x-api-key": self.api_key},
            verify=False,
            timeout=None,
            stream=True,
        )
