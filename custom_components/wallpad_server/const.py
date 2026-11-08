"""Constants of the Wallpad server integration."""

DOMAIN = "wallpad_server"

FEATURE_ID = "elevator"
CONTROL_CALL_UP = "call-up-here"
CONTROL_CALL_DOWN = "call-down-here"

FEATURES_PATH = "/api/v1/features"
SOCKET_PATH = "/api/v1/ws"

REQUEST_TIMEOUT_S = 10.0
INVOKE_TIMEOUT_S = 10.0
HEARTBEAT_S = 30.0
RECONNECT_MIN_S = 1.0
RECONNECT_MAX_S = 60.0
