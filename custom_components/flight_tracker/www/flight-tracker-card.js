/**
 * Flight Tracker Card
 *
 * A custom Lovelace card for the Flight Tracker integration:
 *  - live search controls (radius / altitude sliders, lat-lon fields, filter
 *    selects) that call flight_tracker.set_search_params as they change
 *  - a multi-select list of currently tracked nearby flights, used to choose
 *    which ones are plotted on an embedded map
 *  - a details list/grid for every tracked flight
 *
 * No build step: this loads directly as an ES module. It reuses Home
 * Assistant's own bundled LitElement (via the well-known prototype-chain
 * trick) instead of shipping a second copy, and embeds the built-in "map"
 * card via the officially documented window.loadCardHelpers() API rather
 * than re-implementing map rendering.
 */
(function () {
  "use strict";

  function getLitElementBase() {
    var anchor =
      customElements.get("hui-view") ||
      customElements.get("hui-masonry-view") ||
      customElements.get("home-assistant-main");
    if (!anchor) {
      throw new Error("flight-tracker-card: Home Assistant base elements are not available yet");
    }
    return Object.getPrototypeOf(anchor);
  }

  var LitElementBase = getLitElementBase();
  var html = LitElementBase.prototype.html;
  var css = LitElementBase.prototype.css;

  var DOMAIN = "flight_tracker";
  var SERVICE_SET_SEARCH_PARAMS = "set_search_params";
  var SERVICE_REFRESH = "refresh";

  function fmt(value, digits) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) {
      return "-";
    }
    return Number(value).toFixed(digits === undefined ? 0 : digits);
  }

  function flightLabel(stateObj) {
    var callsign = stateObj.attributes.callsign;
    if (callsign && String(callsign).trim()) {
      return String(callsign).trim();
    }
    var parts = stateObj.entity_id.split(".");
    return parts[1] ? parts[1].toUpperCase() : stateObj.entity_id;
  }

  class FlightTrackerCardElement extends LitElementBase {
    static get properties() {
      return {
        hass: {},
        config: {},
        _deselected: { state: true },
        _expanded: { state: true },
        _draft: { state: true },
      };
    }

    constructor() {
      super();
      this._deselected = new Set();
      this._expanded = new Set();
      this._draft = {};
      this._mapCardEl = null;
      this._mapCardPromise = null;
    }

    setConfig(config) {
      if (!config || !config.entity) {
        throw new Error("flight-tracker-card: 'entity' is required (e.g. sensor.flight_tracker_total_flights)");
      }
      this.config = Object.assign(
        {
          title: "Flight Tracker",
          show_map: true,
          map_default_zoom: 9,
          map_height: 300,
        },
        config
      );
    }

    getCardSize() {
      return 10;
    }

    static getStubConfig(hass) {
      var match = Object.keys(hass.states).find(function (id) {
        return id.indexOf("sensor.") === 0 && id.indexOf("total_flights") !== -1;
      });
      return { entity: match || "sensor.flight_tracker_total_flights" };
    }

    get _stateObj() {
      return this.hass && this.config ? this.hass.states[this.config.entity] : undefined;
    }

    get _params() {
      var stateObj = this._stateObj;
      var attrs = stateObj ? stateObj.attributes : {};
      var fallbackLat = this.hass && this.hass.config ? this.hass.config.latitude : 0;
      var fallbackLon = this.hass && this.hass.config ? this.hass.config.longitude : 0;
      var committed = {
        latitude: attrs.latitude !== undefined ? attrs.latitude : fallbackLat,
        longitude: attrs.longitude !== undefined ? attrs.longitude : fallbackLon,
        radius_km: attrs.radius_km !== undefined ? attrs.radius_km : 50,
        min_altitude: attrs.min_altitude !== undefined ? attrs.min_altitude : 0,
        max_altitude: attrs.max_altitude !== undefined ? attrs.max_altitude : 60000,
        track_military: attrs.track_military === true,
        track_ga: attrs.track_ga !== false,
      };
      return Object.assign({}, committed, this._draft);
    }

    get _flights() {
      if (!this.hass) {
        return [];
      }
      var states = this.hass.states;
      var list = [];
      for (var entityId in states) {
        if (entityId.indexOf("device_tracker.") !== 0) {
          continue;
        }
        var stateObj = states[entityId];
        if (!("icao24" in stateObj.attributes)) {
          continue;
        }
        list.push(stateObj);
      }
      list.sort(function (a, b) {
        var da = a.attributes.distance_km;
        var db = b.attributes.distance_km;
        if (da === undefined && db === undefined) return 0;
        if (da === undefined) return 1;
        if (db === undefined) return -1;
        return da - db;
      });
      return list;
    }

    get _visibleFlightIds() {
      var deselected = this._deselected;
      return this._flights
        .filter(function (f) {
          return !deselected.has(f.entity_id);
        })
        .map(function (f) {
          return f.entity_id;
        });
    }

    _isSelected(entityId) {
      return !this._deselected.has(entityId);
    }

    _toggleFlight(entityId) {
      var next = new Set(this._deselected);
      if (next.has(entityId)) {
        next.delete(entityId);
      } else {
        next.add(entityId);
      }
      this._deselected = next;
    }

    _toggleExpanded(entityId) {
      var next = new Set(this._expanded);
      if (next.has(entityId)) {
        next.delete(entityId);
      } else {
        next.add(entityId);
      }
      this._expanded = next;
    }

    _selectAll() {
      this._deselected = new Set();
    }

    _selectNone() {
      this._deselected = new Set(
        this._flights.map(function (f) {
          return f.entity_id;
        })
      );
    }

    _callService(service, data) {
      if (!this.hass) {
        return;
      }
      var payload = Object.assign({}, data);
      if (this.config.entry_id) {
        payload.entry_id = this.config.entry_id;
      }
      this.hass.callService(DOMAIN, service, payload);
    }

    _setParams(partial) {
      this._draft = Object.assign({}, this._draft, partial);
      this._callService(SERVICE_SET_SEARCH_PARAMS, partial);
    }

    _onRadiusInput(e) {
      this._draft = Object.assign({}, this._draft, { radius_km: Number(e.target.value) });
    }

    _onRadiusChange(e) {
      this._setParams({ radius_km: Number(e.target.value) });
    }

    _onMinAltInput(e) {
      this._draft = Object.assign({}, this._draft, { min_altitude: Number(e.target.value) });
    }

    _onMinAltChange(e) {
      this._setParams({ min_altitude: Number(e.target.value) });
    }

    _onMaxAltInput(e) {
      this._draft = Object.assign({}, this._draft, { max_altitude: Number(e.target.value) });
    }

    _onMaxAltChange(e) {
      this._setParams({ max_altitude: Number(e.target.value) });
    }

    _onLatChange(e) {
      var value = Number(e.target.value);
      if (!Number.isNaN(value)) {
        this._setParams({ latitude: value });
      }
    }

    _onLonChange(e) {
      var value = Number(e.target.value);
      if (!Number.isNaN(value)) {
        this._setParams({ longitude: value });
      }
    }

    _useHomeLocation() {
      if (!this.hass || !this.hass.config) {
        return;
      }
      this._setParams({
        latitude: this.hass.config.latitude,
        longitude: this.hass.config.longitude,
      });
    }

    _onTrackMilitaryChange(e) {
      this._setParams({ track_military: e.target.value === "yes" });
    }

    _onTrackGaChange(e) {
      this._setParams({ track_ga: e.target.value === "yes" });
    }

    _refresh() {
      this._callService(SERVICE_REFRESH, {});
    }

    _ensureMapCard() {
      var _this = this;
      if (this._mapCardEl || this._mapCardPromise || !this.config.show_map) {
        return;
      }
      if (!window.loadCardHelpers) {
        return;
      }
      this._mapCardPromise = window
        .loadCardHelpers()
        .then(function (helpers) {
          return helpers.createCardElement({
            type: "map",
            entities: _this._visibleFlightIds,
            default_zoom: _this.config.map_default_zoom,
          });
        })
        .then(function (el) {
          el.hass = _this.hass;
          _this._mapCardEl = el;
          _this.requestUpdate();
        });
    }

    updated() {
      if (this._mapCardEl) {
        this._mapCardEl.hass = this.hass;
        this._mapCardEl.setConfig({
          type: "map",
          entities: this._visibleFlightIds,
          default_zoom: this.config.map_default_zoom,
        });
        var container = this.renderRoot.getElementById("flight-tracker-map");
        if (container && this._mapCardEl.parentElement !== container) {
          container.innerHTML = "";
          container.appendChild(this._mapCardEl);
        }
      } else {
        this._ensureMapCard();
      }
    }

    _renderFlightRow(stateObj) {
      var a = stateObj.attributes;
      var expanded = this._expanded.has(stateObj.entity_id);
      var selected = this._isSelected(stateObj.entity_id);
      var _this = this;
      return html`
        <div class="flight-row ${selected ? "" : "flight-row-dim"}">
          <div class="flight-summary">
            <input
              type="checkbox"
              .checked=${selected}
              @change=${function () {
                _this._toggleFlight(stateObj.entity_id);
              }}
              title="Show on map"
            />
            <div
              class="flight-summary-text"
              @click=${function () {
                _this._toggleExpanded(stateObj.entity_id);
              }}
            >
              <span class="flight-callsign">${flightLabel(stateObj)}</span>
              <span class="flight-meta">
                ${a.aircraft_type ? a.aircraft_type + " · " : ""}${fmt(a.altitude, 0)} ft ·
                ${fmt(a.speed, 0)} kt · ${a.distance_km !== undefined ? fmt(a.distance_km, 1) + " km" : "? km"}
              </span>
            </div>
            <ha-icon
              class="flight-expand-icon"
              .icon=${expanded ? "mdi:chevron-up" : "mdi:chevron-down"}
              @click=${function () {
                _this._toggleExpanded(stateObj.entity_id);
              }}
            ></ha-icon>
          </div>
          ${expanded
            ? html`
                <div class="flight-details">
                  ${a.image_url ? html`<img class="flight-image" src="${a.image_url}" alt="${flightLabel(stateObj)}" />` : ""}
                  <div class="flight-details-grid">
                    <div><span class="label">Registration</span>${a.registration || "-"}</div>
                    <div><span class="label">ICAO24</span>${a.icao24 || "-"}</div>
                    <div><span class="label">Altitude</span>${fmt(a.altitude, 0)} ft</div>
                    <div><span class="label">Geo. altitude</span>${fmt(a.altitude_geometric, 0)} ft</div>
                    <div><span class="label">Speed</span>${fmt(a.speed, 0)} kt</div>
                    <div><span class="label">Heading</span>${fmt(a.heading, 0)}°</div>
                    <div><span class="label">Vertical rate</span>${fmt(a.vertical_rate, 0)} fpm</div>
                    <div><span class="label">Squawk</span>${a.squawk || "-"}</div>
                    <div><span class="label">Category</span>${a.category_label || "-"}</div>
                    <div><span class="label">Operator</span>${a.operator || "-"}</div>
                    <div><span class="label">Origin</span>${a.origin || "-"}</div>
                    <div><span class="label">Destination</span>${a.destination || "-"}</div>
                    <div><span class="label">Distance</span>${fmt(a.distance_km, 1)} km</div>
                    <div><span class="label">Source</span>${a.source_api || "-"}</div>
                    <div><span class="label">Signal (RSSI)</span>${fmt(a.rssi, 1)}</div>
                  </div>
                </div>
              `
            : ""}
        </div>
      `;
    }

    render() {
      if (!this.hass || !this.config) {
        return html``;
      }
      var stateObj = this._stateObj;
      if (!stateObj) {
        return html`
          <ha-card>
            <div class="card-content">Entity ${this.config.entity} not found.</div>
          </ha-card>
        `;
      }

      var params = this._params;
      var flights = this._flights;
      var _this = this;

      return html`
        <ha-card>
          <div class="card-header">
            <div class="name">${this.config.title}</div>
            <div class="header-actions">
              <span class="flight-count">${flights.length} nearby</span>
              <button
                class="icon-button"
                title="Refresh now"
                @click=${function () {
                  _this._refresh();
                }}
              >
                <ha-icon icon="mdi:refresh"></ha-icon>
              </button>
            </div>
          </div>

          <div class="card-content">
            <div class="params-grid">
              <div class="param param-slider">
                <label>Radius: ${fmt(params.radius_km, 0)} km</label>
                <input
                  type="range"
                  min="1"
                  max="500"
                  step="1"
                  .value=${params.radius_km}
                  @input=${function (e) {
                    _this._onRadiusInput(e);
                  }}
                  @change=${function (e) {
                    _this._onRadiusChange(e);
                  }}
                />
              </div>

              <div class="param param-slider">
                <label>Min altitude: ${fmt(params.min_altitude, 0)} ft</label>
                <input
                  type="range"
                  min="0"
                  max="60000"
                  step="100"
                  .value=${params.min_altitude}
                  @input=${function (e) {
                    _this._onMinAltInput(e);
                  }}
                  @change=${function (e) {
                    _this._onMinAltChange(e);
                  }}
                />
              </div>

              <div class="param param-slider">
                <label>Max altitude: ${fmt(params.max_altitude, 0)} ft</label>
                <input
                  type="range"
                  min="0"
                  max="60000"
                  step="100"
                  .value=${params.max_altitude}
                  @input=${function (e) {
                    _this._onMaxAltInput(e);
                  }}
                  @change=${function (e) {
                    _this._onMaxAltChange(e);
                  }}
                />
              </div>

              <div class="param">
                <label>Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  .value=${params.latitude}
                  @change=${function (e) {
                    _this._onLatChange(e);
                  }}
                />
              </div>

              <div class="param">
                <label>Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  .value=${params.longitude}
                  @change=${function (e) {
                    _this._onLonChange(e);
                  }}
                />
                <button
                  class="link-button"
                  @click=${function () {
                    _this._useHomeLocation();
                  }}
                >
                  Use Home Assistant location
                </button>
              </div>

              <div class="param">
                <label>Track military / heavy</label>
                <select
                  .value=${params.track_military ? "yes" : "no"}
                  @change=${function (e) {
                    _this._onTrackMilitaryChange(e);
                  }}
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </div>

              <div class="param">
                <label>Track general aviation</label>
                <select
                  .value=${params.track_ga ? "yes" : "no"}
                  @change=${function (e) {
                    _this._onTrackGaChange(e);
                  }}
                >
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </div>
            </div>

            ${this.config.show_map
              ? html`<div id="flight-tracker-map" style="height: ${this.config.map_height}px;"></div>`
              : ""}

            <div class="flight-list-header">
              <span>Nearby flights (${flights.length})</span>
              <span class="flight-list-actions">
                <button
                  class="link-button"
                  @click=${function () {
                    _this._selectAll();
                  }}
                >
                  All
                </button>
                <button
                  class="link-button"
                  @click=${function () {
                    _this._selectNone();
                  }}
                >
                  None
                </button>
              </span>
            </div>

            <div class="flight-list">
              ${flights.length === 0
                ? html`<div class="empty">No flights currently tracked.</div>`
                : flights.map(function (f) {
                    return _this._renderFlightRow(f);
                  })}
            </div>
          </div>
        </ha-card>
      `;
    }

    static get styles() {
      return css`
        ha-card {
          padding: 0;
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 16px 0 16px;
        }
        .card-header .name {
          font-size: 1.2em;
          font-weight: 500;
          color: var(--ha-card-header-color, var(--primary-text-color));
        }
        .header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--secondary-text-color);
          font-size: 0.9em;
        }
        .icon-button {
          background: none;
          border: none;
          cursor: pointer;
          color: var(--secondary-text-color);
          display: flex;
          align-items: center;
          padding: 4px;
        }
        .card-content {
          padding: 16px;
        }
        .params-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 12px 16px;
          margin-bottom: 16px;
        }
        .param {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .param label {
          font-size: 0.85em;
          color: var(--secondary-text-color);
        }
        .param input[type="number"],
        .param select {
          background: var(--card-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          padding: 6px 8px;
          font-size: 0.95em;
        }
        .param input[type="range"] {
          width: 100%;
          accent-color: var(--primary-color);
        }
        .link-button {
          background: none;
          border: none;
          color: var(--primary-color);
          cursor: pointer;
          padding: 0;
          font-size: 0.85em;
          text-align: left;
        }
        #flight-tracker-map {
          border-radius: var(--ha-card-border-radius, 12px);
          overflow: hidden;
          margin-bottom: 16px;
        }
        .flight-list-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          color: var(--secondary-text-color);
          font-size: 0.9em;
        }
        .flight-list-actions {
          display: flex;
          gap: 8px;
        }
        .flight-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          max-height: 420px;
          overflow-y: auto;
        }
        .flight-row {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 8px 10px;
        }
        .flight-row-dim {
          opacity: 0.55;
        }
        .flight-summary {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .flight-summary-text {
          flex: 1;
          display: flex;
          flex-direction: column;
          cursor: pointer;
        }
        .flight-callsign {
          font-weight: 600;
        }
        .flight-meta {
          font-size: 0.85em;
          color: var(--secondary-text-color);
        }
        .flight-expand-icon {
          cursor: pointer;
          color: var(--secondary-text-color);
        }
        .flight-details {
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid var(--divider-color);
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
        }
        .flight-image {
          max-width: 160px;
          max-height: 110px;
          border-radius: 6px;
          object-fit: cover;
        }
        .flight-details-grid {
          flex: 1;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 6px 12px;
          font-size: 0.85em;
        }
        .flight-details-grid .label {
          display: block;
          color: var(--secondary-text-color);
          font-size: 0.85em;
        }
        .empty {
          color: var(--secondary-text-color);
          padding: 16px 0;
          text-align: center;
        }
      `;
    }
  }

  if (!customElements.get("flight-tracker-card")) {
    customElements.define("flight-tracker-card", FlightTrackerCardElement);
  }

  window.customCards = window.customCards || [];
  if (
    !window.customCards.some(function (c) {
      return c.type === "flight-tracker-card";
    })
  ) {
    window.customCards.push({
      type: "flight-tracker-card",
      name: "Flight Tracker Card",
      description: "Map, live search filters, multi-select, and details for nearby flights.",
    });
  }
})();
