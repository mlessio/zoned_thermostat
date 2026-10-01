/**
 * Zoned Heating Thermostat - Dedicated Full-Width Frontend Panel
 * Native Custom Web Component for Home Assistant
 */

class ZonedThermostatPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._systemData = null;
    this._diagnosticEvents = [];
    this._activeTab = "dashboard"; // "dashboard" | "scheduler" | "diagnostics"
    this._selectedRoomId = null;
    this._selectedDay = "mon";
    this._pollInterval = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._systemData) {
      this._loadData();
    }
  }

  connectedCallback() {
    this._loadData();
    // Poll updates every 10 seconds for real-time reactivity
    this._pollInterval = setInterval(() => this._loadData(), 10000);
  }

  disconnectedCallback() {
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
      this._pollInterval = null;
    }
  }

  async _loadData() {
    if (!this._hass) return;
    try {
      const data = await this._hass.callWS({
        type: "zoned_thermostat/get_overview",
      });
      this._systemData = data;
      if (!this._selectedRoomId && data.zones) {
        for (const z of Object.values(data.zones)) {
          if (z.rooms && Object.keys(z.rooms).length > 0) {
            this._selectedRoomId = Object.keys(z.rooms)[0];
            break;
          }
        }
      }
      this._render();
    } catch (err) {
      console.warn("Could not fetch zoned_thermostat overview:", err);
    }
  }

  async _setGlobalMode(mode) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_global_mode",
      mode: mode,
    });
    await this._loadData();
  }

  async _setRoomOverride(roomId, target, mode = "until_next_change", durationMinutes = null) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_room_override",
      room_id: roomId,
      target: parseFloat(target),
      mode: mode,
      duration_minutes: durationMinutes,
    });
    await this._loadData();
  }

  async _clearRoomOverride(roomId) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/clear_room_override",
      room_id: roomId,
    });
    await this._loadData();
  }

  async _setRoomHvacMode(roomId, hvacMode) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_room_hvac_mode",
      room_id: roomId,
      hvac_mode: hvacMode,
    });
    await this._loadData();
  }

  async _copySchedule(sourceId, targetId) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/copy_schedule",
      source_room_id: sourceId,
      target_room_id: targetId,
    });
    await this._loadData();
  }

  async _updatePreset(presetName, val) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_preset",
      preset_name: presetName,
      value: parseFloat(val),
    });
    await this._loadData();
  }

  async _setZonePumpManual(zoneId, manualOn) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_zone_pump_manual",
      zone_id: zoneId,
      manual_on: manualOn,
    });
    await this._loadData();
  }

  async _applyRoomPreset(roomId, preset) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/apply_room_preset",
      room_id: roomId,
      preset: preset,
    });
    await this._loadData();
  }

  async _setRoomPresets(roomId, presets) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_room_presets",
      room_id: roomId,
      presets: presets,
    });
    await this._loadData();
  }

  async _setBufferSettings(sensorId, minTemp, hysteresis) {
    if (!this._hass) return;
    await this._hass.callWS({
      type: "zoned_thermostat/set_buffer_settings",
      sensor_id: sensorId,
      min_temp: parseFloat(minTemp),
      hysteresis: parseFloat(hysteresis),
    });
    await this._loadData();
  }

  _render() {
    if (!this._systemData) {
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; padding: 32px; font-family: var(--paper-font-body1_-_font-family, sans-serif); color: var(--primary-text-color); }
          .loading { text-align: center; margin-top: 100px; font-size: 1.2rem; }
        </style>
        <div class="loading">Caricamento Zoned Heating Thermostat...</div>
      `;
      return;
    }

    const sys = this._systemData;
    const globalMode = sys.global_mode || "home";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          background: var(--primary-background-color, #111111);
          color: var(--primary-text-color, #ffffff);
          min-height: 100vh;
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
          box-sizing: border-box;
          padding: 24px 32px 64px 32px;
        }

        /* Top Header */
        .header {
          display: flex;
          flex-wrap: wrap;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          border-bottom: 1px solid var(--divider-color, rgba(255,255,255,0.12));
          padding-bottom: 20px;
          margin-bottom: 24px;
        }

        .header-title-box h1 {
          margin: 0;
          font-size: 2rem;
          font-weight: 700;
          letter-spacing: -0.5px;
        }

        .header-title-box p {
          margin: 4px 0 0 0;
          font-size: 0.95rem;
          color: var(--secondary-text-color, #9e9e9e);
        }

        .header-status-bar {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }

        .mode-chips {
          display: flex;
          background: var(--card-background-color, #1e1e1e);
          border-radius: 28px;
          padding: 4px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.08));
        }

        .mode-btn {
          border: none;
          background: transparent;
          color: var(--secondary-text-color, #9e9e9e);
          padding: 8px 16px;
          border-radius: 20px;
          cursor: pointer;
          font-weight: 600;
          font-size: 0.85rem;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .mode-btn.active {
          background: var(--primary-color, #03a9f4);
          color: #ffffff;
          box-shadow: 0 2px 8px rgba(3, 169, 244, 0.4);
        }

        .badge-metric {
          background: var(--card-background-color, #1e1e1e);
          padding: 8px 14px;
          border-radius: 20px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.08));
          font-size: 0.85rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        /* Navigation Tabs */
        .nav-tabs {
          display: flex;
          gap: 12px;
          margin-bottom: 28px;
          border-bottom: 1px solid var(--divider-color, rgba(255,255,255,0.08));
          padding-bottom: 12px;
        }

        .tab-btn {
          background: none;
          border: none;
          color: var(--secondary-text-color, #9e9e9e);
          font-size: 1.05rem;
          font-weight: 600;
          padding: 8px 16px;
          cursor: pointer;
          border-radius: 8px;
          transition: all 0.2s;
        }

        .tab-btn:hover {
          color: var(--primary-text-color, #ffffff);
          background: rgba(255,255,255,0.04);
        }

        .tab-btn.active {
          color: var(--primary-color, #03a9f4);
          background: rgba(3, 169, 244, 0.12);
        }

        /* ZONE LAYOUT */
        .zones-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
          gap: 24px;
          margin-bottom: 32px;
        }

        @media (max-width: 600px) {
          .zones-grid { grid-template-columns: 1fr; }
        }

        .zone-card {
          background: var(--card-background-color, #1c1c1e);
          border: 1px solid var(--divider-color, rgba(255,255,255,0.1));
          border-radius: 16px;
          padding: 20px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }

        .zone-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          padding-bottom: 16px;
          margin-bottom: 20px;
        }

        .zone-title {
          font-size: 1.4rem;
          font-weight: 700;
          margin: 0;
        }

        .pump-indicator {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          font-weight: 700;
          padding: 6px 12px;
          border-radius: 20px;
        }

        .pump-on {
          background: rgba(255, 111, 0, 0.2);
          color: #ff9800;
          border: 1px solid rgba(255, 152, 0, 0.4);
        }

        .pump-off {
          background: rgba(255, 255, 255, 0.05);
          color: #9e9e9e;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .pump-reason {
          font-size: 0.85rem;
          color: var(--secondary-text-color, #a0a0a0);
          margin-bottom: 16px;
          padding: 8px 12px;
          background: rgba(0,0,0,0.2);
          border-radius: 8px;
          border-left: 3px solid var(--primary-color, #03a9f4);
        }

        /* ROOMS LIST */
        .rooms-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .room-item {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
          padding: 16px;
          transition: background 0.2s;
        }

        .room-item:hover {
          background: rgba(255, 255, 255, 0.05);
        }

        .room-top-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .room-name-box {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .room-name {
          font-size: 1.15rem;
          font-weight: 600;
          margin: 0;
        }

        .badge-status {
          font-size: 0.75rem;
          padding: 3px 8px;
          border-radius: 12px;
          font-weight: 700;
        }

        .badge-heating {
          background: #d84315;
          color: #ffffff;
        }

        .badge-reached {
          background: #2e7d32;
          color: #ffffff;
        }

        .badge-idle {
          background: rgba(255,255,255,0.1);
          color: #bdbdbd;
        }

        .badge-window {
          background: #0288d1;
          color: #ffffff;
        }

        .badge-override {
          background: #6a1b9a;
          color: #ffffff;
        }

        .room-temp-row {
          display: flex;
          align-items: baseline;
          gap: 8px;
          margin-bottom: 14px;
        }

        .current-temp-big {
          font-size: 2.2rem;
          font-weight: 700;
          letter-spacing: -1px;
        }

        .target-temp-display {
          font-size: 1.1rem;
          color: var(--secondary-text-color, #9e9e9e);
        }

        /* Controls Row */
        .controls-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 10px;
        }

        .temp-stepper {
          display: flex;
          align-items: center;
          background: rgba(255,255,255,0.06);
          border-radius: 8px;
          overflow: hidden;
        }

        .step-btn {
          border: none;
          background: transparent;
          color: #ffffff;
          padding: 6px 12px;
          font-size: 1.2rem;
          font-weight: 700;
          cursor: pointer;
        }

        .step-btn:hover {
          background: rgba(255,255,255,0.12);
        }

        .preset-pill {
          border: none;
          background: rgba(255,255,255,0.05);
          color: #e0e0e0;
          padding: 6px 10px;
          border-radius: 6px;
          font-size: 0.8rem;
          font-weight: 600;
          cursor: pointer;
        }

        .preset-pill:hover {
          background: rgba(255,255,255,0.12);
        }

        .trv-badge-list {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 10px;
          font-size: 0.78rem;
          color: #888888;
        }

        .trv-tag {
          background: rgba(0,0,0,0.3);
          padding: 2px 6px;
          border-radius: 4px;
        }

        .clickable-target {
          cursor: pointer;
          text-decoration: underline dotted rgba(255,255,255,0.4);
          border-radius: 4px;
          padding: 2px 6px;
          transition: all 0.2s ease;
        }

        .clickable-target:hover {
          color: var(--primary-color, #03a9f4);
          background: rgba(3, 169, 244, 0.15);
        }

        .pump-manual-toggle {
          border: none;
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 0.82rem;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .pump-manual-auto {
          background: rgba(255, 255, 255, 0.08);
          color: #e0e0e0;
          border: 1px solid rgba(255, 255, 255, 0.15);
        }

        .pump-manual-auto:hover {
          background: rgba(255, 255, 255, 0.16);
          color: #ffffff;
        }

        .pump-manual-on {
          background: #e65100;
          color: #ffffff;
          box-shadow: 0 0 12px rgba(230, 81, 0, 0.6);
          border: 1px solid #ff9800;
        }

        .pump-manual-on:hover {
          background: #f57c00;
        }

        .preset-pill.active-preset {
          background: var(--primary-color, #03a9f4) !important;
          color: #ffffff !important;
          box-shadow: 0 2px 10px rgba(3, 169, 244, 0.5) !important;
          font-weight: 700;
        }

        .badge-buffer-ready {
          border-color: rgba(76, 175, 80, 0.4) !important;
          background: rgba(76, 175, 80, 0.12) !important;
        }

        .badge-buffer-waiting {
          border-color: rgba(255, 152, 0, 0.4) !important;
          background: rgba(255, 152, 0, 0.12) !important;
        }

        /* SCHEDULER VIEW */
        .scheduler-container {
          background: var(--card-background-color, #1c1c1e);
          border-radius: 16px;
          padding: 24px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.1));
        }

        .scheduler-controls {
          display: flex;
          flex-wrap: wrap;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          margin-bottom: 24px;
        }

        .days-bar {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .day-chip {
          border: 1px solid rgba(255,255,255,0.1);
          background: transparent;
          color: #ffffff;
          padding: 8px 14px;
          border-radius: 10px;
          font-weight: 600;
          cursor: pointer;
        }

        .day-chip.active {
          background: var(--primary-color, #03a9f4);
          border-color: var(--primary-color, #03a9f4);
        }

        .schedule-table {
          width: 100%;
          border-collapse: collapse;
          margin-top: 16px;
        }

        .schedule-table th, .schedule-table td {
          padding: 12px 16px;
          text-align: left;
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        .schedule-table th {
          color: var(--secondary-text-color, #888888);
          font-size: 0.85rem;
          text-transform: uppercase;
        }

        .action-link {
          color: var(--primary-color, #03a9f4);
          cursor: pointer;
          font-weight: 600;
          text-decoration: underline;
        }

        /* DIAGNOSTICS TIMELINE */
        .timeline {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-width: 800px;
        }

        .timeline-item {
          background: rgba(255,255,255,0.03);
          border-left: 4px solid var(--primary-color, #03a9f4);
          border-radius: 0 8px 8px 0;
          padding: 12px 16px;
        }

        .timeline-time {
          font-size: 0.8rem;
          color: #888888;
        }

        .timeline-msg {
          font-size: 0.95rem;
          font-weight: 500;
          margin-top: 4px;
        }
      </style>

      <!-- HEADER -->
      <div class="header">
        <div class="header-title-box">
          <h1>${sys.name}</h1>
          <p>Controllo Intelligente del Riscaldamento a Zone</p>
        </div>

        <div class="header-status-bar">
          <div class="mode-chips">
            <button class="mode-btn ${globalMode === 'home' ? 'active' : ''}" id="mode-home">🏠 Casa</button>
            <button class="mode-btn ${globalMode === 'away' ? 'active' : ''}" id="mode-away">🚗 Fuori</button>
            <button class="mode-btn ${globalMode === 'frost' ? 'active' : ''}" id="mode-frost">❄️ Antigelo</button>
            <button class="mode-btn ${globalMode === 'off' ? 'active' : ''}" id="mode-off">⏹ Spento</button>
          </div>

          <div class="badge-metric">
            <span>🔥 Richiesta Totale:</span>
            <span style="color: ${sys.total_heat_demand ? '#ff9800' : '#4caf50'}">
              ${sys.total_heat_demand ? 'ATTIVA' : 'OFF'}
            </span>
          </div>

          <div class="badge-metric">
            <span>Zone Attive: ${sys.total_active_zones_count} / ${Object.keys(sys.zones || {}).length}</span>
          </div>

          ${sys.buffer_temp_sensor ? `
            <div class="badge-metric ${sys.is_buffer_ready ? 'badge-buffer-ready' : 'badge-buffer-waiting'}" title="Sensore: ${sys.buffer_temp_sensor} | Isteresi stop: ${sys.buffer_temp_hysteresis}°C">
              <span>🛢️ Accumulo:</span>
              <strong style="color: #ffffff;">${sys.buffer_current_temp !== null && sys.buffer_current_temp !== undefined ? `${sys.buffer_current_temp}°C` : '--'}</strong>
              <span style="font-size: 0.78rem; opacity: 0.85;">(min ${sys.buffer_min_temp}°C)</span>
              <span style="font-weight: 700; color: ${sys.is_buffer_ready ? '#4caf50' : '#ff9800'}">
                ${sys.is_buffer_ready ? '✓ PRONTO' : '⏳ IN ATTESA'}
              </span>
            </div>
          ` : ''}
        </div>
      </div>

      <!-- TABS -->
      <div class="nav-tabs">
        <button class="tab-btn ${this._activeTab === 'dashboard' ? 'active' : ''}" id="tab-dash">Panoramica & Zone</button>
        <button class="tab-btn ${this._activeTab === 'scheduler' ? 'active' : ''}" id="tab-sched">Pianificazione Settimanale</button>
        <button class="tab-btn ${this._activeTab === 'config' ? 'active' : ''}" id="tab-config">⚙️ Configurazione & Entità</button>
        <button class="tab-btn ${this._activeTab === 'diagnostics' ? 'active' : ''}" id="tab-diag">Diagnostica & Timeline</button>
      </div>

      <!-- CONTENT SWITCH -->
      <div id="tab-content">
        ${this._activeTab === 'dashboard' ? this._renderDashboard(sys) : ''}
        ${this._activeTab === 'scheduler' ? this._renderScheduler(sys) : ''}
        ${this._activeTab === 'config' ? this._renderConfiguration(sys) : ''}
        ${this._activeTab === 'diagnostics' ? this._renderDiagnostics(sys) : ''}
      </div>
    `;

    this._bindEvents();
  }

  _renderDashboard(sys) {
    const zones = Object.values(sys.zones || {});
    if (zones.length === 0) {
      return `<div style="text-align: center; padding: 40px;">Nessuna zona configurata nell'impianto.</div>`;
    }

    return `
      <div class="zones-grid">
        ${zones.map(z => this._renderZoneCard(z)).join("")}
      </div>
    `;
  }

  _renderZoneCard(zone) {
    const isPumpOn = zone.pump && zone.pump.is_physically_on;
    const pumpState = zone.pump ? zone.pump.state : 'off';
    const pumpReason = zone.pump ? zone.pump.status_reason : 'N/D';
    const isManual = Boolean(zone.manual_pump_mode);
    const rooms = Object.values(zone.rooms || {});

    return `
      <div class="zone-card">
        <div class="zone-header">
          <div>
            <h2 class="zone-title">${zone.name}</h2>
            <div style="font-size: 0.8rem; color: #888; margin-top: 2px;">
              Pompa: <code>${zone.pump ? zone.pump.pump_switch_id : 'N/D'}</code>
            </div>
          </div>
          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <button class="pump-manual-toggle ${isManual ? 'pump-manual-on' : 'pump-manual-auto'}"
                    data-action="toggle-pump-manual"
                    data-zone="${zone.zone_id}"
                    data-manual="${isManual}"
                    title="Clicca per forzare l'accensione manuale della pompa della zona">
              ${isManual ? '🔥 Pompa: MANUALE ON' : '⚙️ Pompa: AUTO'}
            </button>
            <div class="pump-indicator ${isPumpOn ? 'pump-on' : 'pump-off'}">
              <span>${isPumpOn ? '● ATTIVA' : '○ SPENTA'}</span>
            </div>
          </div>
        </div>

        <div class="pump-reason">
          <strong>Stato Pompa:</strong> ${pumpReason}
          ${isManual ? '<div style="margin-top: 4px; color: #ffb74d; font-weight: 600;">⚠️ Modalità forzata manuale attiva: pompa accesa indipendentemente dai setpoint.</div>' : ''}
        </div>

        <div class="rooms-list">
          ${rooms.map(r => this._renderRoomItem(r)).join("")}
        </div>
      </div>
    `;
  }

  _renderRoomItem(room) {
    const currTemp = room.current_temp !== null && room.current_temp !== undefined ? `${room.current_temp}°C` : "--";
    const targetTemp = `${room.target_temp}°C`;

    let badgeClass = "badge-idle";
    let badgeText = "A RIPOSO";
    if (room.state === "heating") {
      badgeClass = "badge-heating";
      badgeText = "🔥 RISCALDAMENTO";
    } else if (room.state === "target_reached") {
      badgeClass = "badge-reached";
      badgeText = "✓ RAGGIUNTO";
    } else if (room.state === "window_open") {
      badgeClass = "badge-window";
      badgeText = "⏸ FINESTRA APERTA";
    } else if (room.manual_override) {
      badgeClass = "badge-override";
      badgeText = "⏱ OVERRIDE";
    }

    const trvEntries = Object.entries(room.trv_states || {});
    const eff = room.effective_presets || {};
    const comfortVal = eff.comfort !== undefined ? eff.comfort : 21.0;
    const ecoVal = eff.eco !== undefined ? eff.eco : 18.0;

    const isComfortActive = Math.abs(room.target_temp - comfortVal) < 0.1;
    const isEcoActive = Math.abs(room.target_temp - ecoVal) < 0.1;

    return `
      <div class="room-item">
        <div class="room-top-row">
          <div class="room-name-box">
            <h3 class="room-name">${room.name}</h3>
            <span class="badge-status ${badgeClass}">${badgeText}</span>
          </div>
          <div>
            ${room.hvac_mode === 'off' ? `
              <button class="preset-pill" data-action="set-hvac" data-room="${room.room_id}" data-mode="heat">Accendi</button>
            ` : `
              <button class="preset-pill" data-action="set-hvac" data-room="${room.room_id}" data-mode="off">Spegni</button>
            `}
          </div>
        </div>

        <div class="room-temp-row">
          <span class="current-temp-big">${currTemp}</span>
          <span class="target-temp-display">/ target <span class="clickable-target" data-action="prompt-target" data-room="${room.room_id}" data-target="${room.target_temp}" data-name="${room.name}" title="Clicca per impostare la temperatura">${targetTemp} ✏️</span></span>
        </div>

        <div class="controls-row">
          <div class="temp-stepper">
            <button class="step-btn" data-action="step-down" data-room="${room.room_id}" data-target="${room.target_temp}" title="Diminuisci di 0.5°C">-</button>
            <span class="clickable-target" style="padding: 0 10px; font-weight: 700; font-size: 0.95rem;" data-action="prompt-target" data-room="${room.room_id}" data-target="${room.target_temp}" data-name="${room.name}" title="Clicca per digitare il setpoint">${targetTemp}</span>
            <button class="step-btn" data-action="step-up" data-room="${room.room_id}" data-target="${room.target_temp}" title="Aumenta di 0.5°C">+</button>
          </div>

          <button class="preset-pill ${isComfortActive ? 'active-preset' : ''}"
                  data-action="apply-preset"
                  data-room="${room.room_id}"
                  data-preset="comfort"
                  title="Imposta modalità Comfort (${comfortVal}°C)">
            Comfort (${comfortVal}°)
          </button>
          <button class="preset-pill ${isEcoActive ? 'active-preset' : ''}"
                  data-action="apply-preset"
                  data-room="${room.room_id}"
                  data-preset="eco"
                  title="Imposta modalità Eco (${ecoVal}°C)">
            Eco (${ecoVal}°)
          </button>

          ${room.manual_override ? `
            <button class="preset-pill" style="color: #ff5252;" data-action="clear-override" data-room="${room.room_id}" title="Ripristina programmazione oraria">Annulla Override</button>
          ` : ''}
        </div>

        ${trvEntries.length > 0 ? `
          <div class="trv-badge-list">
            ${trvEntries.map(([tId, tData]) => {
              const valve = tData.valve !== null && tData.valve !== undefined ? `${tData.valve}%` : 'sincronizzata';
              return `<span class="trv-tag">TRV: ${valve}</span>`;
            }).join("")}
          </div>
        ` : ''}
      </div>
    `;
  }

  _renderScheduler(sys) {
    const allRooms = [];
    for (const z of Object.values(sys.zones || {})) {
      for (const r of Object.values(z.rooms || {})) {
        allRooms.push(r);
      }
    }

    const currentRoom = allRooms.find(r => r.room_id === this._selectedRoomId) || allRooms[0];
    if (!currentRoom) return `<div>Nessuna stanza disponibile per la pianificazione.</div>`;

    const dayEntries = (currentRoom.schedule && currentRoom.schedule[this._selectedDay]) || [];

    return `
      <div class="scheduler-container">
        <div class="scheduler-controls">
          <div>
            <label style="font-weight: 600; margin-right: 8px;">Seleziona Stanza:</label>
            <select id="select-room-scheduler" style="padding: 8px 12px; border-radius: 8px; background: #2c2c2e; color: #fff; border: 1px solid #444;">
              ${allRooms.map(r => `
                <option value="${r.room_id}" ${r.room_id === currentRoom.room_id ? 'selected' : ''}>${r.name}</option>
              `).join("")}
            </select>
          </div>

          <div class="days-bar">
            ${['mon','tue','wed','thu','fri','sat','sun'].map(d => {
              const label = { mon: 'Lun', tue: 'Mar', wed: 'Mer', thu: 'Gio', fri: 'Ven', sat: 'Sab', sun: 'Dom' }[d];
              return `<button class="day-chip ${this._selectedDay === d ? 'active' : ''}" data-day="${d}">${label}</button>`;
            }).join("")}
          </div>
        </div>

        <table class="schedule-table">
          <thead>
            <tr>
              <th>Inizio</th>
              <th>Fine</th>
              <th>Preset / Target</th>
              <th>Azione</th>
            </tr>
          </thead>
          <tbody>
            ${dayEntries.length > 0 ? dayEntries.map((e, idx) => `
              <tr>
                <td><strong>${e.start}</strong></td>
                <td><strong>${e.end}</strong></td>
                <td>${e.preset ? e.preset.toUpperCase() : `${e.target_temp}°C`}</td>
                <td><span class="action-link" data-action="edit-slot" data-idx="${idx}">Modifica</span></td>
              </tr>
            `).join("") : `
              <tr><td colspan="4" style="text-align: center; color: #888;">Nessun blocco per questo giorno (usa Eco di fallback).</td></tr>
            `}
          </tbody>
        </table>

        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; flex-wrap: wrap;">
          <button class="day-chip" id="btn-copy-to-week">Copia ${this._selectedDay.toUpperCase()} su tutta la settimana</button>
        </div>
      </div>
    `;
  }

  _renderDiagnostics(sys) {
    const events = sys.recent_events || [];

    return `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 24px;">
        <div>
          <h3>Timeline Decisionale</h3>
          <div class="timeline">
            ${events.length > 0 ? events.map(ev => `
              <div class="timeline-item">
                <div class="timeline-time">${ev.iso_time.substring(11, 19)} - [${ev.entity_type.toUpperCase()}] ${ev.entity_name}</div>
                <div class="timeline-msg">${ev.message}</div>
              </div>
            `).join("") : `
              <div style="color: #888;">Nessun evento registrato finora.</div>
            `}
          </div>
        </div>

        <div>
          <h3>Stato Tecnico Impianto</h3>
          <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 12px; font-family: monospace; font-size: 0.85rem; line-height: 1.6;">
            <div><strong>System ID:</strong> ${sys.system_id}</div>
            <div><strong>Modalità Globale:</strong> ${sys.global_mode}</div>
            <div><strong>Richiesta Calore:</strong> ${sys.total_heat_demand ? 'ATTIVA' : 'OFF'}</div>
            <br/>
            ${Object.values(sys.zones || {}).map(z => `
              <div><strong>Zona: ${z.name}</strong></div>
              <div>• Pompa Switch: ${z.pump.pump_switch_id}</div>
              <div>• Stato Pompa: ${z.pump.state} (fisicamente: ${z.pump.is_physically_on ? 'ON' : 'OFF'})</div>
              <div>• Tempo min ON/OFF: ${z.pump.min_on_time}s / ${z.pump.min_off_time}s</div>
              <div>• Ritardo avvio/stop: ${z.pump.startup_delay}s / ${z.pump.shutdown_delay}s</div>
              <br/>
            `).join("")}
          </div>
        </div>
      </div>
    `;
  }

  _renderConfiguration(sys) {
    const zones = Object.values(sys.zones || {});
    return `
      <div style="display: flex; flex-direction: column; gap: 24px;">
        <div style="background: rgba(3, 169, 244, 0.1); border: 1px solid rgba(3, 169, 244, 0.3); border-radius: 12px; padding: 18px 22px;">
          <h3 style="margin: 0 0 8px 0; color: var(--primary-color, #03a9f4); font-size: 1.15rem;">🛠️ Configurazione & Gestione Entità</h3>
          <p style="margin: 0; line-height: 1.6; font-size: 0.95rem;">
            Tutti i sensori di temperatura, le valvole termostatiche (TRV), gli switch delle pompe, le soglie dell'accumulo e i preset delle singole stanze possono essere gestiti direttamente qui o nel wizard:
            <br/>Vai in <strong>Impostazioni &rarr; Dispositivi e Servizi &rarr; Zoned Heating Thermostat &rarr; CONFIGURA</strong>.
          </p>
        </div>

        <!-- Buffer Tank Management Card -->
        <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 18px 22px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 12px;">
            <h3 style="margin: 0; font-size: 1.2rem; display: flex; align-items: center; gap: 8px;">
              🛢️ Accumulo Termico / Puffer (Interblocco Pompe)
            </h3>
            <button class="preset-pill" data-action="edit-buffer-settings" style="font-size: 0.85rem; padding: 6px 14px; background: rgba(3, 169, 244, 0.2); border: 1px solid rgba(3, 169, 244, 0.4); color: #fff;">
              ✏️ Modifica Soglie Accumulo
            </button>
          </div>
          <div style="font-size: 0.9rem; line-height: 1.8; color: #ddd;">
            <div>• <strong>Sensore Temperatura:</strong> <code>${sys.buffer_temp_sensor || 'Nessuno (controllo disattivato, pompe libere)'}</code></div>
            <div>• <strong>Temperatura Attuale:</strong> <strong>${sys.buffer_current_temp !== null && sys.buffer_current_temp !== undefined ? `${sys.buffer_current_temp}°C` : 'N/D'}</strong></div>
            <div>• <strong>Soglia Minima di Avvio:</strong> ${sys.buffer_min_temp}°C (le pompe non partono finché l'accumulo non raggiunge questo valore)</div>
            <div>• <strong>Isteresi di Spegnimento:</strong> ${sys.buffer_temp_hysteresis}°C (spegne le pompe se l'acqua scende sotto a ${(sys.buffer_min_temp - sys.buffer_temp_hysteresis).toFixed(1)}°C)</div>
            <div>• <strong>Stato Riserva:</strong> <strong style="color: ${sys.is_buffer_ready ? '#4caf50' : '#ff9800'}">${sys.is_buffer_ready ? '✓ PRONTO (avvio pompe autorizzato)' : '⏳ IN ATTESA RISERVA (pompe bloccate)'}</strong></div>
          </div>
        </div>

        <div class="zones-grid">
          ${zones.map(z => `
            <div class="zone-card">
              <div class="zone-header">
                <h3 class="zone-title" style="font-size: 1.3rem;">Zona: ${z.name}</h3>
                <span class="badge-status badge-idle">ID: ${z.zone_id}</span>
              </div>

              <div style="font-size: 0.88rem; line-height: 1.6; margin-bottom: 18px; background: rgba(0,0,0,0.25); padding: 14px; border-radius: 8px;">
                <div><strong>Pompa associata:</strong> <code>${z.pump ? z.pump.pump_switch_id : 'N/D'}</code></div>
                <div><strong>Modalità Pompa:</strong> <strong>${z.manual_pump_mode ? '🔥 FORZATA MANUALE ON' : '⚙️ AUTOMATICA (su richiesta calore)'}</strong></div>
                <div><strong>Protezione Min ON / Min OFF:</strong> ${z.pump ? z.pump.min_on_time : 120}s / ${z.pump ? z.pump.min_off_time : 120}s</div>
                <div><strong>Ritardo Avvio / Spegnimento:</strong> ${z.pump ? z.pump.startup_delay : 15}s / ${z.pump ? z.pump.shutdown_delay : 30}s</div>
              </div>

              <h4 style="margin: 12px 0 10px 0; font-size: 1.05rem;">Stanze Configurate (${Object.keys(z.rooms || {}).length}):</h4>
              <div style="display: flex; flex-direction: column; gap: 12px;">
                ${Object.values(z.rooms || {}).map(r => {
                  const comfortVal = (r.effective_presets && r.effective_presets.comfort !== undefined) ? r.effective_presets.comfort : 21.0;
                  const ecoVal = (r.effective_presets && r.effective_presets.eco !== undefined) ? r.effective_presets.eco : 18.0;
                  return `
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 14px;">
                      <div style="display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: 8px;">
                        <span style="font-size: 1.05rem;">🏠 ${r.name}</span>
                        <span style="font-size: 0.8rem; color: #888;">ID: ${r.room_id}</span>
                      </div>
                      <div style="font-size: 0.85rem; line-height: 1.7; color: #ccc;">
                        <div>• <strong>Preset Indipendenti:</strong> Comfort <strong>${comfortVal}°C</strong> | Eco <strong>${ecoVal}°C</strong></div>
                        <div>• <strong>Sensore Temperatura:</strong> <code>${(r.temp_sensor_ids && r.temp_sensor_ids.length > 0) ? r.temp_sensor_ids.join(', ') : 'Nessun sensore'}</code></div>
                        <div>• <strong>Valvole TRV:</strong> <code>${(r.trv_ids && r.trv_ids.length > 0) ? r.trv_ids.join(', ') : 'Nessuna valvola'}</code></div>
                        <div>• <strong>Sensore Finestra:</strong> <code>${r.window_sensor_id || 'Nessuno'}</code></div>
                        <div>• <strong>Isteresi:</strong> &plusmn;${r.hysteresis}&deg;C | <strong>Range:</strong> ${r.min_temp}&deg;C - ${r.max_temp}&deg;C</div>
                      </div>
                      <button class="preset-pill" style="margin-top: 10px; font-size: 0.8rem; background: rgba(255,255,255,0.08);"
                              data-action="edit-room-presets"
                              data-room="${r.room_id}"
                              data-comfort="${comfortVal}"
                              data-eco="${ecoVal}"
                              data-name="${r.name}">
                        ✏️ Modifica Preset ${r.name}
                      </button>
                    </div>
                  `;
                }).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  _bindEvents() {
    const root = this.shadowRoot;

    const tabDash = root.getElementById("tab-dash");
    const tabSched = root.getElementById("tab-sched");
    const tabConfig = root.getElementById("tab-config");
    const tabDiag = root.getElementById("tab-diag");
    if (tabDash) tabDash.onclick = () => { this._activeTab = "dashboard"; this._render(); };
    if (tabSched) tabSched.onclick = () => { this._activeTab = "scheduler"; this._render(); };
    if (tabConfig) tabConfig.onclick = () => { this._activeTab = "config"; this._render(); };
    if (tabDiag) tabDiag.onclick = () => { this._activeTab = "diagnostics"; this._render(); };

    // Modes
    const mHome = root.getElementById("mode-home");
    const mAway = root.getElementById("mode-away");
    const mFrost = root.getElementById("mode-frost");
    const mOff = root.getElementById("mode-off");
    if (mHome) mHome.onclick = () => this._setGlobalMode("home");
    if (mAway) mAway.onclick = () => this._setGlobalMode("away");
    if (mFrost) mFrost.onclick = () => this._setGlobalMode("frost");
    if (mOff) mOff.onclick = () => this._setGlobalMode("off");

    // Room control clicks & interactive buttons
    root.querySelectorAll("[data-action]").forEach(btn => {
      btn.onclick = async (e) => {
        const action = btn.dataset.action;
        const roomId = btn.dataset.room;
        if (action === "step-up") {
          const t = parseFloat(btn.dataset.target) + 0.5;
          await this._setRoomOverride(roomId, t);
        } else if (action === "step-down") {
          const t = parseFloat(btn.dataset.target) - 0.5;
          await this._setRoomOverride(roomId, t);
        } else if (action === "apply-preset") {
          const preset = btn.dataset.preset;
          await this._applyRoomPreset(roomId, preset);
        } else if (action === "set-preset") {
          const t = parseFloat(btn.dataset.val);
          await this._setRoomOverride(roomId, t);
        } else if (action === "clear-override") {
          await this._clearRoomOverride(roomId);
        } else if (action === "set-hvac") {
          await this._setRoomHvacMode(roomId, btn.dataset.mode);
        } else if (action === "prompt-target") {
          const curr = parseFloat(btn.dataset.target) || 20.0;
          const roomName = btn.dataset.name || "Stanza";
          const input = prompt(`Imposta temperatura desiderata per ${roomName} (°C):`, curr);
          if (input !== null) {
            const val = parseFloat(input);
            if (!isNaN(val)) {
              await this._setRoomOverride(roomId, val);
            }
          }
        } else if (action === "toggle-pump-manual") {
          const zoneId = btn.dataset.zone;
          const isManual = btn.dataset.manual === "true";
          await this._setZonePumpManual(zoneId, !isManual);
        } else if (action === "edit-buffer-settings") {
          const sys = this._systemData;
          const currMin = sys.buffer_min_temp !== undefined ? sys.buffer_min_temp : 45.0;
          const currHyst = sys.buffer_temp_hysteresis !== undefined ? sys.buffer_temp_hysteresis : 2.0;
          const newMin = prompt(`Temperatura minima di avvio accumulo (°C):`, currMin);
          if (newMin === null) return;
          const newHyst = prompt(`Isteresi di spegnimento pompe accumulo (°C):`, currHyst);
          if (newHyst === null) return;
          const mVal = parseFloat(newMin);
          const hVal = parseFloat(newHyst);
          if (!isNaN(mVal) && !isNaN(hVal)) {
            await this._setBufferSettings(sys.buffer_temp_sensor, mVal, hVal);
          }
        } else if (action === "edit-room-presets") {
          const roomName = btn.dataset.name || "Stanza";
          const currC = btn.dataset.comfort || "21";
          const currE = btn.dataset.eco || "18";
          const newC = prompt(`Temperatura Comfort per ${roomName} (°C):`, currC);
          if (newC === null) return;
          const newE = prompt(`Temperatura Eco per ${roomName} (°C):`, currE);
          if (newE === null) return;
          const cVal = parseFloat(newC);
          const eVal = parseFloat(newE);
          if (!isNaN(cVal) && !isNaN(eVal)) {
            await this._setRoomPresets(roomId, { comfort: cVal, eco: eVal });
          }
        }
      };
    });

    // Scheduler Day Chips
    root.querySelectorAll(".day-chip[data-day]").forEach(btn => {
      btn.onclick = () => {
        this._selectedDay = btn.dataset.day;
        this._render();
      };
    });

    // Scheduler Room Select
    const roomSelect = root.getElementById("select-room-scheduler");
    if (roomSelect) {
      roomSelect.onchange = (e) => {
        this._selectedRoomId = e.target.value;
        this._render();
      };
    }

    // Copy to week
    const btnCopyWeek = root.getElementById("btn-copy-to-week");
    if (btnCopyWeek) {
      btnCopyWeek.onclick = async () => {
        const room = this._systemData ? this.shadowRoot.getElementById("select-room-scheduler")?.value : null;
        if (room && this._systemData) {
          // Clone day to week in current schedule
          const rObj = Object.values(this._systemData.zones || {})
            .flatMap(z => Object.values(z.rooms || {}))
            .find(r => r.room_id === this._selectedRoomId);
          if (rObj && rObj.schedule) {
            const masterDay = rObj.schedule[this._selectedDay];
            const updated = {};
            for (const d of ['mon','tue','wed','thu','fri','sat','sun']) {
              updated[d] = masterDay;
            }
            await this._hass.callWS({
              type: "zoned_thermostat/update_schedule",
              room_id: this._selectedRoomId,
              schedule: updated,
            });
            await this._loadData();
          }
        }
      };
    }
  }
}

customElements.define("zoned-thermostat-panel", ZonedThermostatPanel);
