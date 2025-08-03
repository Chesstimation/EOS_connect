# EOS Connect

**EOS Connect** is an open-source tool for intelligent energy management and optimization.  
It connects to various smart home platforms (like Home Assistant and OpenHAB) to monitor, forecast, and control your energy flows.  
EOS Connect fetches real-time and forecast data (PV, load, prices), processes it via the [EOS (Energy Optimization System)](https://github.com/Akkudoktor-EOS/EOS), and automatically controls devices (such as Fronius inverters or batteries supported by [evcc](https://docs.evcc.io/docs/devices/meters)) to optimize your energy usage and costs.

**Key Features:**
- **Automated Energy Optimization:**  
  Uses real-time and forecast data to maximize self-consumption and minimize grid costs.
- **Battery and Inverter Management:**  
  Supports charge/discharge control, grid/PV modes, and dynamic charging curves.
- **Integration with Smart Home Platforms:**  
  Works with Home Assistant, OpenHAB, EVCC, and MQTT for seamless data exchange and automation.
- **Dynamic Web Dashboard:**  
  Provides live monitoring, manual control, and visualization of your energy system.
- **Cost Optimization:**  
  Aligns energy usage with dynamic electricity prices (e.g., Tibber, smartenergy.at).
- **Flexible Configuration:**  
  Easy to set up and extend for a wide range of energy systems and user needs.

EOS Connect helps you get the most out of your solar and storage systems—whether you want to save money, increase self-sufficiency, or simply monitor your energy flows in real time.


- [EOS Connect](#eos-connect)
  - [Key Features](#key-features)
    - [**Energy Optimization**](#energy-optimization)
    - [**Interactive Web Interface**](#interactive-web-interface)
    - [**Integration with External Systems**](#integration-with-external-systems)
  - [Current Status](#current-status)
  - [Quick Start](#quick-start)
    - [1. Requirements](#1-requirements)
    - [2. Install via Home Assistant Add-on](#2-install-via-home-assistant-add-on)
    - [3. Configure](#3-configure)
    - [4. Explore](#4-explore)
  - [How it Works](#how-it-works)
    - [Base](#base)
    - [Collecting Data](#collecting-data)
      - [Home Assistant](#home-assistant)
      - [OpenHAB](#openhab)
      - [PV Forecast](#pv-forecast)
      - [Energy Price Forecast](#energy-price-forecast)
  - [Webpage Example](#webpage-example)
  - [Provided Data per **EOS connect** API](#provided-data-per-eos-connect-api)
    - [Web API (REST/JSON)](#web-api-restjson)
    - [Main Endpoints](#main-endpoints)
    - [MQTT - provided data and possible commands](#mqtt---provided-data-and-possible-commands)
    - [Published Topics](#published-topics)
    - [Example Usage](#example-usage)
    - [Subscribed Topics](#subscribed-topics)
    - [System Mode Control (`control/overall_state/set`)](#system-mode-control-controloverall_stateset)
    - [How to Use](#how-to-use)
      - [Examples](#examples)
  - [Configuration](#configuration)
  - [Useful Information](#useful-information)
    - [Getting historical values](#getting-historical-values)
      - [Home Assistant Persistance](#home-assistant-persistance)
      - [Openhab](#openhab-1)
  - [Usage](#usage)
  - [Requirements](#requirements)
  - [Installation and Running](#installation-and-running)
  - [Contributing](#contributing)
  - [Glossary](#glossary)
  - [License](#license)


## Key Features

### **Energy Optimization**
- **Dynamic Energy Flow Control**:
  - Automatically optimizes energy usage based on system states and external data.
  - Supports manual override modes for precise control.
- **Battery Management**:
  - Monitors battery state of charge (SOC) and remaining energy.
  - Configures charging and discharging modes, including:
    - Charge from grid.
    - Avoid discharge.
    - Discharge allowed.
    - EVCC-specific modes (e.g., fast charge, PV mode).
  - **Dynamic Charging Curve**:
    - If enabled, EOS Connect automatically adjusts the maximum battery charging power based on the current state of charge (SOC). This helps to optimize battery health and efficiency by reducing charge power as the battery approaches full capacity.
- **Cost and Solar Optimization**:
  - Aligns energy usage with real-time electricity prices (e.g., from Tibber or [smartenergy.at](https://www.smartenergy.at/)) to minimize costs.
  - Incorporates PV forecasts to prioritize charging during periods of high solar output.
  - Reduces grid dependency and maximizes self-consumption by combining cost and solar production data.
- **Energy Optimization Scheduling**:
  - Displays timestamps for the last and next optimization runs.
  - Tracks system performance and optimization results.

### **Interactive Web Interface**
- **Real-Time Monitoring**:
  - View current system states, including battery SOC, grid charge power, and EVCC modes.
  - Dynamic icons and color-coded indicators for easy visualization.
- **User Controls**:
  - Set grid charge power and override system modes directly from the interface.
  - Configure EVCC charging behavior with intuitive controls.

### **Integration with External Systems**
- **Home Assistant**:
  - Full MQTT integration with Home Assistant Auto Discovery.
  - Automatically detects and configures energy system entities.
- **OpenHAB**:
  - Integrates with OpenHAB for monitoring and controlling energy systems.
  - Publishes system states and subscribes to commands via MQTT.
- **EVCC (Electric Vehicle Charging Controller)**:
  - Monitors and controls EVCC charging modes and states.
  - Supports fast charge, PV charging, and combined modes.
- **Inverter Interfaces**:
  - OPTION 1: Communicates directly with a Fronius GEN24 to monitor and control energy flows.
  - OPTION 2: Use the [evcc external battery control](https://docs.evcc.io/docs/integrations/rest-api) to interact with all inverter/ battery systems that [are supported by evcc](https://docs.evcc.io/en/docs/devices/meters) (hint: the dynamic max charge power is currently not supported by evcc external battery control)
  - OPTION 3: using without a direct control interface to get the resulting commands by **EOS connect** MQTT or web API to control within your own environment (e.g. [Integrate inverter e.g. sungrow SH10RT #35](https://github.com/ohAnd/EOS_connect/discussions/35)  )
  - Retrieves real-time data such as grid charge power, discharge power, and battery SOC.
- **MQTT Broker**:
  - Acts as the central hub for real-time data exchange.
  - Publishes system states and subscribes to control commands.

## Current Status

This project is in its early stages and is actively being developed and enhanced.

2025-04-10

- EOS made a breaking change - see here https://github.com/Akkudoktor-EOS/EOS/discussions/513
- there were also changes in the API at '<your_ip>:8503' - unfortunately the API is not versioned (*ping* ;-) )
- to fullfil both versions there is small hack to identify the connected EOS
- finally the current version can run with both EOS versions

---

## Quick Start

Get up and running with EOS Connect in just a few steps!

### 1. Requirements

- **Home Assistant** (recommended for most users)  
  *(Or see [Installation and Running](#installation-and-running) for Docker and local options)*
- **An already running instance of [EOS (Energy Optimization System)](https://github.com/Akkudoktor-EOS/EOS)**  
  EOS Connect acts as a client and requires a reachable EOS server for optimization and control.

### 2. Install via Home Assistant Add-on

- Add the [ohAnd/ha_addons](https://github.com/ohAnd/ha_addons) repository to your Home Assistant add-on store.
- Install both the **EOS Add-on** and the **EOS Connect Add-on**.
- Configure both add-ons via the Home Assistant UI.
- Start both add-ons.  
  The EOS Connect web dashboard will be available at [http://homeassistant.local:8081](http://homeassistant.local:8081) (or your HA IP).

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fohand%2Fha_addons)

### 3. Configure

- On first start, a default `config.yaml` will be created in the add-on’s config folder.
- Edit this file via the Home Assistant add-on UI to set your EOS server address and other options.
- See the [CONFIG_README](src/CONFIG_README.md) for full configuration details.

### 4. Explore

- Open the web dashboard at [http://homeassistant.local:8081](http://homeassistant.local:8081) (or your HA IP).
- Check live data, forecasts, and system status.
- Integrate with your automation tools using the [Web API](#web-api-restjson) or [MQTT](#mqtt---provided-data-and-possible-commands).

---

> If you’re new to Home Assistant add-ons, see [the official documentation](https://www.home-assistant.io/addons/) for help.

> **Not using Home Assistant?**  
> See [Installation and Running](#installation-and-running) for Docker and local installation instructions.

## How it Works

### Base

**EOS Connect** is a self-running system that periodically collects:
- Local energy consumption data.
- PV solar forecasts for the next 48 hours.
- Upcoming energy prices.

Using this data, a request is sent to EOS, which creates a model predicting the energy needs based on different energy sources and loads (grid, battery, PV).

**EOS Connect** waits for the response from EOS (e.g., ~2 min 15 sec for a full 48-hour prediction on a Raspberry Pi 5). After receiving the response, it is analyzed to extract the necessary values.

Finally, the system sets up the inverter based on the following states:
- `MODE_CHARGE_FROM_GRID` with a specific target charging power (based on your configuration).
- `MODE_AVOID_DISCHARGE`.
- `MODE_DISCHARGE_ALLOWED` with a specific target maximum discharging power (based on your configuration).

The system repeats this process periodically, e.g., every 3 minutes, as defined in the configuration.

<div align="center">

<img src="doc/eos_connect_flow.png" alt="EOS connect flow" width="450"/>

<br>
<sub><i>Figure: EOS Connect process flow</i></sub>
<br>
<sub><i>Note: Due to my limited drawing skills ;-) , the principle diagram above was generated with the help of an AI image engine.</i></sub>
</div>

---

### Collecting Data

Data collection for load forecasting is based on your existing load data provided by an OpenHAB or Home Assistant instance (using the persistence of each system). EOS requires a load forecast for today and tomorrow.

#### Home Assistant
Load data is retrieved from:
- Today one week ago, averaged with today two weeks ago.
- Tomorrow one week ago, averaged with tomorrow two weeks ago.
- **Car Load Adjustment**: If an electric vehicle (EV) is/ was connected, its load is subtracted from the household load to ensure accurate forecasting of non-EV energy consumption.

**Load Sensor Requirements:**
- **Data Quality**: The sensor must provide numeric values and in unit 'watts'.
- **Value Handling**: EOS Connect accepts both positive and negative values from your sensor. For the internal processing: all values are converted to absolute positive values for load calculations.
- **Sensor Types**: Use sensors representing the overall net household consumption. Expected that all additonal loads as ev charge or an optional load are included here.

(See [Home Assistant Persistance](#home-assistant-persistance) for more details.)

#### OpenHAB
Load data is retrieved from the last two days:
- From two days ago (00:00) to yesterday midnight.
- **Car Load Adjustment**: Similar to Home Assistant, the EV load is subtracted from the household load to isolate non-EV energy consumption.

#### PV Forecast
EOS Connect supports multiple sources for solar (PV) production forecasts. You can choose the provider that best fits your location and needs. The following PV forecast sources are available and configurable:

- **Akkudoktor** (default)  
  Direct integration with the [Akkudoktor API](https://api.akkudoktor.net/forecast) for reliable PV forecasts.

- **Open-Meteo**  
  Uses the [Open-Meteo API](https://open-meteo.com/en/docs) and [open-meteo-solar-forecast Python library](https://github.com/rany2/open-meteo-solar-forecast) for library-based calculation

- **Open-Meteo Local**  
  Gathers radiation and cloud cover data from Open-Meteo and calculates PV output locally using an own model (experimental).

- **Forecast.Solar**  
  Connects to the [Forecast.Solar API](https://doc.forecast.solar/api) for detailed PV production forecasts.

#### Energy Price Forecast
Energy price forecasts are retrieved from the chosen source (TIBBER or AKKUDOKTOR API). **Note**: Prices for tomorrow are available earliest at 1 PM. Until then, today's prices are used to feed the model.

---

## Webpage Example

The dashbaord of **EOS connect** is available at `http://localhost:8081`.

![webpage screenshot](doc/screenshot_0_1_20.png)

## Provided Data per **EOS connect** API

EOS Connect can be integrated with your smart home or automation tools using MQTT or its built-in web API. See below for details.

### Web API (REST/JSON)

EOS Connect provides a RESTful web API for real-time data access and remote control.  
All endpoints return JSON and can be accessed via HTTP requests.

<details>
<summary>Details</summary>

**Base URL:**  
`http://<host>:<port>/`  
*(Default port is set in your config, e.g., `8081`)*

---

### Main Endpoints

| Endpoint                          | Method | Returns / Accepts           | Description                                                      |
|------------------------------------|--------|-----------------------------|------------------------------------------------------------------|
| `/json/current_controls.json`      | GET    | JSON                        | Current system control states (AC/DC charge, mode, etc.)         |
| `/json/optimize_request.json`      | GET    | JSON                        | Last optimization request sent to EOS                            |
| `/json/optimize_response.json`     | GET    | JSON                        | Last optimization response from EOS                              |
| `/controls/mode_override`          | POST   | JSON (see below)            | Override system mode, duration, and grid charge power            |

---

<details>
<summary>Show Example: <code>/json/current_controls.json</code> (GET)</summary>

```json
{
  "current_states": {
    "current_ac_charge_demand": 2000,
    "current_dc_charge_demand": 0,
    "current_discharge_allowed": true,
    "inverter_mode": "Discharge Allowed",
    "inverter_mode_num": 2,
    "override_active": false,
    "override_end_time": null
  },
  "battery": {
    "soc": 85.5,
    "usable_capacity": 9000,
    "max_charge_power_dyn": 5000
  },
  "evcc": {
    "charging_mode": "pv",
    "charging_state": true,
    "current_sessions": [ ... ]
  },
  "state": {
    "last_response_timestamp": "2024-06-01T12:00:00+02:00",
    "next_run": "2024-06-01T12:03:00+02:00"
  },
  "timestamp": "2024-06-01T12:00:00+02:00",
  "api_version": "0.0.1"
}
```
</details>

---

<details>
<summary>Show Example: <code>/controls/mode_override</code> (POST)</summary>

Override the system mode, duration, and grid charge power.

**Payload:**
```json
{
  "mode": 1,                // Integer, see mode table below
  "duration": "02:00",      // String, format "HH:MM"
  "grid_charge_power": 2.0  // Float, kW (e.g., 2.0 for 2000 W)
}
```

**Response:**
- On success:
  ```json
  { "status": "success", "message": "Mode override applied" }
  ```
- On error:
  ```json
  { "error": "Invalid mode value" }
  ```

**System Modes (`mode` field):**

| Mode Name         | Mode Number | Description                                 |
|-------------------|-------------|---------------------------------------------|
| `Auto`            | 0           | Fully automatic optimization (default mode) |
| `ChargeFromGrid`  | 1           | Force battery charging from the grid        |
| `Discharge`       | 2           | Force battery discharge                     |
| `Idle`            | 3           | No charging or discharging                  |
| `PVOnly`          | 4           | Charge battery only from PV (solar)         |

</details>

---

**How to Use:**
- **Get current system state:**  
  `GET http://localhost:8081/json/current_controls.json`
- **Override mode and charge power:**  
  `POST http://localhost:8081/controls/mode_override`  
  with JSON body as shown above.

You can use `curl`, Postman, or any HTTP client to interact with these endpoints.

**Notes:**
- The web API is always available on the configured port.
- All responses are in JSON format.
- The override will be active for the specified duration, after which the system returns to automatic mode.
- Invalid values will result in an error response.

</details>

---

### MQTT - provided data and possible commands

EOS Connect publishes a wide range of real-time system data and control states to MQTT topics. You can use these topics to monitor system status, battery and inverter data, optimization results, and more from any MQTT-compatible tool (e.g., Home Assistant, Node-RED, Grafana, etc.).

<details>
<summary>MQTT Data Published</summary>

**Base topic:**  
`<mqtt_configured_prefix>/eos_connect/`  
*(Set `<mqtt_configured_prefix>` in your `config.yaml`, e.g., `myhome`)*

---

### Published Topics

| Topic Suffix                                      | Full Topic Example                                             | Payload Type / Example         | Description                                              |
|---------------------------------------------------|---------------------------------------------------------------|-------------------------------|----------------------------------------------------------|
| `optimization/state`                              | `myhome/eos_connect/optimization/state`                       | String (`"ok"`, `"error"`)    | Current optimization request state                       |
| `optimization/last_run`                           | `myhome/eos_connect/optimization/last_run`                    | ISO timestamp                 | Timestamp of the last optimization run                   |
| `optimization/next_run`                           | `myhome/eos_connect/optimization/next_run`                    | ISO timestamp                 | Timestamp of the next scheduled optimization run         |
| `control/override_charge_power`                   | `myhome/eos_connect/control/override_charge_power`             | Integer (W)                   | Override charge power                                    |
| `control/override_active`                         | `myhome/eos_connect/control/override_active`                   | Boolean (`true`/`false`)      | Whether override is active                               |
| `control/override_end_time`                       | `myhome/eos_connect/control/override_end_time`                 | ISO timestamp                 | When override ends                                       |
| `control/overall_state`                           | `myhome/eos_connect/control/overall_state`                     | Integer (see mode table)      | Current overall system mode                              |
| `control/eos_homeappliance_released`              | `myhome/eos_connect/control/eos_homeappliance_released`        | Boolean                       | Home appliance released flag                             |
| `control/eos_homeappliance_start_hour`            | `myhome/eos_connect/control/eos_homeappliance_start_hour`      | Integer (hour)                | Home appliance start hour                                |
| `battery/soc`                                    | `myhome/eos_connect/battery/soc`                              | Float (%)                     | Battery state of charge                                  |
| `battery/remaining_energy`                        | `myhome/eos_connect/battery/remaining_energy`                  | Integer (Wh)                  | Usable battery capacity                                  |
| `battery/dyn_max_charge_power`                    | `myhome/eos_connect/battery/dyn_max_charge_power`              | Integer (W)                   | Dynamic max charge power                                 |
| `inverter/special/temperature_inverter`           | `myhome/eos_connect/inverter/special/temperature_inverter`     | Float (°C)                    | Inverter temperature (if Fronius)                        |
| `inverter/special/temperature_ac_module`          | `myhome/eos_connect/inverter/special/temperature_ac_module`    | Float (°C)                    | AC module temperature (if Fronius)                       |
| `inverter/special/temperature_dc_module`          | `myhome/eos_connect/inverter/special/temperature_dc_module`    | Float (°C)                    | DC module temperature (if Fronius)                       |
| `inverter/special/temperature_battery_module`     | `myhome/eos_connect/inverter/special/temperature_battery_module`| Float (°C)                   | Battery module temperature (if Fronius)                  |
| `inverter/special/fan_control_01`                 | `myhome/eos_connect/inverter/special/fan_control_01`           | Integer                       | Fan control 1 (if Fronius)                               |
| `inverter/special/fan_control_02`                 | `myhome/eos_connect/inverter/special/fan_control_02`           | Integer                       | Fan control 2 (if Fronius)                               |
| `evcc`                                            | `myhome/eos_connect/evcc`                                      | JSON object                   | Charging state, mode, and session info (if enabled)      |
| `status`                                          | `myhome/eos_connect/status`                                    | String (`"online"`)           | Always set to `"online"`                                 |
| `control/eos_ac_charge_demand`                    | `myhome/eos_connect/control/eos_ac_charge_demand`              | Integer (W)                   | AC charge demand                                         |
| `control/eos_dc_charge_demand`                    | `myhome/eos_connect/control/eos_dc_charge_demand`              | Integer (W)                   | DC charge demand                                         |
| `control/eos_discharge_allowed`                   | `myhome/eos_connect/control/eos_discharge_allowed`             | Boolean                       | Discharge allowed                                        |

---

### Example Usage

- **Monitor battery SOC in Home Assistant:**
  - Subscribe to `myhome/eos_connect/battery/soc` to get real-time battery state of charge.
- **Track optimization runs:**
  - Subscribe to `myhome/eos_connect/optimization/last_run` and `myhome/eos_connect/optimization/next_run` for scheduling info.
- **Visualize inverter temperatures:**
  - Subscribe to `myhome/eos_connect/inverter/special/temperature_inverter` (if Fronius inverter is connected).
- **Check if override is active:**
  - Subscribe to `myhome/eos_connect/control/override_active`.

You can use any MQTT client, automation platform, or dashboard tool to subscribe to these topics and visualize or process the data as needed.

---

**Notes:**
- The `<mqtt_configured_prefix>` is set in your configuration file (see `config.yaml`).
- Some topics (e.g., inverter special values, EVCC) are only published if the corresponding hardware is present and enabled.
- All topics are published with real-time updates as soon as new data is available.

</details>
</br>
EOS Connect can be remotely controlled via MQTT by publishing messages to specific topics. This allows you to change system modes, set override durations, and adjust grid charge power from external tools such as Home Assistant, Node-RED, or any MQTT client.
</br></br>
<details>
<summary>MQTT Data Subscribed</summary>



**Base topic:**  
`<mqtt_configured_prefix>/eos_connect/`  
*(Set `<mqtt_configured_prefix>` in your `config.yaml`, e.g., `myhome`)*

---

### Subscribed Topics

| Topic Suffix                      | Full Topic Example                                         | Expected Payload         | Description / Effect                                  |
|------------------------------------|-----------------------------------------------------------|-------------------------|-------------------------------------------------------|
| `control/overall_state/set`        | `myhome/eos_connect/control/overall_state/set`            | Integer or string (mode)| Changes the system mode (see table below)             |
| `control/override_remain_time/set` | `myhome/eos_connect/control/override_remain_time/set`     | String `"HH:MM"`        | Sets the override duration (e.g., `"02:00"`)          |
| `control/override_charge_power/set`| `myhome/eos_connect/control/override_charge_power/set`    | Integer (watts)         | Sets the override grid charge power (e.g., `2000`)    |

---

### System Mode Control (`control/overall_state/set`)

You can set the system mode by publishing either the **mode name** (string) or the **mode number** (integer).  
**Only the following values are accepted:**

| Mode Name         | Mode Number | Description                                 |
|-------------------|-------------|---------------------------------------------|
| `Auto`            | 0           | Fully automatic optimization (default mode) |
| `ChargeFromGrid`  | 1           | Force battery charging from the grid        |
| `Discharge`       | 2           | Force battery discharge                     |
| `Idle`            | 3           | No charging or discharging                  |
| `PVOnly`          | 4           | Charge battery only from PV (solar)         |

---

### How to Use

- **Publish a message** to the desired topic with the correct payload.
- The system will immediately process the command and update its state.
- You can use any MQTT client, automation platform, or script.

#### Examples

- **Set system mode to "Auto":**
  ```bash
  mosquitto_pub -t "myhome/eos_connect/control/overall_state/set" -m "Auto"
  ```
  or
  ```bash
  mosquitto_pub -t "myhome/eos_connect/control/overall_state/set" -m "0"
  ```

- **Force battery charging from grid:**
  ```bash
  mosquitto_pub -t "myhome/eos_connect/control/overall_state/set" -m "ChargeFromGrid"
  ```
  or
  ```bash
  mosquitto_pub -t "myhome/eos_connect/control/overall_state/set" -m "1"
  ```

- **Set override duration to 1 hour 30 minutes:**
  ```bash
  mosquitto_pub -t "myhome/eos_connect/control/override_remain_time/set" -m "01:30"
  ```

- **Set override grid charge power to 1500 W:**
  ```bash
  mosquitto_pub -t "myhome/eos_connect/control/override_charge_power/set" -m "1500"
  ```

---

**Notes:**
- The `<mqtt_configured_prefix>` is set in your configuration file (see `config.yaml`).
- Payloads must match the expected format for each topic.
- Any value other than those listed for system mode will be ignored or rejected.
- These topics allow you to remotely control and override the energy management system in real time.

</details>

## Configuration

With the first start of **EOS connect** a default `config.yaml` will be generated in the `\src` folder. For full documentation for the different entries go to [CONFIG_README](src/CONFIG_README.md)

*Note: With the default config and a valid EOS server IP/DNS name entry ('eos -> server') - **EOS connect** should be running out of the box with some static defaults as a start point for a step-by-step commissioning.*

## Useful Information

### Getting historical values

#### Home Assistant Persistance

The tool will use historical data from Home Assistant's local database. By default, this database is configured with a retention period of **10 days**.

To improve the accuracy of load forecasts, it is recommended to use data from the last **2 weeks**. 

You can extend the retention period by modifying the `recorder` configuration in Home Assistant's `configuration.yaml` file. If the `recorder` section is not already present, you can add it as shown below:

```yaml
recorder:
  purge_keep_days: 15  # Keep data for 15 days
```

After making this change, restart Home Assistant for the new retention period to take effect.

**Note**: Increasing the retention period will require more storage space, depending on the number of entities being recorded.

If you do not change the retention period, the tool will still work, but it will use the available 10 days of data, which may result in less accurate load forecasts.

#### Openhab

No specific info yet.

## Usage

The application will start fetching energy data from OpenHAB or HomeAssistant and processing it. You can access the web interface at `http://localhost:8081`. For local usage the port is configurable see [CONFIG_README](src/CONFIG_README.md). For docker usage change the mapped port in docker-compose.yml.

## Requirements

To run this project, you need to have the following installed:

- Python >= 3.11


## Installation and Running

You can run EOS Connect in three ways. Choose the method that best fits your environment:

---

<details>
<summary><strong>1. Home Assistant Add-on (Recommended for Home Assistant users)</strong></summary>

- Easiest way if you already use Home Assistant.
- Install the [EOS Add-on](https://github.com/Duetting/ha_eos_addon) and **EOS connect** Add-on from the [ohAnd/ha_addons](https://github.com/ohAnd/ha_addons) repository.
- Configure both add-ons via the Home Assistant UI.
- Both EOS and EOS Connect will run as managed add-ons.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fohand%2Fha_addons)

</details>

---

<details>
<summary><strong>2. Docker (Recommended for most users)</strong></summary>

- Works on any system with Docker and Docker Compose.
- Pull and run the latest image:
  ```bash
  git clone https://github.com/ohAnd/EOS_connect.git
  cd EOS_connect
  docker-compose up --pull always -d
  ```
- The web dashboard will be available at [http://localhost:8081](http://localhost:8081) by default.
- Configure by editing `src/config.yaml`.

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ohand/eos_connect/docker-image.yml)

[get the latest version](https://github.com/ohAnd/EOS_connect/pkgs/container/eos_connect)

</details>

---

<details>
<summary><strong>3. Local Installation (Advanced users, for development or custom setups)</strong></summary>

- Requires Python 3.11+ and pip.
- Clone the repository and install dependencies:
  ```bash
  git clone https://github.com/ohAnd/EOS_connect.git
  cd EOS_connect
  pip install -r requirements.txt
  python src/eos_connect.py
  ```
- Configure by editing `src/config.yaml`.

</details>

---

> For all methods, you need a running instance of [EOS (Energy Optimization System)](https://github.com/Akkudoktor-EOS/EOS).  
> See the [Quick Start](#quick-start) section for more details.


## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any suggestions or improvements.

## Glossary

<details>
<summary>Show Glossary</summary>

| Term / Abbreviation | Meaning                                                                                   |
|---------------------|------------------------------------------------------------------------------------------|
| **EOS**             | Energy Optimization System – the [backend optimizer](https://github.com/Akkudoktor-EOS/EOS) this project connects to.              |
| **SOC**             | State of Charge – the current charge level of your battery, usually in percent (%).      |
| **PV**              | Photovoltaic – refers to solar panels and their energy production.                       |
| **EV**              | Electric Vehicle.                                                                        |
| **EVCC**            | Electric Vehicle Charge Controller – [software](https://github.com/evcc-io/evcc)/hardware for managing EV charging.         |
| **HA**              | [Home Assistant](https://www.home-assistant.io/) – popular open-source smart home platform.                                |
| **OpenHAB**         | Another [open-source](https://www.openhab.org/) smart home platform.                                                 |
| **MQTT**            | Lightweight messaging protocol for IoT and smart home integration.                       |
| **API**             | Application Programming Interface – allows other software to interact with EOS Connect.   |
| **Add-on**          | A packaged extension for Home Assistant, installable via its UI.                         |
| **Grid**            | The public electricity network.                                                          |
| **Dashboard**       | The web interface provided by EOS Connect for monitoring and control.                    |

</details>

## License

This project is licensed under the MIT License. See the LICENSE file for more details.