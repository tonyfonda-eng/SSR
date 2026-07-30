import logging
import hashlib
import json
from typing import Dict, Any

class ConfigurationService:
    """Central authority for runtime configuration state. Validates and promotes changes."""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.logger = logging.getLogger("SSR.ConfigService")
        self._current_config: Dict[str, Any] = {}
        self._current_hash: str = ""

        # Default fallback values to safeguard bootstrapping before any external inputs arrive
        self._defaults = {
            "assignment_risk_threshold": 0.90,
            "spread_collapse_threshold": -0.05,
            "sec_poll_interval_sec": 60,
            "yahoo_poll_interval_sec": 15,
            "watchlist": []
        }
        self.load_defaults()

    def load_defaults(self):
        """Hydrates the runtime config with base system defaults."""
        self._update_state(self._defaults)

    def update_from_sheet(self, raw_sheet_data: Dict[str, Any]):
        """Sanitizes raw external configuration inputs and hot-reloads runtime if mutated."""
        sanitized = {}
        for key, value in self._defaults.items():
            # Basic type coercion using defaults as schema anchors
            if key in raw_sheet_data:
                try:
                    expected_type = type(value)
                    sanitized[key] = expected_type(raw_sheet_data[key])
                except (ValueError, TypeError):
                    self.logger.warning(f"Type coercion failed for {key}. Reverting to baseline.")
                    sanitized[key] = value
            else:
                sanitized[key] = value

        self._update_state(sanitized)

    def _update_state(self, new_config: Dict[str, Any]):
        """Calculates state fingerprint hashes and announces updates to downstream observers."""
        config_bytes = json.dumps(new_config, sort_keys=True).encode()
        new_hash = hashlib.sha256(config_bytes).hexdigest()

        if new_hash != self._current_hash:
            old_hash = self._current_hash
            self._current_config = new_config
            self._current_hash = new_hash
            
            self.logger.info(f"Configuration state hot-reloaded. Hash updated to: {new_hash[:8]}")
            
            # Publish change notification payload onto the reactive EventBus
            self.event_bus.publish("EVT.CONFIG.UPDATED", {
                "config_hash": new_hash,
                "old_hash": old_hash,
                "config": self._current_config
            })

    def get(self, key: str) -> Any:
        """Retrieves an active runtime parameter thread-safely."""
        return self._current_config.get(key, self._defaults.get(key))

    @property
    def current_hash(self) -> str:
        return self._current_hash
