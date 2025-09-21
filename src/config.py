"""
This module provides the ConfigManager class for managing configuration settings
of the application. The configuration settings are stored in a 'config.yaml' file.
"""

import os
import sys
import logging
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

logger = logging.getLogger("__main__")
logger.info("[Config] loading module ")


class ConfigManager:
    """
    Manages the configuration settings for the application.

    This class handles loading, updating, and saving configuration settings from a 'config.yaml'
    file. If the configuration file does not exist, it creates one with default values and
    prompts the user to restart the server.
    """

    def __init__(self, given_dir):
        self.current_dir = given_dir
        self.config_file = os.path.join(self.current_dir, "config.yaml")
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.yaml.preserve_quotes = True
        self.default_config = self.create_default_config()
        self.config = self.default_config.copy()
        self.load_config()

    def create_default_config(self):
        """
        Creates the default configuration with comments.
        """
        config = CommentedMap(
            {
                "load": CommentedMap(
                    {
                        "source": "default",  # data source for load power
                        "url": "http://homeassistant:8123",  # URL for openhab or homeassistant
                        "access_token": "abc123",  # access token for homeassistant
                        "load_sensor": "Load_Power",  # item / entity for load power data
                        "car_charge_load_sensor": "Wallbox_Power",  # item / entity wallbox power
                        # item / entity for additional load power data
                        "additional_load_1_sensor": "additional_load_1_sensor",
                        "additional_load_1_runtime": 0,  # runtime for additional load 1 in minutes
                        "additional_load_1_consumption": 0,  # consumption for
                        # additional load 1 in Wh
                    }
                ),
                "eos": CommentedMap(
                    {
                        "server": "192.168.100.100",  # Default EOS server address
                        "port": 8503,  # Default port for EOS server
                        "timeout": 180,  # Default timeout for EOS optimize request
                    }
                ),
                "price": CommentedMap(
                    {
                        "source": "default",
                        "token": "tibberBearerToken",  # token for electricity price
                        # 24 hours array with fixed end customer prices in ct/kWh over the day
                        "fixed_24h_array": "10.1,10.1,10.1,10.1,10.1,23,28.23,28.23"
                        + ",28.23,28.23,28.23,23.52,23.52,23.52,23.52,28.17,28.17,34.28,"
                        + "34.28,34.28,34.28,34.28,28,23",
                        "feed_in_price": 0.0,  # feed in price for the grid
                        "negative_price_switch": False,  # switch for negative price
                    }
                ),
                "battery": CommentedMap(
                    {
                        "source": "default",  # data source for battery soc
                        "url": "http://homeassistant:8123",  # URL for openhab or homeassistant
                        "soc_sensor": "battery_SOC",  # item / entity for battery SOC data
                        "access_token": "abc123",  # access token for homeassistant
                        "capacity_wh": 11059,
                        "charge_efficiency": 0.88,
                        "discharge_efficiency": 0.88,
                        "max_charge_power_w": 5000,
                        "min_soc_percentage": 5,
                        "max_soc_percentage": 100,
                        "price_euro_per_wh_accu": 0.0,  # price for battery in euro/Wh
                        "charging_curve_enabled": True,  # enable charging curve
                    }
                ),
                "pv_forecast_source": CommentedMap(
                    {
                        # openmeteo, openmeteo_local, forecast_solar, akkudoktor
                        "source": "akkudoktor",
                    }
                ),
                "pv_forecast": [
                    CommentedMap(
                        {
                            "name": "myPvInstallation1",  # Placeholder for user-defined
                            # configuration name
                            "lat": 47.5,  # Latitude for PV forecast
                            "lon": 8.5,  # Longitude for PV forecast
                            "azimuth": 90.0,  # Azimuth for PV forecast
                            "tilt": 30.0,  # Tilt for PV forecast
                            "power": 4600,  # Power of PV system in Wp
                            "powerInverter": 5000,  # Inverter Power
                            "inverterEfficiency": 0.9,  # Inverter Efficiency for PV forecast
                            "horizon": "10,20,10,15",  # Horizon to calculate shading
                        }
                    )
                ],
                "inverter": CommentedMap(
                    {
                        "type": "default",
                        "address": "192.168.1.12",
                        "user": "customer",
                        "password": "abc123",
                        "max_grid_charge_rate": 5000,
                        "max_pv_charge_rate": 5000,
                    }
                ),
                "evcc": CommentedMap(
                    {
                        # URL to your evcc installation, if not used set to ""
                        # or leave as http://yourEVCCserver:7070
                        "url": "http://yourEVCCserver:7070",
                    }
                ),
                "mqtt": CommentedMap(
                    {
                        "enabled": False,  # Enable MQTT - default: false
                        # URL for MQTT server - default: mqtt://yourMQTTserver
                        "broker": "homeassistant",
                        "port": 1883,  # Port for MQTT server - default: 1883
                        "user": "username",  # Username for MQTT server - default: mqtt
                        "password": "password",  # Password for MQTT server - default: mqtt
                        "tls": False,  # Use TLS for MQTT server - default: false
                        # Enable Home Assistant MQTT auto discovery - default: true
                        "ha_mqtt_auto_discovery": True,
                        # Prefix for Home Assistant MQTT auto discovery - default: homeassistant
                        "ha_mqtt_auto_discovery_prefix": "homeassistant",
                    }
                ),
                "refresh_time": 3,  # Default refresh time in minutes
                "time_zone": "Europe/Berlin",  # Add default time zone
                "eos_connect_web_port": 8081,  # Default port for EOS connect server
                "log_level": "info",  # Default log level
            }
        )
        # load configuration
        config.yaml_set_comment_before_after_key("load", before="Load configuration")
        config["load"].yaml_add_eol_comment(
            "Data source for load power - openhab, homeassistant,"
            + " default (using a static load profile)",
            "source",
        )
        config["load"].yaml_add_eol_comment(
            "access token for homeassistant (optional)", "access_token"
        )
        config["load"].yaml_add_eol_comment(
            "URL for openhab or homeassistant"
            + " (e.g. http://openhab:8080 or http://homeassistant:8123)",
            "url",
        )
        config["load"].yaml_add_eol_comment(
            "item / entity for load power data in watts", "load_sensor"
        )
        config["load"].yaml_add_eol_comment(
            "item / entity for wallbox power data in watts. "
            + '(If not needed, set to `load.car_charge_load_sensor: ""`)',
            "car_charge_load_sensor",
        )
        config["load"].yaml_add_eol_comment(
            "item / entity for additional load power data in watts."
            + ' (If not needed set to `additional_load_1_sensor: ""`)',
            "additional_load_1_sensor",
        )
        config["load"].yaml_add_eol_comment(
            "runtime for additional load 1 in minutes - default: 0"
            + ' (If not needed set to `additional_load_1_sensor: ""`)',
            "additional_load_1_runtime",
        )
        config["load"].yaml_add_eol_comment(
            "consumption for additional load 1 in Wh - default: 0"
            + ' (If not needed set to `additional_load_1_sensor: ""`)',
            "additional_load_1_consumption",
        )

        # eos configuration
        config.yaml_set_comment_before_after_key(
            "eos", before="EOS server configuration"
        )
        config["eos"].yaml_add_eol_comment("EOS server address", "server")
        config["eos"].yaml_add_eol_comment(
            "port for EOS server - default: 8503", "port"
        )
        config["eos"].yaml_add_eol_comment(
            "timeout for EOS optimize request in seconds - default: 180", "timeout"
        )
        # price configuration
        config.yaml_set_comment_before_after_key(
            "price", before="Electricity price configuration"
        )
        config["price"].yaml_add_eol_comment(
            "data source for electricity price tibber, smartenergy_at,"
            + " fixed_24h, default (default uses akkudoktor)",
            "source",
        )
        config["price"].yaml_add_eol_comment("Token for electricity price", "token")
        config["price"].yaml_add_eol_comment(
            "24 hours array with fixed end customer prices in ct/kWh over the day",
            "fixed_24h_array",
        )
        config["price"].yaml_add_eol_comment(
            "feed in price for the grid in €/kWh", "feed_in_price"
        )
        config["price"].yaml_add_eol_comment(
            "switch for no payment if negative stock price is given",
            "negative_price_switch",
        )
        # battery configuration
        config.yaml_set_comment_before_after_key(
            "battery", before="battery configuration"
        )
        config["battery"].yaml_add_eol_comment(
            "Data source for battery soc - openhab, homeassistant, default", "source"
        )
        config["battery"].yaml_add_eol_comment(
            "URL for openhab or homeassistant"
            + " (e.g. http://openhab:8080 or http://homeassistant:8123)",
            "url",
        )
        config["battery"].yaml_add_eol_comment(
            "item / entity for battery SOC data in [0..1]", "soc_sensor"
        )
        config["battery"].yaml_add_eol_comment(
            "access token for homeassistant (optional)", "access_token"
        )
        config["battery"].yaml_add_eol_comment("battery capacity in Wh", "capacity_wh")
        config["battery"].yaml_add_eol_comment(
            "efficiency for charging the battery in [0..1]", "charge_efficiency"
        )
        config["battery"].yaml_add_eol_comment(
            "efficiency for discharging the battery in [0..1]", "discharge_efficiency"
        )
        config["battery"].yaml_add_eol_comment(
            "max charging power in W", "max_charge_power_w"
        )
        config["battery"].yaml_add_eol_comment(
            "URL for battery soc in %", "min_soc_percentage"
        )
        config["battery"].yaml_add_eol_comment(
            "URL for battery soc in %", "max_soc_percentage"
        )
        config["battery"].yaml_add_eol_comment(
            "price for battery in euro/Wh - default: 0.0", "price_euro_per_wh_accu"
        )
        config["battery"].yaml_add_eol_comment(
            "enabling charging curve for controlled charging power"+
            " according to the SOC (default: true)",
            "charging_curve_enabled",
        )

        # pv forecast source configuration
        config.yaml_set_comment_before_after_key(
            "pv_forecast_source", before="pv forecast source configuration"
        )
        config["pv_forecast_source"].yaml_add_eol_comment(
            "data source for solar forecast providers akkudoktor, openmeteo, openmeteo_local,"
            + " forecast_solar, evcc, default (default uses akkudoktor)",
            "source",
        )
        # pv forecast configuration
        config.yaml_set_comment_before_after_key(
            "pv_forecast",
            before="List of PV forecast configurations."
            + " Add multiple entries as needed.\nSee Akkudoktor API "
            + "(https://api.akkudoktor.net/#/pv%20generation%20calculation/getForecast) "
            + "for more details.",
        )
        for index, pv_config in enumerate(config["pv_forecast"]):
            config["pv_forecast"][index].yaml_add_eol_comment(
                "User-defined identifier for the PV installation,"
                + " have to be unique if you use more installations",
                "name",
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Latitude for PV forecast", "lat"
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Longitude for PV forecast", "lon"
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Azimuth for PV forecast", "azimuth"
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Tilt for PV forecast", "tilt"
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Power for PV forecast", "power"
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Power Inverter for PV forecast", "powerInverter"
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Inverter Efficiency for PV forecast",
                "inverterEfficiency",
            )
            config["pv_forecast"][index].yaml_add_eol_comment(
                "Horizon to calculate shading, up to 360 values"
                + " to describe the shading situation for your PV.",
                "horizon",
            )
        # inverter configuration
        config.yaml_set_comment_before_after_key(
            "inverter", before="Inverter configuration"
        )
        config["inverter"].yaml_add_eol_comment(
            "Type of inverter - fronius_gen24, fronius_gen24_legacy, evcc, default"
            + " (default will disable inverter control -"
            + " only displaying the target state) - preset: default",
            "type",
        )
        config["inverter"].yaml_add_eol_comment(
            "Address of the inverter (fronius_gen24/fronius_gen24_legacy only)", "address"
        )
        config["inverter"].yaml_add_eol_comment(
            "Username for the inverter (fronius_gen24/fronius_gen24_legacy only)", "user"
        )
        config["inverter"].yaml_add_eol_comment(
            "Password for the inverter (fronius_gen24/fronius_gen24_legacy only)", "password"
        )
        config["inverter"].yaml_add_eol_comment(
            "Max inverter grid charge rate in W - default: 5000", "max_grid_charge_rate"
        )
        config["inverter"].yaml_add_eol_comment(
            "Max inverter PV charge rate in W - default: 5000", "max_pv_charge_rate"
        )
        # evcc configuration
        config.yaml_set_comment_before_after_key("evcc", before="EVCC configuration")
        config["evcc"].yaml_add_eol_comment(
            '# URL to your evcc installation, if not used set to ""'
            + " or leave as http://yourEVCCserver:7070",
            "url",
        )
        # mqtt configuration
        config.yaml_set_comment_before_after_key("mqtt", before="MQTT configuration")
        config["mqtt"].yaml_add_eol_comment("Enable MQTT - default: false", "enabled")
        config["mqtt"].yaml_add_eol_comment(
            "URL for MQTT server - default: mqtt://yourMQTTserver", "broker"
        )
        config["mqtt"].yaml_add_eol_comment(
            "Port for MQTT server - default: 1883", "port"
        )
        config["mqtt"].yaml_add_eol_comment(
            "Username for MQTT server - default: mqtt", "user"
        )
        config["mqtt"].yaml_add_eol_comment(
            "Password for MQTT server - default: mqtt", "password"
        )
        config["mqtt"].yaml_add_eol_comment(
            "Use TLS for MQTT server - default: false", "tls"
        )
        config["mqtt"].yaml_add_eol_comment(
            "Enable Home Assistant MQTT auto discovery - default: true",
            "ha_mqtt_auto_discovery",
        )
        config["mqtt"].yaml_add_eol_comment(
            "Prefix for Home Assistant MQTT auto discovery - default: homeassistant",
            "ha_mqtt_auto_discovery_prefix",
        )

        # refresh time configuration
        config.yaml_add_eol_comment(
            "Default refresh time of EOS connect in minutes - default: 3",
            "refresh_time",
        )
        # time zone configuration
        config.yaml_add_eol_comment(
            "Default time zone - default: Europe/Berlin", "time_zone"
        )
        # eos connect web port configuration
        config.yaml_add_eol_comment(
            "Default port for EOS connect server - default: 8081",
            "eos_connect_web_port",
        )
        # loglevel configuration
        config.yaml_add_eol_comment(
            "Log level for the application : debug, info, warning, error - default: info",
            "log_level",
        )
        return config

    def load_config(self):
        """
        Reads the configuration from 'config.yaml' file located in the current directory.
        If the file exists, it loads the configuration values.
        If the file does not exist, it creates a new 'config.yaml' file with default values and
        prompts the user to restart the server after configuring the settings.
        """
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config.update(self.yaml.load(f))
            self.check_eos_timeout_and_refreshtime()
        else:
            self.write_config()
            print("Config file not found. Created a new one with default values.")
            print(
                "Please restart the server after configuring the settings in config.yaml"
            )
            sys.exit(0)

    def write_config(self):
        """
        Writes the configuration to 'config.yaml' file located in the current directory.
        """
        logger.info("[Config] writing config file")
        with open(self.config_file, "w", encoding="utf-8") as config_file_handle:
            self.yaml.dump(self.config, config_file_handle)

    def check_eos_timeout_and_refreshtime(self):
        """
        Check if the eos timeout is smaller than the refresh time
        """
        eos_timeout_seconds = self.config["eos"]["timeout"]
        refresh_time_seconds = self.config["refresh_time"] * 60

        if eos_timeout_seconds > refresh_time_seconds:
            logger.error(
                (
                    "[Config] EOS timeout (%s s) is greater than the refresh time (%s s)."
                    " Please adjust the settings."
                ),
                eos_timeout_seconds,
                refresh_time_seconds,
            )
            sys.exit(0)
