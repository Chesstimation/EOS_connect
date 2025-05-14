"""
This module provides the `LoadInterface` class, which is used to fetch and process energy data
from various sources such as OpenHAB and Home Assistant. It also includes methods to create
load profiles based on historical energy consumption data.
"""

from datetime import datetime, timedelta
import logging
import requests

logger = logging.getLogger("__main__")
logger.info("[LOAD-IF] loading module ")


class LoadInterface:
    """
    LoadInterface class provides methods to fetch and process energy data from various sources
    such as OpenHAB and Home Assistant. It also supports creating load profiles based on the
    retrieved energy data.
    """

    def __init__(
        self,
        src,
        url,
        load_sensor,
        car_charge_load_sensor,
        access_token,
        timezone="UTC",
    ):
        self.src = src
        self.url = url
        self.load_sensor = load_sensor
        self.car_charge_load_sensor = car_charge_load_sensor
        self.access_token = access_token
        self.time_zone = timezone

    # get load data from url persistance source
    def fetch_energy_data_from_openhab(self, openhab_item_url, start_time, end_time):
        """
        Fetch energy data from the specified OpenHAB item URL within the given time range.
        """
        if openhab_item_url == "":
            return {"data": []}
        openhab_item_url = self.url + "/rest/persistence/items/" + self.load_sensor
        params = {"starttime": start_time.isoformat(), "endtime": end_time.isoformat()}
        try:
            response = requests.get(openhab_item_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(
                "[LOAD-IF] OPENHAB - Request timed out while fetching energy data."
            )
            return {"data": []}
        except requests.exceptions.RequestException as e:
            logger.error(
                "[LOAD-IF] OPENHAB - Request failed while fetching energy data: %s", e
            )
            return {"data": []}

    def fetch_historical_energy_data_from_homeassistant(
        self, entity_id, start_time, end_time
    ):
        """
        Fetch historical energy data for a specific entity from Home Assistant.

        Args:
            entity_id (str): The ID of the entity to fetch data for.
            start_time (datetime): The start time for the historical data.
            end_time (datetime): The end time for the historical data.

        Returns:
            list: A list of historical state changes for the entity.
        """
        # Headers for the API request
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        # API endpoint to get the history of the entity
        url = f"{self.url}/api/history/period/{start_time.isoformat()}"

        # Parameters for the API request
        params = {"filter_entity_id": entity_id, "end_time": end_time.isoformat()}

        # Make the API request
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            # Check if the request was successful
            if response.status_code == 200:
                historical_data = response.json()
                # Extract only 'state' and 'last_updated' from the historical data
                filtered_data = [
                    {"state": entry["state"], "last_updated": entry["last_updated"]}
                    for sublist in historical_data
                    for entry in sublist
                ]
                return filtered_data
            logger.error(
                "[LOAD-IF] HOMEASSISTANT - Failed to retrieve historical data: %s",
                response.status_code,
            )
            logger.error(response.text)
            return []
        except requests.exceptions.Timeout:
            logger.error(
                "[LOAD-IF] HOMEASSISTANT - Request timed out while fetching historical energy data."
            )
            return []
        except requests.exceptions.RequestException as e:
            logger.error(
                "[LOAD-IF] HOMEASSISTANT - Request failed while fetching"
                + " historical energy data: %s",
                e,
            )
            return []

    def process_energy_data(self, data):
        """
        Processes energy data to calculate the average energy consumption based on timestamps.
        """
        total_energy = 0.0
        total_duration = 0.0
        current_state = 0.0
        last_state = 0.0
        current_time = datetime.now()
        duration = 0.0

        for i in range(len(data["data"]) - 1):
            try:
                current_state = float(data["data"][i]["state"])
                last_state = float(data["data"][i + 1]["state"])
                current_time = datetime.fromisoformat(data["data"][i]["last_updated"])
                next_time = datetime.fromisoformat(data["data"][i + 1]["last_updated"])
            except (ValueError, KeyError):
                continue

            duration = (next_time - current_time).total_seconds()
            total_energy += current_state * duration
            total_duration += duration
        # add last data point to total energy calculation if duration is less than 1 hour
        if total_duration < 3600:
            duration = (
                (current_time + timedelta(seconds=3600)).replace(
                    minute=0, second=0, microsecond=0
                )
                - current_time
            ).total_seconds()
            total_energy += last_state * duration
            total_duration += duration
        if total_duration > 0:
            return round(total_energy / total_duration, 4)
        return 0

    def create_load_profile_openhab_from_last_days(self, tgt_duration, start_time=None):
        """
        Creates a load profile for energy consumption over the last `tgt_duration` hours.

        The function calculates the energy consumption for each hour from the current hour
        going back `tgt_duration` hours. It fetches energy data for base load and additional loads,
        processes the data, and sums the energy values. If the total energy for an hour is zero,
        it skips that hour. The resulting load profile is a list of energy consumption values
        for each hour.

        """
        logger.info("[LOAD-IF] Creating load profile from openhab ...")
        current_time = datetime.now(self.time_zone).replace(
            minute=0, second=0, microsecond=0
        )
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
            # logger.debug("[LOAD-IF] Fetching data for %s to %s",current_hour, next_hour)

            energy_data = self.fetch_energy_data_from_openhab(
                self.url, current_hour, next_hour
            )
            energy = self.process_energy_data(energy_data)
            # if energy == 0:
            #     current_hour += timedelta(hours=1)
            #     continue

            energy_sum = energy
            # easy workaround to prevent car charging energy data in the standard load profile
            if energy_sum > 10800:
                energy_sum = energy_sum - 10800
            elif energy_sum > 9200:
                energy_sum = energy_sum - 9200

            load_profile.append(energy_sum)
            logger.debug("[LOAD-IF] Energy for %s: %s", current_hour, energy_sum)

            current_hour += timedelta(hours=1)
        logger.info("[LOAD-IF] Load profile created successfully.")
        return load_profile

    def create_load_profile_homeassistant_from_last_days(
        self, tgt_duration, start_time=None
    ):
        """
        Creates a load profile for energy consumption over the last `tgt_duration` hours.

        This function calculates the energy consumption for each hour from the current hour
        going back `tgt_duration` hours. It fetches energy data from Home Assistant,
        processes the data, and sums the energy values. If the total energy for an hour is zero,
        it skips that hour. The resulting load profile is a list of energy consumption values
        for each hour.

        Args:
            tgt_duration (int): The target duration in hours for which the load profile is needed.
            start_time (datetime, optional): The start time for fetching the load profile.
            Defaults to None.

        Returns:
            list: A list of energy consumption values for the specified duration.
        """
        logger.info("[LOAD-IF] Creating load profile from Home Assistant ...")
        current_time = datetime.now(self.time_zone).replace(
            minute=0, second=0, microsecond=0
        )
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

        # current_hour = datetime.strptime("18.03.2025 11:00", "%d.%m.%Y %H:%M")
        # end_time = current_hour + timedelta(hours=tgt_duration)

        # check car load data for W or kW
        car_load_data = self.fetch_historical_energy_data_from_homeassistant(
            self.car_charge_load_sensor, current_hour, end_time
        )
        # check for max value in car_load_data
        max_car_load = 0
        car_load_unit_factor = 1
        for data_entry in car_load_data:
            try:
                float(data_entry["state"])
            except ValueError:
                continue
            max_car_load = max(max_car_load, float(data_entry["state"]))
        if 0 < max_car_load < 23:
            max_car_load = max_car_load * 1000
            car_load_unit_factor = 1000
        logger.debug("[LOAD-IF] Max car load: %s W", round(max_car_load, 0))

        while current_hour < end_time:
            next_hour = current_hour + timedelta(hours=1)
            # logger.debug("[LOAD-IF] Fetching data for %s to %s", current_hour, next_hour)
            energy_data = self.fetch_historical_energy_data_from_homeassistant(
                self.load_sensor, current_hour, next_hour
            )
            car_load_data = self.fetch_historical_energy_data_from_homeassistant(
                self.car_charge_load_sensor, current_hour, next_hour
            )

            # print(f'HA Energy data: {car_load_data}')
            energy = abs(self.process_energy_data({"data": energy_data}))
            car_load_energy = abs(
                self.process_energy_data({"data": car_load_data}) * car_load_unit_factor
            )
            car_load_energy = max(car_load_energy, 0)  # prevent negative values
            # print(f'HA Energy Orig: {energy}')
            # print(f'HA Car load energy: {car_load_energy}')
            energy = energy - car_load_energy
            if energy < 0:
                logger.error(
                    "[LOAD-IF] DATA ERROR Energy for %s: %5.1f Wh (car load: %5.1f Wh)",
                    current_hour,
                    round(energy, 1),
                    round(car_load_energy, 1),
                )
            # print(f'HA Energy Final: {energy}')
            # if energy == 0:
            #     current_hour += timedelta(hours=1)
            #     continue

            energy_sum = energy

            load_profile.append(energy_sum)
            logger.debug(
                "[LOAD-IF] Energy for %s: %5.1f Wh (car load: %5.1f Wh)",
                current_hour,
                round(energy, 1),
                round(car_load_energy, 1),
            )
            # logger.debug("[LOAD-IF] Energy for %s: %s", current_hour, round(energy_sum,1))

            current_hour += timedelta(hours=1)
        logger.info("[LOAD-IF] Load profile created successfully.")
        return load_profile

    def __get_car_load_list_from_to(self, start_time, end_time):
        """
        Retrieves and processes car load data within a specified time range.
        This method fetches historical energy data for car charging from Home Assistant,
        determines the maximum car load, and adjusts the unit of measurement if necessary.
        The processed data is then returned with all values converted to the appropriate unit.
        Args:
            start_time (datetime): The start time of the data retrieval period.
            end_time (datetime): The end time of the data retrieval period.
        Returns:
            list[dict]: A list of dictionaries containing the processed car load data.
                        Each dictionary includes a "state" key with the adjusted load value.
        Raises:
            ValueError: If a data entry's "state" value cannot be converted to a float.
            KeyError: If a data entry does not contain the "state" key.
        Notes:
            - If the maximum car load is between 0 and 23 (assumed to be in kW), it is
              converted to W.
            - All load values are multiplied by the determined unit factor before being returned.
        """

        # check car load data for W or kW
        car_load_data = self.fetch_historical_energy_data_from_homeassistant(
            self.car_charge_load_sensor, start_time, end_time
        )
        # check for max value in car_load_data
        # max_car_load = 0
        # car_load_unit_factor = 1
        # for data_entry in car_load_data:
        #     try:
        #         float(data_entry["state"])
        #     except ValueError:
        #         continue
        #     max_car_load = max(max_car_load, float(data_entry["state"]))
        # if 0 < max_car_load < 23:
        #     max_car_load = max_car_load * 1000
        #     car_load_unit_factor = 1000
        # logger.debug("[LOAD-IF] Max car load: %s W", round(max_car_load,0))
        # multiply every value with car_load_unit_factor before returning
        for data_entry in car_load_data:
            try:
                data_entry["state"] = float(
                    data_entry["state"]
                )  # * car_load_unit_factor
            except ValueError:
                continue
            except KeyError:
                continue
        # print(f'HA Car load data: {car_load_data}')
        return car_load_data

    def get_load_profile_for_day(self, start_time, end_time):
        """
        Retrieves the load profile for a specific day by fetching energy data from Home Assistant.

        Args:
            start_time (datetime): The start time for the load profile.
            end_time (datetime): The end time for the load profile.

        Returns:
            list: A list of energy consumption values for the specified day.
        """
        logger.debug(
            "[LOAD-IF] Creating day load profile from %s to %s", start_time, end_time
        )

        load_profile = []
        current_hour = start_time

        while current_hour < end_time:
            next_hour = current_hour + timedelta(hours=1)
            # logger.debug("[LOAD-IF] Fetching data for %s to %s", current_hour, next_hour)
            energy_data = self.fetch_historical_energy_data_from_homeassistant(
                self.load_sensor, current_hour, next_hour
            )
            car_load_data = self.__get_car_load_list_from_to(current_hour, next_hour)

            energy = abs(self.process_energy_data({"data": energy_data}))
            car_load_energy = abs(self.process_energy_data({"data": car_load_data}))
            # print(f'HA Car load data: {car_load_data} --- {energy}')
            car_load_energy = max(car_load_energy, 0)  # prevent negative values
            if car_load_energy <= energy:
                energy = energy - car_load_energy
            else:
                logger.error(
                    "[LOAD-IF] DATA ERROR load smaller than car load "+
                    "- Energy for %s: %5.1f Wh (car load: %5.1f Wh)",
                    current_hour,
                    round(energy, 1),
                    round(car_load_energy, 1),
                )
            if energy == 0:
                current_hour += timedelta(hours=1)
                continue

            energy_sum = energy

            load_profile.append(energy_sum)
            logger.debug(
                "[LOAD-IF] Energy for %s: %5.1f Wh (car load: %5.1f Wh)",
                current_hour,
                round(energy, 1),
                round(car_load_energy, 1),
            )
            current_hour += timedelta(hours=1)
        if not load_profile:
            logger.error(
                "[LOAD-IF] No load profile data available for the specified day - % s to % s",
                start_time,
                end_time,
            )
        return load_profile

    def create_load_profile_homeassistant_weekdays(self):
        """
        Creates a load profile for weekdays based on historical data from Home Assistant.
        This method calculates the average load profile for the same day of the week
        from one and two weeks prior, as well as the following day from one and two weeks prior.
        The resulting load profile is a combination of these averages.
        Args:
            tgt_duration (int): Target duration for the load profile
            (not currently used in the method).
        Returns:
            list: A list of 48 values representing the combined load profile for the specified days.
        """
        day_one_week_before = datetime.now(self.time_zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=7)
        day_two_week_before = datetime.now(self.time_zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=14)

        day_tomorrow_one_week_before = datetime.now(self.time_zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=6)
        day_tomorrow_two_week_before = datetime.now(self.time_zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=13)
        logger.info(
            "[LOAD-IF] creating load profile for weekdays %s (%s) and %s (%s)",
            day_one_week_before,
            day_one_week_before.strftime("%A"),
            day_tomorrow_one_week_before,
            day_tomorrow_one_week_before.strftime("%A"),
        )

        # get load profile for day one week before
        load_profile_one_week_before = self.get_load_profile_for_day(
            day_one_week_before, day_one_week_before + timedelta(days=1)
        )
        # get load profile for day two week before
        load_profile_two_week_before = self.get_load_profile_for_day(
            day_two_week_before, day_two_week_before + timedelta(days=1)
        )
        # get load profile for day tomorrow one week before
        load_profile_tomorrow_one_week_before = self.get_load_profile_for_day(
            day_tomorrow_one_week_before,
            day_tomorrow_one_week_before + timedelta(days=1),
        )
        # get load profile for day tomorrow two week before
        load_profile_tomorrow_two_week_before = self.get_load_profile_for_day(
            day_tomorrow_two_week_before,
            day_tomorrow_two_week_before + timedelta(days=1),
        )
        # combine load profiles with average of the connected days and
        # combine to a list with 48 values
        load_profile = []
        for i, value in enumerate(load_profile_one_week_before):
            if load_profile_two_week_before and len(load_profile_two_week_before) >= 24:
                load_profile.append((value + load_profile_two_week_before[i]) / 2)
            else:
                load_profile.append(value)
        for i, value in enumerate(load_profile_tomorrow_one_week_before):
            if (
                load_profile_tomorrow_two_week_before
                and len(load_profile_tomorrow_two_week_before) >= 24
            ):
                load_profile.append(
                    (value + load_profile_tomorrow_two_week_before[i]) / 2
                )
            else:
                load_profile.append(value)
        return load_profile

    def get_load_profile(self, tgt_duration, start_time=None):
        """
        Retrieves the load profile based on the configured source.

        Depending on the configuration, this function fetches the load profile from one of the
        following sources:
        - Default: Returns a predefined static load profile.
        - OpenHAB: Fetches the load profile from an OpenHAB instance.
        - Home Assistant: Fetches the load profile from a Home Assistant instance.

        Args:
            tgt_duration (int): The target duration in hours for which the load profile is needed.
            start_time (datetime, optional): The start time for fetching the load profile.
            Defaults to None.

        Returns:
            list: A list of energy consumption values for the specified duration.
        """
        if self.src == "default":
            logger.info("[LOAD-IF] Using load source default")
            default_profile = [
                200.0,  # 0:00 - 1:00 -- day 1
                200.0,  # 1:00 - 2:00
                200.0,  # 2:00 - 3:00
                200.0,  # 3:00 - 4:00
                200.0,  # 4:00 - 5:00
                300.0,  # 5:00 - 6:00
                350.0,  # 6:00 - 7:00
                400.0,  # 7:00 - 8:00
                350.0,  # 8:00 - 9:00
                300.0,  # 9:00 - 10:00
                300.0,  # 10:00 - 11:00
                550.0,  # 11:00 - 12:00
                450.0,  # 12:00 - 13:00
                400.0,  # 13:00 - 14:00
                300.0,  # 14:00 - 15:00
                300.0,  # 15:00 - 16:00
                400.0,  # 16:00 - 17:00
                450.0,  # 17:00 - 18:00
                500.0,  # 18:00 - 19:00
                500.0,  # 19:00 - 20:00
                500.0,  # 20:00 - 21:00
                400.0,  # 21:00 - 22:00
                300.0,  # 22:00 - 23:00
                200.0,  # 23:00 - 0:00
                200.0,  # 0:00 - 1:00 -- day 2
                200.0,  # 1:00 - 2:00
                200.0,  # 2:00 - 3:00
                200.0,  # 3:00 - 4:00
                200.0,  # 4:00 - 5:00
                300.0,  # 5:00 - 6:00
                350.0,  # 6:00 - 7:00
                400.0,  # 7:00 - 8:00
                350.0,  # 8:00 - 9:00
                300.0,  # 9:00 - 10:00
                300.0,  # 10:00 - 11:00
                550.0,  # 11:00 - 12:00
                450.0,  # 12:00 - 13:00
                400.0,  # 13:00 - 14:00
                300.0,  # 14:00 - 15:00
                300.0,  # 15:00 - 16:00
                400.0,  # 16:00 - 17:00
                450.0,  # 17:00 - 18:00
                500.0,  # 18:00 - 19:00
                500.0,  # 19:00 - 20:00
                500.0,  # 20:00 - 21:00
                400.0,  # 21:00 - 22:00
                300.0,  # 22:00 - 23:00
                200.0,  # 23:00 - 0:00
            ]
            return default_profile[:tgt_duration]
        if self.src == "openhab":
            # logger.info("[LOAD-IF] Using load source openhab")
            return self.create_load_profile_openhab_from_last_days(
                tgt_duration, start_time
            )
        if self.src == "homeassistant":
            # logger.info("[LOAD-IF] Using load source homeassistant")
            # return self.create_load_profile_homeassistant_from_last_days(tgt_duration, start_time)
            return self.create_load_profile_homeassistant_weekdays()
        logger.error(
            "[LOAD-IF] Load source '%s' currently not supported. Using default.",
            self.src,
        )
        return []
