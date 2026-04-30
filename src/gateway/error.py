class WebGymRLError(Exception):
    pass


class ConfigError(WebGymRLError):
    pass


class WebGymEnvRetryableError(Exception):
    pass


class OmniboxBusyError(WebGymEnvRetryableError):
    pass


class OmniBoxTransportError(WebGymEnvRetryableError):
    pass


class HttpStackOperationTimeoutError(WebGymEnvRetryableError):
    pass


class OmniboxInvalidScreenshotError(WebGymEnvRetryableError):
    pass
