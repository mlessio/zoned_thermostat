"""Unit tests for panel registration and websocket coordinator lookup."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.zoned_thermostat.const import DOMAIN
from custom_components.zoned_thermostat.panel import (
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    async_register_panel,
    async_unregister_panel,
)
from custom_components.zoned_thermostat.websocket import _get_coordinator


class TestPanelAndWebsocket(unittest.TestCase):
    """Test panel registration and websocket API helpers."""

    def test_get_coordinator_ignores_non_dict_metadata(self):
        """Verify _get_coordinator safely handles non-dict entries like _ws_registered = True."""
        mock_hass = MagicMock()
        mock_coordinator = MagicMock()
        mock_hass.data = {
            DOMAIN: {
                "_ws_registered": True,  # Boolean metadata flag
                "another_flag": "test",
                "valid_entry_id": {
                    "coordinator": mock_coordinator,
                    "system": MagicMock(),
                },
            }
        }

        # 1. Lookup without entry_id should find the valid entry dict
        coord = _get_coordinator(mock_hass, "")
        self.assertEqual(coord, mock_coordinator)

        # 2. Lookup with specific entry_id
        coord_specific = _get_coordinator(mock_hass, "valid_entry_id")
        self.assertEqual(coord_specific, mock_coordinator)

    def test_async_register_panel_uses_panel_custom(self):
        """Verify async_register_panel calls panel_custom.async_register_panel with webcomponent_name."""
        mock_hass = MagicMock()
        mock_hass.data = {"frontend_panels": {}}
        mock_hass.http = MagicMock()

        mock_panel_custom = MagicMock()
        mock_panel_custom.async_register_panel = AsyncMock()

        with patch.dict(
            "sys.modules",
            {
                "homeassistant.components.panel_custom": mock_panel_custom,
            },
        ):
            # Patch inside panel module
            with patch(
                "custom_components.zoned_thermostat.panel.panel_custom",
                mock_panel_custom,
            ):
                asyncio.run(async_register_panel(mock_hass))

                mock_panel_custom.async_register_panel.assert_awaited_once_with(
                    mock_hass,
                    frontend_url_path=PANEL_URL,
                    webcomponent_name="zoned-thermostat-panel",
                    sidebar_title=PANEL_TITLE,
                    sidebar_icon=PANEL_ICON,
                    module_url="/zoned_thermostat_static/zoned-thermostat-panel.js",
                    require_admin=False,
                    embed_iframe=False,
                )

    def test_async_register_panel_skips_if_already_registered(self):
        """Verify async_register_panel does not re-register if PANEL_URL is already present."""
        mock_hass = MagicMock()
        mock_hass.data = {"frontend_panels": {PANEL_URL: MagicMock()}}
        mock_panel_custom = MagicMock()
        mock_panel_custom.async_register_panel = AsyncMock()

        with patch(
            "custom_components.zoned_thermostat.panel.panel_custom",
            mock_panel_custom,
        ):
            asyncio.run(async_register_panel(mock_hass))
            mock_panel_custom.async_register_panel.assert_not_called()

    def test_async_register_static_paths_with_static_path_config(self):
        """Verify static paths are registered using StaticPathConfig."""
        mock_hass = MagicMock()
        mock_hass.data = {DOMAIN: {}, "frontend_panels": {}}
        mock_hass.http = MagicMock()
        mock_hass.http.async_register_static_paths = AsyncMock()

        mock_config_cls = MagicMock()
        mock_panel_custom = MagicMock()
        mock_panel_custom.async_register_panel = AsyncMock()

        with patch.dict(
            "sys.modules",
            {
                "homeassistant.components.http": MagicMock(StaticPathConfig=mock_config_cls),
                "homeassistant.components.panel_custom": mock_panel_custom,
            },
        ):
            with patch("custom_components.zoned_thermostat.panel.panel_custom", mock_panel_custom):
                asyncio.run(async_register_panel(mock_hass))

                mock_hass.http.async_register_static_paths.assert_awaited_once()
                self.assertTrue(mock_hass.data[DOMAIN].get("_static_paths_registered"))


if __name__ == "__main__":
    unittest.main()
