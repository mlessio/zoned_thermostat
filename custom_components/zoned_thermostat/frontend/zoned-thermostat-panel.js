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
        </div>
      </div>

      <!-- TABS -->
      <div class="nav-tabs">
        <button class="tab-btn ${this._activeTab === 'dashboard' ? 'active' : ''}" id="tab-dash">Panoramica & Zone</button>
        <button class="tab-btn ${this._activeTab === 'scheduler' ? 'active' : ''}" id="tab-sched">Pianificazione Settimanale</button>
        <button class="tab-btn ${this._activeTab === 'diagnostics' ? 'active' : ''}" id="tab-diag">Diagnostica & Timeline</button>
      </div>

      <!-- CONTENT SWITCH -->
      <div id="tab-content">
        ${this._activeTab === 'dashboard' ? this._renderDashboard(sys) : ''}
        ${this._activeTab === 'scheduler' ? this._renderScheduler(sys) : ''}
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
    const rooms = Object.values(zone.rooms || {});

    return `
      <div class="zone-card">
        <div class="zone-header">
          <h2 class="zone-title">${zone.name}</h2>
          <div class="pump-indicator ${isPumpOn ? 'pump-on' : 'pump-off'}">
            <span>⚙️ Pompa: ${pumpState.toUpperCase()}</span>
          </div>
        </div>

        <div class="pump-reason">
          <strong>Stato Pompa:</strong> ${pumpReason}
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
          <span class="target-temp-display">/ target ${targetTemp}</span>
        </div>

        <div class="controls-row">
          <div class="temp-stepper">
            <button class="step-btn" data-action="step-down" data-room="${room.room_id}" data-target="${room.target_temp}">-</button>
            <span style="padding: 0 10px; font-weight: 700; font-size: 0.95rem;">${targetTemp}</span>
            <button class="step-btn" data-action="step-up" data-room="${room.room_id}" data-target="${room.target_temp}">+</button>
          </div>

          <button class="preset-pill" data-action="set-preset" data-room="${room.room_id}" data-val="21.0">Comfort (21°)</button>
          <button class="preset-pill" data-action="set-preset" data-room="${room.room_id}" data-val="18.0">Eco (18°)</button>

          ${room.manual_override ? `
            <button class="preset-pill" style="color: #ff5252;" data-action="clear-override" data-room="${room.room_id}">Annulla Override</button>
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

  _bindEvents() {
    const root = this.shadowRoot;

    // Tabs
    const tabDash = root.getElementById("tab-dash");
    const tabSched = root.getElementById("tab-sched");
    const tabDiag = root.getElementById("tab-diag");
    if (tabDash) tabDash.onclick = () => { this._activeTab = "dashboard"; this._render(); };
    if (tabSched) tabSched.onclick = () => { this._activeTab = "scheduler"; this._render(); };
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

    // Room control clicks
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
        } else if (action === "set-preset") {
          const t = parseFloat(btn.dataset.val);
          await this._setRoomOverride(roomId, t);
        } else if (action === "clear-override") {
          await this._clearRoomOverride(roomId);
        } else if (action === "set-hvac") {
          await this._setRoomHvacMode(roomId, btn.dataset.mode);
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
