"""Constants for the Zoned Heating Thermostat integration."""

DOMAIN = "zoned_thermostat"
NAME = "Zoned Heating Thermostat"
VERSION = "1.0.0"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"
SAVE_DELAY = 10  # Seconds to debounce storage saves

# Default temperature thresholds and limits (°C)
DEFAULT_MIN_TEMP = 10.0
DEFAULT_MAX_TEMP = 28.0
DEFAULT_TEMP_STEP = 0.5
DEFAULT_HYSTERESIS = 0.2

# Default pump protection timings (seconds)
DEFAULT_PUMP_MIN_ON_TIME = 120      # 2 minutes
DEFAULT_PUMP_MIN_OFF_TIME = 120     # 2 minutes
DEFAULT_PUMP_STARTUP_DELAY = 15     # 15 seconds (allows TRV to start opening)
DEFAULT_PUMP_SHUTDOWN_DELAY = 30    # 30 seconds (overrun dissipation)

# Window and Presence defaults
DEFAULT_WINDOW_DELAY = 15           # 15 seconds before turning off room demand
DEFAULT_AWAY_TEMP = 16.0
DEFAULT_FROST_TEMP = 10.0

# Presets defaults (°C)
DEFAULT_PRESET_COMFORT = 21.0
DEFAULT_PRESET_ECO = 18.0
DEFAULT_PRESET_SLEEP = 17.0
DEFAULT_PRESET_AWAY = 16.0
DEFAULT_PRESET_FROST = 10.0

DEFAULT_PRESETS = {
    "comfort": DEFAULT_PRESET_COMFORT,
    "eco": DEFAULT_PRESET_ECO,
    "sleep": DEFAULT_PRESET_SLEEP,
    "away": DEFAULT_PRESET_AWAY,
    "frost": DEFAULT_PRESET_FROST,
}

# Supported platforms
PLATFORMS = ["climate", "binary_sensor", "sensor"]

# WebSocket endpoints prefix
WS_PREFIX = f"{DOMAIN}/"

# Event Log max size
DEFAULT_EVENT_LOG_SIZE = 100
