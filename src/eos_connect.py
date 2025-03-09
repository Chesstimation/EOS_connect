"""
This module fetches energy data from OpenHAB, processes it, and creates a load profile.
"""

import os
import sys
from datetime import datetime, timedelta
import time
import logging
import json
from threading import Thread
import sched
import pytz
import requests
import pandas as pd
import numpy as np
from flask import Flask, render_template_string
from gevent.pywsgi import WSGIServer
from config import ConfigManager

EOS_TGT_DURATION = 48
EOS_START_TIME = None  # None = midnight before EOS_TGT_DURATION hours

###################################################################################################
###################################################################################################
LOGLEVEL = logging.INFO
logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"
)
streamhandler = logging.StreamHandler(sys.stdout)
streamhandler.setFormatter(formatter)
logger.addHandler(streamhandler)
logger.setLevel(LOGLEVEL)
logger.info("[Main] Starting eos_connect")

base_path = os.path.dirname(os.path.abspath(__file__))
# get param to set a specific path
if len(sys.argv) > 1:
    current_dir = sys.argv[1]
else:
    current_dir = base_path
config_manager = ConfigManager(current_dir)
time_zone = pytz.timezone(config_manager.config["time_zone"])
EOS_SERVER = config_manager.config["eos"]["server"]
EOS_SERVER_PORT = config_manager.config["eos"]["port"]

# *** EOS API URLs ***

EOS_API_PUT_CONFIG_VALUES = (
    f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/v1/config/value"  # ?key=..&value=..
)
EOS_API_POST_UPDATE_CONFIG_FROM_CONFIG_FILE = {
    f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/v1/config/update"
}
EOS_API_PUT_SAVE_CONFIG_TO_CONFIG_FILE = {
    f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/v1/config/file"
}
EOS_API_GET_CONFIG_VALUES = {f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/v1/config"}
EOS_API_PUT_LOAD_PROFILE = {
    f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/v1/measurement/load-mr/value/by-name"
}
EOS_API_PUT_LOAD_SERIES = {
    f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/v1/measurement/load-mr/series/by-name"  #
}  # ?name=Household
EOS_API_OPTIMIZE = f"http://{EOS_SERVER}:{EOS_SERVER_PORT}/optimize"

EOS_API_GET_PV_FORECAST = "https://api.akkudoktor.net/forecast"
TIBBER_API = "https://api.tibber.com/v1-beta/gql"


# EOS basic API helper
def set_config_value(key, value):
    """
    Set a configuration value on the EOS server.
    """
    if isinstance(value, list):
        value = json.dumps(value)
    params = {"key": key, "value": value}
    response = requests.put(EOS_API_PUT_CONFIG_VALUES, params=params, timeout=10)
    response.raise_for_status()
    logger.info(
        "[Main] Config value set successfully. Key: {key} \t\t => Value: {value}"
    )


def send_measurement_to_eos(dataframe):
    """
    Send the measurement data to the EOS server.
    """
    params = {
        "data": dataframe.to_json(orient="index"),
        "dtype": "float64",
        "tz": "UTC",
    }
    response = requests.put(
        EOS_API_PUT_LOAD_SERIES + "?name=Household", params=params, timeout=10
    )
    response.raise_for_status()
    if response.status_code == 200:
        logger.debug("[SEND_TO_EOS] Data sent to EOS server successfully.")
    else:
        logger.debug(
            "[SEND_TO_EOS]"
            "Failed to send data to EOS server. Status code: {response.status_code}"
            ", Response: {response.text}"
        )


def eos_set_optimize_request(payload, timeout=120):
    """
    Send the optimize request to the EOS server.
    """
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    request_url = EOS_API_OPTIMIZE + "?start_hour=" + str(datetime.now(time_zone).hour)
    logger.info("[OPTIMIZE] request optimization with: %s", request_url)
    response = requests.post(
        request_url, headers=headers, json=payload, timeout=timeout
    )
    response.raise_for_status()
    logger.info("[Main] Optimize response retrieved successfully.")
    return response.json()


# getting data


def get_prices_for_today_and_tomorrow(tgt_duration, start_time=None):
    """
    Fetches and processes electricity prices for today and tomorrow.

    This function retrieves electricity prices for today and tomorrow from a web service,
    processes the prices, and returns a list of prices for the specified duration starting
    from the specified start time. If tomorrow's prices are not available, today's prices are
    repeated for tomorrow.

    Args:
        tgt_duration (int): The target duration in hours for which the prices are needed.
        start_time (datetime, optional): The start time for fetching prices. Defaults to None.

    Returns:
        list: A list of electricity prices for the specified duration starting
              from the specified start time.
    """
    # logger.info("[PRICES] Prices fetching started")
    if config_manager.config["price"]["source"] != "tibber":
        logger.error("[PRICES] Price source currently not supported.")
        return []
    headers = {
        "Authorization": config_manager.config["price"]["token"],
        "Content-Type": "application/json",
    }
    query = """
    {
        viewer {
            homes {
                currentSubscription {
                    priceInfo {
                        today {
                            total
                            startsAt
                        }
                        tomorrow {
                            total
                            startsAt
                        }
                    }
                }
            }
        }
    }
    """
    response = requests.post(
        TIBBER_API, headers=headers, json={"query": query}, timeout=10
    )
    response.raise_for_status()
    data = response.json()
    today_prices = json.dumps(
        data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]
    )
    tomorrow_prices = json.dumps(
        data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"][
            "tomorrow"
        ]
    )

    today_prices_json = json.loads(today_prices)
    tomorrow_prices_json = json.loads(tomorrow_prices)
    prices = []

    for price in today_prices_json:
        prices.append(round(price["total"] / 1000, 9))
        logger.debug(
            "[Main] day 1 - price for %s -> %s", price["startsAt"], price["total"]
        )
    if tomorrow_prices_json:
        for price in tomorrow_prices_json:
            prices.append(round(price["total"] / 1000, 9))
            logger.debug(
                "[Main] day 2 - price for %s -> %s", price["startsAt"], price["total"]
            )
    else:
        prices.extend(prices[:24])  # Repeat today's prices for tomorrow

    if start_time is None:
        start_time = datetime.now(time_zone).replace(minute=0, second=0, microsecond=0)
    current_hour = start_time.hour
    extended_prices = prices[current_hour : current_hour + tgt_duration]

    if len(extended_prices) < tgt_duration:
        remaining_hours = tgt_duration - len(extended_prices)
        extended_prices.extend(prices[:remaining_hours])
    logger.info("[PRICES] Prices fetched successfully.")
    return extended_prices


def create_forecast_request(pv_config_name):
    """
    Creates a forecast request URL for the EOS server.
    """
    horizont_string = ""
    if config_manager.config["pv_forecast"][pv_config_name]["horizont"] != "":
        horizont_string = "&horizont=" + str(
            config_manager.config["pv_forecast"][pv_config_name]["horizont"]
        )
    return (
        EOS_API_GET_PV_FORECAST
        + "?lat="
        + str(config_manager.config["pv_forecast"][pv_config_name]["lat"])
        + "&lon="
        + str(config_manager.config["pv_forecast"][pv_config_name]["lon"])
        + "&azimuth="
        + str(config_manager.config["pv_forecast"][pv_config_name]["azimuth"])
        + "&tilt="
        + str(config_manager.config["pv_forecast"][pv_config_name]["tilt"])
        + "&power="
        + str(config_manager.config["pv_forecast"][pv_config_name]["power"])
        + "&powerInverter="
        + str(config_manager.config["pv_forecast"][pv_config_name]["powerInverter"])
        + "&inverterEfficiency="
        + str(
            config_manager.config["pv_forecast"][pv_config_name]["inverterEfficiency"]
        )
        + horizont_string
    )


def get_pv_forecast(tgt_value="power", pv_config_name="default", tgt_duration=24):
    """
    Fetches the PV forecast data from the EOS API and processes it to extract
    power and temperature values for the specified duration starting from the current hour.
    """
    if pv_config_name not in config_manager.config["pv_forecast"]:
        # take the first entry if the config name is not found
        pv_config_name = list(config_manager.config["pv_forecast"].keys())[0]
        # print("pv_config_name not found in config, using first pv config entry: " + pv_config_name)

    forecast_request_payload = create_forecast_request(pv_config_name)
    # print(forecast_request_payload)
    response = requests.get(forecast_request_payload, timeout=10)
    response.raise_for_status()
    day_values = response.json()
    day_values = day_values["values"]

    forecast_values = []
    # current_time = datetime.now(time_zone).astimezone()
    current_time = (
        datetime.now(time_zone)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone()
    )
    end_time = current_time + timedelta(hours=tgt_duration)

    for forecast_entry in day_values:
        for forecast in forecast_entry:
            entry_time = datetime.fromisoformat(forecast["datetime"]).astimezone()
            if current_time <= entry_time < end_time:
                forecast_values.append(forecast.get(tgt_value, 0))
    logger.info(
        "[FORECAST] forecast fetched successfully for %s (%s)",
        pv_config_name,
        tgt_value,
    )
    return forecast_values


def get_summerized_pv_forecast(tgt_duration=24):
    """
    requesting pv forecast freach config entry and summarize the values
    """
    forecast_values = []
    for config_entry in config_manager.config["pv_forecast"]:
        # logger.debug("[FORECAST] fetching forecast for %s", config_entry)
        forecast = get_pv_forecast("power", config_entry, tgt_duration)
        # print("values for " + config_entry+ " -> ")
        # print(forecast)
        if not forecast_values:
            forecast_values = forecast
        else:
            forecast_values = [x + y for x, y in zip(forecast_values, forecast)]
    return forecast_values


def battery_get_current_soc():
    """
    Fetch the current state of charge (SOC) of the battery from OpenHAB.
    """
    # default value for start SOC = 5
    if config_manager.config["battery"]["source"] == "default":
        logger.debug("[BATTERY] Battery source set default with SOC = 5%")
        return 5
    if config_manager.config["battery"]["source"] == "homeassistant":
        logger.error("[BATTERY] Battery source currently not supported. Using default.")
        return 5
    if config_manager.config["battery"]["source"] != "openhab":
        logger.error("[BATTERY] Battery source currently not supported. Using default.")
        return 5
    url = config_manager.config["battery"]["url"]
    response = requests.get(url, timeout=6)
    response.raise_for_status()
    data = response.json()
    soc = float(data["state"]) * 100
    return round(soc)


def eos_save_config_to_config_file():
    """
    Save the current configuration to the configuration file on the EOS server.
    """
    response = requests.put(EOS_API_PUT_SAVE_CONFIG_TO_CONFIG_FILE, timeout=10)
    response.raise_for_status()
    logger.debug("[EOS_CONFIG] Config saved to config file successfully.")


def eos_update_config_from_config_file():
    """
    Update the current configuration from the configuration file on the EOS server.
    """
    response = requests.post(EOS_API_POST_UPDATE_CONFIG_FROM_CONFIG_FILE, timeout=10)
    response.raise_for_status()
    logger.info("[EOS_CONFIG] Config updated from config file successfully.")


# function that creates a pandas dataframe with a DateTimeIndex with the given average profile
def create_dataframe(profile):
    """
    Creates a pandas DataFrame with hourly energy values for a given profile.

    Args:
        profile (list of tuples): A list of tuples where each tuple contains:
            - month (int): The month (1-12).
            - weekday (int): The day of the week (0=Monday, 6=Sunday).
            - hour (int): The hour of the day (0-23).
            - energy (float): The energy value to set.

    Returns:
        pandas.DataFrame: A DataFrame with a DateTime index for the year 2025 and a 'Household'
        column containing the energy values from the profile.
    """

    # create a list of all dates in the year
    dates = pd.date_range(start="1/1/2025", end="31/12/2025", freq="H")
    # create an empty dataframe with the dates as index
    df = pd.DataFrame(index=dates)
    # add a column 'Household' to the dataframe with NaN values
    df["Household"] = np.nan
    # iterate over the profile and set the energy values in the dataframe
    for entry in profile:
        month = entry[0]
        weekday = entry[1]
        hour = entry[2]
        energy = entry[3]
        # get the dates that match the month, weekday and hour
        dates = df[
            (df.index.month == month)
            & (df.index.weekday == weekday)
            & (df.index.hour == hour)
        ].index
        # set the energy value for the dates
        for date in dates:
            df.loc[date, "Household"] = energy
    return df

# get load data from url persistance source

def fetch_energy_data_from_openhab(openhab_item_url, start_time, end_time):
    """
    Fetch energy data from the specified OpenHAB item URL within the given time range.
    """
    if openhab_item_url == "":
        return {"data": []}
    params = {"starttime": start_time.isoformat(), "endtime": end_time.isoformat()}
    response = requests.get(openhab_item_url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

def process_energy_data(data):
    """
    Processes energy data to calculate the average energy consumption.
    """
    total_energy = 0
    count = len(data["data"])
    for data_entry in data["data"]:
        total_energy += float(data_entry["state"])
    if count > 0:
        return round(total_energy / count, 4)
    return 0

def create_load_profile_from_last_days(tgt_duration, start_time=None):
    """
    Creates a load profile for energy consumption over the last `tgt_duration` hours.

    The function calculates the energy consumption for each hour from the current hour
    going back `tgt_duration` hours. It fetches energy data for base load and additional loads,
    processes the data, and sums the energy values. If the total energy for an hour is zero,
    it skips that hour. The resulting load profile is a list of energy consumption values
    for each hour.

    """
    if config_manager.config["load"]["source"] == "default":
        logger.error("[LOAD] using load source default")
        default_profile = [
            200.0,
            200.0,
            200.0,
            200.0,
            200.0,
            200.0,
            300.0,
            300.0,
            300.0,
            300.0,
            300.0,
            400.0,
            400.0,
            400.0,
            300.0,
            300.0,
            200.0,
            300.0,
            400.0,
            400.0,
            300.0,
            300.0,
            300.0,
            200.0,
            200.0,
            200.0,
            200.0,
            200.0,
            200.0,
            200.0,
            300.0,
            300.0,
            300.0,
            300.0,
            300.0,
            400.0,
            400.0,
            400.0,
            300.0,
            300.0,
            200.0,
            300.0,
            400.0,
            400.0,
            300.0,
            300.0,
            300.0,
            200.0
        ]
        return default_profile[:tgt_duration]

    if config_manager.config["load"]["source"] != "openhab":
        logger.error("[LOAD] Load source currently not supported.")
        return []

    logger.info("[LOAD] Creating load profile from openhab ...")
    current_time = datetime.now(time_zone).replace(minute=0, second=0, microsecond=0)
    if start_time is None:
        start_time = current_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(hours=tgt_duration)
        end_time = start_time + timedelta(hours=tgt_duration)
    else:
        start_time = current_time - timedelta(hours=tgt_duration)
        end_time = current_time

    load_profile = []
    current_hour = start_time

    while current_hour < end_time:
        next_hour = current_hour + timedelta(hours=1)
        # logger.debug("[LOAD] Fetching data for %s to %s",current_hour, next_hour)

        energy_data = fetch_energy_data_from_openhab(
            config_manager.config["load"]["url"], current_hour, next_hour
        )
        energy = process_energy_data(energy_data) * -1
        if energy == 0:
            current_hour += timedelta(hours=1)
            continue

        energy_sum = energy
        # easy workaround to prevent car charging energy data in the standard load profile
        if energy_sum > 10800:
            energy_sum = energy_sum - 10800
        elif energy_sum > 9200:
            energy_sum = energy_sum - 9200

        load_profile.append(energy_sum)
        logger.debug("[LOAD] Energy for %s: %s", current_hour, energy_sum)

        current_hour += timedelta(hours=1)
    logger.info("[LOAD] Load profile created successfully.")
    return load_profile

# summarize all date


def create_optimize_request(api_version="new"):
    """
    Creates an optimization request payload for energy management systems.

    Args:
        api_version (str): The API version to use for the request. Defaults to "new".

    Returns:
        dict: A dictionary containing the payload for the optimization request.
    """

    def get_ems_data():
        return {
            "preis_euro_pro_wh_akku": 0.0,
            "einspeiseverguetung_euro_pro_wh": 0.00000001,
            "gesamtlast": create_load_profile_from_last_days(
                EOS_TGT_DURATION,
                datetime.now(time_zone).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            ),
            "pv_prognose_wh": get_summerized_pv_forecast(EOS_TGT_DURATION),
            "strompreis_euro_pro_wh": get_prices_for_today_and_tomorrow(
                EOS_TGT_DURATION,
                datetime.now(time_zone).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            ),
        }

    def get_pv_akku_data(api_version="new"):
        if api_version != "new":
            return {
                "kapazitaet_wh": 11059,
                "lade_effizienz": 0.88,
                "entlade_effizienz": 0.88,
                "max_ladeleistung_w": 5000,
                "start_soc_prozent": battery_get_current_soc(),
                "min_soc_prozent": 5,
                "max_soc_prozent": 100,
            }
        return {
            "capacity_wh": 11059,
            "charging_efficiency": 0.88,
            "discharging_efficiency": 0.88,
            "max_charge_power_w": 5000,
            "initial_soc_percentage": battery_get_current_soc(),
            "min_soc_percentage": 0,
            "max_soc_percentage": 100,
        }

    def get_wechselrichter_data(api_version="new"):
        if api_version != "new":
            return {"max_leistung_wh": 8500}
        return {"max_power_wh": 8500}

    def get_eauto_data(api_version="new"):
        if api_version != "new":
            return {
                "kapazitaet_wh": 1,
                "lade_effizienz": 0.90,
                "entlade_effizienz": 0.95,
                "max_ladeleistung_w": 1,
                "start_soc_prozent": 50,
                "min_soc_prozent": 5,
                "max_soc_prozent": 100,
            }
        return {
            "capacity_wh": 27000,
            "charging_efficiency": 0.90,
            "discharging_efficiency": 0.95,
            "max_charge_power_w": 7360,
            "initial_soc_percentage": 50,
            "min_soc_percentage": 5,
            "max_soc_percentage": 100,
        }

    def get_dishwasher_data():
        return {"consumption_wh": 1, "duration_h": 1}

    if api_version != "new":
        payload = {
            "ems": get_ems_data(),
            "pv_akku": get_pv_akku_data(api_version),
            "inverter": get_wechselrichter_data(api_version),
            "eauto": get_eauto_data(api_version),
            "dishwasher": get_dishwasher_data(),
            "temperature_forecast": get_pv_forecast(
                tgt_value="temperature", tgt_duration=EOS_TGT_DURATION
            ),
            "start_solution": None,
        }
    else:
        payload = {
            "ems": get_ems_data(),
            "pv_akku": get_pv_akku_data(),
            "wechselrichter": get_wechselrichter_data(),
            "eauto": get_eauto_data(),
            "dishwasher": get_dishwasher_data(),
            "temperature_forecast": get_pv_forecast(
                tgt_value="temperature", tgt_duration=EOS_TGT_DURATION
            ),
            "start_solution": None,
        }

    return payload


app = Flask(__name__)


@app.route("/", methods=["GET"])
def main_page():
    """
    Renders the main page of the web application.

    This function reads the content of the 'index.html' file located in the 'web' directory
    and returns it as a rendered template string.
    """
    with open(base_path + "/web/index.html", "r", encoding="utf-8") as html_file:
        return render_template_string(html_file.read())


@app.route("/json/optimize_request.json", methods=["GET"])
def get_optimize_request():
    """
    Returns the content of the 'optimize_request.json' file as a JSON response.
    """
    with open(
        base_path + "/json/optimize_request.json", "r", encoding="utf-8"
    ) as json_file:
        return json_file.read()


@app.route("/json/optimize_response.json", methods=["GET"])
def get_optimize_response():
    """
    Returns the content of the 'optimize_response.json' file as a JSON response.
    """
    with open(
        base_path + "/json/optimize_response.json", "r", encoding="utf-8"
    ) as json_file:
        return json_file.read()


if __name__ == "__main__":
    # initial config
    # set_config_value("latitude", 48.812)
    # set_config_value("longitude", 8.907)

    # set_config_value("measurement_load0_name", "Household")
    # set_config_value("loadakkudoktor_year_energy", 4600)

    # # set_config_value("pvforecast_provider", "PVForecastAkkudoktor")
    # set_config_value("pvforecast_provider", "PVForecast")
    # set_config_value("pvforecast0_surface_tilt", 31)
    # set_config_value("pvforecast0_surface_azimuth", 13)
    # set_config_value("pvforecast0_peakpower", 860.0)
    # set_config_value("pvforecast0_inverter_paco", 800)
    # # set_config_value("pvforecast0_userhorizon", [0,0])

    # # persist and update config
    # eos_save_config_to_config_file()

    # print(get_prices_for_today_and_tomorrow(EOS_TGT_DURATION,
    # datetime.now(time_zone).replace(hour=0, minute=0, second=0, microsecond=0)))

    # test = get_summerized_pv_forecast(EOS_TGT_DURATION)
    # print(test)

    # forecast = get_pv_forecast("power", "Garage_West", 24)
    # print(forecast)

    # json_optimize_input = create_optimize_request("old")

    # with open(base_path + "/json/optimize_request.json", "w", encoding="utf-8") as file:
    #     json.dump(json_optimize_input, file, indent=4)

    # optimized_response = eos_set_optimize_request(json_optimize_input)
    # optimized_response["timestamp"] = datetime.now(time_zone).isoformat()

    # with open(
    #     base_path + "/json/optimize_response.json", "w", encoding="utf-8"
    # ) as file:
    #     json.dump(optimized_response, file, indent=4)

    # sys.exit()

    http_server = WSGIServer(
        ("0.0.0.0", config_manager.config["eos_connect_web_port"]),
        app,
        log=None,
        error_log=logger,
    )

    def run_optimization_loop():
        """
        Continuously runs the optimization loop until interrupted.
        This function performs the following steps in an infinite loop:
        1. Logs the start of a new run.
        2. Creates an optimization request and saves it to a JSON file.
        3. Sends the optimization request and receives the optimized response.
        4. Adds a timestamp to the optimized response and saves it to a JSON file.
        5. Calculates the time to the next evaluation based on a predefined interval.
        6. Logs the next evaluation time and sleeps until that time.
        The loop can be interrupted with a KeyboardInterrupt, which will log an exit message and
        terminate the program.
        Raises:
            KeyboardInterrupt: If the loop is interrupted by the user.
        """

        scheduler = sched.scheduler(time.time, time.sleep)

        def run_optimization_event(sc):
            logger.info("[Main] start new run")
            # create optimize request
            json_optimize_input = create_optimize_request("old")

            with open(
                base_path + "/json/optimize_request.json", "w", encoding="utf-8"
            ) as file:
                json.dump(json_optimize_input, file, indent=4)

            optimized_response = eos_set_optimize_request(json_optimize_input)
            optimized_response["timestamp"] = datetime.now(time_zone).isoformat()

            with open(
                base_path + "/json/optimize_response.json", "w", encoding="utf-8"
            ) as file:
                json.dump(optimized_response, file, indent=4)

            loop_now = datetime.now(time_zone).astimezone()
            # reset base to full minutes on the clock
            next_eval = loop_now - timedelta(
                minutes=loop_now.minute % config_manager.config["refresh_time"],
                seconds=loop_now.second,
                microseconds=loop_now.microsecond,
            )
            # add time increments to trigger next evaluation
            next_eval += timedelta(
                minutes=config_manager.config["refresh_time"], seconds=0, microseconds=0
            )
            sleeptime = (next_eval - loop_now).total_seconds()
            minutes, seconds = divmod(sleeptime, 60)
            logger.info(
                "[Main] Next optimization at %s. Sleeping for %d min %.0f seconds\n",
                next_eval.strftime("%H:%M:%S"),
                minutes,
                seconds,
            )
            scheduler.enter(sleeptime, 1, run_optimization_event, (sc,))

        scheduler.enter(0, 1, run_optimization_event, (scheduler,))
        scheduler.run()

    optimization_thread = Thread(target=run_optimization_loop)
    optimization_thread.start()

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[Main] Shutting down server")
        http_server.stop()
        optimization_thread.join(timeout=10)
        if optimization_thread.is_alive():
            logger.warning(
                "[Main] Optimization thread did not finish in time, terminating."
            )
            # Terminate the thread (not recommended, but shown here for completeness)
            # Note: Python does not provide a direct way to kill a thread. This is a workaround.
            import ctypes

            if optimization_thread.ident is not None:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(optimization_thread.ident),
                    ctypes.py_object(SystemExit),
                )
        logger.info("[Main] Server stopped")
        sys.exit(0)
