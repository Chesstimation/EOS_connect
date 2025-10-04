"""
This module defines the BaseControl class, which manages the state and demands
of a control system. It includes methods for setting and retrieving charge demands,
discharge permissions, and overall system state.
"""

import logging
import time
import threading
from datetime import datetime

logger = logging.getLogger("__main__")
logger.info("[BASE-CTRL] loading module ")

MODE_CHARGE_FROM_GRID = 0
MODE_AVOID_DISCHARGE = 1
MODE_DISCHARGE_ALLOWED = 2
MODE_AVOID_DISCHARGE_EVCC_FAST = 3
MODE_DISCHARGE_ALLOWED_EVCC_PV = 4
MODE_DISCHARGE_ALLOWED_EVCC_MIN_PV = 5

state_mapping = {
    -2: "BACK TO AUTO",
    -1: "MODE Startup",
    0: "MODE CHARGE FROM GRID",
    1: "MODE AVOID DISCHARGE",
    2: "MODE DISCHARGE ALLOWED",
    3: "MODE AVOID DISCHARGE EVCC FAST",
    4: "MODE DISCHARGE ALLOWED EVCC PV",
    5: "MODE DISCHARGE ALLOWED EVCC MIN+PV",
}


class BaseControl:
    """
    BaseControl is a class that manages the state and demands of a control system.
    It keeps track of the current AC and DC charge demands, discharge allowed status,
    and the overall state of the system. The overall state can be one of three modes:
    MODE_CHARGE_FROM_GRID, MODE_AVOID_DISCHARGE, or MODE_DISCHARGE_ALLOWED.
    """

    def __init__(self, config, timezone):
        self.current_ac_charge_demand = 0
        self.last_ac_charge_demand = 0
        self.current_ac_charge_demand_no_override = 0
        self.current_dc_charge_demand = 0
        self.last_dc_charge_demand = 0
        self.current_dc_charge_demand_no_override = 0
        self.current_bat_charge_max = 0
        self.last_bat_charge_max = 0
        self.current_discharge_allowed = -1
        self.current_evcc_charging_state = False
        self.current_evcc_charging_mode = False
        # startup with None to force a writing to the inverter
        self.current_overall_state = -1
        self.override_active = False
        self.override_end_time = 0
        self.current_battery_soc = 0
        self.time_zone = timezone
        self.config = config
        self._state_change_timestamps = []
        self.update_interval = 15  # seconds
        self._update_thread = None
        self._stop_event = threading.Event()
        self.__start_update_service()

    def get_state_mapping(self, num_mode):
        """
        Returns the state mapping dictionary.
        """
        return state_mapping.get(num_mode, "unknown state")

    def was_overall_state_changed_recently(self, time_window_seconds):
        """
        Checks if the overall state was changed within the last `time_window_seconds`.
        """
        current_time = time.time()
        # Remove timestamps older than the time window
        self._state_change_timestamps = [
            ts
            for ts in self._state_change_timestamps
            if current_time - ts <= time_window_seconds
        ]
        return len(self._state_change_timestamps) > 0

    def get_current_ac_charge_demand(self):
        """
        Returns the current AC charge demand calculated based on maximum battery charge power.
        """
        return self.current_ac_charge_demand

    def get_current_dc_charge_demand(self):
        """
        Returns the current DC charge demand.
        """
        return self.current_dc_charge_demand

    def get_current_bat_charge_max(self):
        """
        Returns the current maximum battery charge power.
        """
        logger.debug(
            "[BASE-CTRL] get current battery charge max %s", self.current_bat_charge_max
        )
        return self.current_bat_charge_max

    def get_current_discharge_allowed(self):
        """
        Returns the current discharge demand.
        """
        return self.current_discharge_allowed

    def get_current_overall_state(self):
        """
        Returns the current overall state.
        """
        # Return the string representation of the state
        return state_mapping.get(self.current_overall_state, "unknown state")

    def get_current_overall_state_number(self):
        """
        Returns the current overall state as a number.
        """
        return self.current_overall_state

    def get_current_battery_soc(self):
        """
        Returns the current battery state of charge (SOC).
        """
        return self.current_battery_soc

    def get_current_evcc_charging_state(self):
        """
        Returns the current EVCC charging state.
        """
        return self.current_evcc_charging_state

    def get_current_evcc_charging_mode(self):
        """
        Returns the current EVCC charging mode.
        """
        return self.current_evcc_charging_mode

    def get_override_active_and_endtime(self):
        """
        Returns whether the override is active.
        """
        return self.override_active, int(self.override_end_time)

    def set_current_ac_charge_demand(self, value_relative):
        """
        Sets the current AC charge demand.
        """
        current_hour = datetime.now(self.time_zone).hour
        current_charge_demand = (
            value_relative * self.config["battery"]["max_charge_power_w"]
        )
        # store the current charge demand without override
        self.current_ac_charge_demand_no_override = current_charge_demand
        if not self.override_active:
            self.current_ac_charge_demand = current_charge_demand
            logger.debug(
                "[BASE-CTRL] set AC charge demand for current hour %s:00 -> %s Wh -"
                + " based on max charge power %s W",
                current_hour,
                self.current_ac_charge_demand,
                self.config["battery"]["max_charge_power_w"],
            )
        else:
            logger.debug(
                "[BASE-CTRL] OVERRIDE AC charge demand for current hour %s:00 -> %s Wh -"
                + " based on max charge power %s W",
                current_hour,
                self.current_ac_charge_demand,
                self.config["battery"]["max_charge_power_w"],
            )
        self.__set_current_overall_state()

    def set_current_dc_charge_demand(self, value_relative):
        """
        Sets the current DC charge demand.
        """
        current_hour = datetime.now(self.time_zone).hour
        current_charge_demand = (
            value_relative * self.config["battery"]["max_charge_power_w"]
        )
        # store the current charge demand without override
        self.current_dc_charge_demand_no_override = current_charge_demand
        if not self.override_active:
            self.current_dc_charge_demand = current_charge_demand
            logger.debug(
                "[BASE-CTRL] set DC charge demand for current hour %s:00 -> %s Wh -"
                + " based on max charge power %s W",
                current_hour,
                self.current_dc_charge_demand,
                self.config["battery"]["max_charge_power_w"],
            )
        else:
            logger.debug(
                "[BASE-CTRL] OVERRIDE DC charge demand for current hour %s:00 -> %s Wh -"
                + " based on max charge power %s W",
                current_hour,
                self.current_dc_charge_demand,
                self.config["battery"]["max_charge_power_w"],
            )
        self.__set_current_overall_state()

    def set_current_bat_charge_max(self, value_max):
        """
        Sets the current maximum battery charge power.
        """
        # store the current charge demand without override
        self.current_bat_charge_max = value_max
        logger.debug(
            "[BASE-CTRL] set current battery charge max to %s",
            self.current_bat_charge_max,
        )
        self.__set_current_overall_state()

    def set_current_discharge_allowed(self, value):
        """
        Sets the current discharge demand.
        """
        current_hour = datetime.now(self.time_zone).hour
        self.current_discharge_allowed = value
        logger.debug(
            "[BASE-CTRL] set Discharge allowed for current hour %s:00 %s",
            current_hour,
            self.current_discharge_allowed,
        )
        self.__set_current_overall_state()

    def set_current_evcc_charging_state(self, value):
        """
        Sets the current EVCC charging state.
        """
        self.current_evcc_charging_state = value
        # logger.debug("[BASE-CTRL] set current EVCC charging state to %s", value)
        self.__set_current_overall_state()

    def set_current_evcc_charging_mode(self, value):
        """
        Sets the current EVCC charging mode.
        """
        self.current_evcc_charging_mode = value
        # logger.debug("[BASE-CTRL] set current EVCC charging mode to %s", value)
        self.__set_current_overall_state()

    def __set_current_overall_state(self):
        """
        Sets the current overall state and logs the timestamp if it changes.
        """
        if self.override_active:
            # check if the override end time is reached
            if time.time() > self.override_end_time:
                logger.info("[BASE-CTRL] OVERRIDE end time reached, clearing override")
                self.clear_mode_override()
                return
            return
        if self.current_ac_charge_demand > 0:
            new_state = MODE_CHARGE_FROM_GRID
        elif self.current_discharge_allowed > 0:
            new_state = MODE_DISCHARGE_ALLOWED
        elif self.current_discharge_allowed == 0:
            new_state = MODE_AVOID_DISCHARGE
        else:
            new_state = -1
        # check if the grid charge demand has changed
        grid_charge_value_changed = (
            self.current_ac_charge_demand != self.last_ac_charge_demand
        )
        dc_charge_value_changed = (
            self.current_dc_charge_demand != self.last_dc_charge_demand
        )
        bat_charge_max_value_changed = (
            self.current_bat_charge_max != self.last_bat_charge_max
        )

        # override overall state if EVCC charging state is active and
        # in mode fast charge and discharge is allowed
        if (
            # new_state == MODE_DISCHARGE_ALLOWED
            # and 
            self.current_evcc_charging_state
            and self.current_evcc_charging_mode in ("now", "pv+now", "minpv+now")
        ):
            new_state = MODE_AVOID_DISCHARGE_EVCC_FAST
            logger.info(
                "[BASE-CTRL] EVCC charging state is active,"
                + " setting overall state to MODE_AVOID_DISCHARGE_EVCC_FAST"
            )

        # override overall state if EVCC charging state is active and
        # in mode pv charge and discharge is allowed
        if (
            # new_state == MODE_DISCHARGE_ALLOWED
            # and 
            self.current_evcc_charging_state
            and self.current_evcc_charging_mode == "pv"
        ):
            new_state = MODE_DISCHARGE_ALLOWED_EVCC_PV
            logger.info(
                "[BASE-CTRL] EVCC charging state is active,"
                + " setting overall state to MODE_DISCHARGE_ALLOWED_EVCC_PV"
            )

        # override overall state if EVCC charging state is active and
        # in mode pv charge and discharge is allowed
        if (
            # new_state == MODE_DISCHARGE_ALLOWED
            # and 
            self.current_evcc_charging_state
            and self.current_evcc_charging_mode == "minpv"
        ):
            new_state = MODE_DISCHARGE_ALLOWED_EVCC_MIN_PV
            logger.info(
                "[BASE-CTRL] EVCC charging state is active,"
                + " setting overall state to MODE_DISCHARGE_ALLOWED_EVCC_MIN_PV"
            )

        if (
            new_state != self.current_overall_state
            or grid_charge_value_changed
            or dc_charge_value_changed
            or bat_charge_max_value_changed
        ):
            self._state_change_timestamps.append(time.time())
            # Limit the size of the state change timestamps to avoid memory overrun
            max_timestamps = 1000  # Adjust this value as needed
            if len(self._state_change_timestamps) > max_timestamps:
                self._state_change_timestamps.pop(0)
            if grid_charge_value_changed:
                logger.info(
                    "[BASE-CTRL] AC charge demand changed to %s W",
                    self.current_ac_charge_demand,
                )
            elif dc_charge_value_changed:
                logger.info(
                    "[BASE-CTRL] DC charge demand changed to %s W",
                    self.current_dc_charge_demand,
                )
            elif bat_charge_max_value_changed:
                logger.info(
                    "[BASE-CTRL] Battery charge max changed to %s W",
                    self.current_bat_charge_max,
                )
            else:
                logger.debug(
                    "[BASE-CTRL] overall state changed to %s",
                    state_mapping.get(new_state, "unknown state"),
                )
        # store the last AC charge demand for comparison
        self.last_ac_charge_demand = self.current_ac_charge_demand
        # store the last DC charge demand for comparison
        self.last_dc_charge_demand = self.current_dc_charge_demand
        # store the last battery charge max for comparison
        self.last_bat_charge_max = self.current_bat_charge_max

        self.current_overall_state = new_state

    def set_current_battery_soc(self, value):
        """
        Sets the current battery state of charge (SOC).
        """
        self.current_battery_soc = value
        # logger.debug("[BASE-CTRL] set current battery SOC to %s", value)

    def set_mode_override(self, mode, duration, charge_rate):
        """
        Sets the current overall state to a specific mode.
        """
        # switch back to EOS given demands
        if mode == -2:
            self.clear_mode_override()
            return
        # convert to seconds
        duration_seconds = 0
        if 0 <= duration <= 12 * 60:
            duration_seconds = duration * 60
            # duration_seconds = duration * 60 / 10
        else:
            logger.error("[BASE-CTRL] OVERRIDE invalid duration %s", duration)
            return

        if mode >= 0 or mode <= 2:
            self.current_overall_state = mode
            self.override_active = True
            self.override_end_time = (time.time() + duration_seconds) // 60 * 60
            self._state_change_timestamps.append(time.time())
            logger.info(
                "[BASE-CTRL] OVERRIDE set overall state to %s with endtime %s",
                state_mapping[mode],
                datetime.fromtimestamp(
                    self.override_end_time, self.time_zone
                ).isoformat(),
            )
            if charge_rate > 0 and mode == MODE_CHARGE_FROM_GRID:
                self.current_ac_charge_demand = charge_rate * 1000
                logger.info(
                    "[BASE-CTRL] OVERRIDE set AC charge demand to %s",
                    self.current_ac_charge_demand,
                )
            if charge_rate > 0 and mode == MODE_DISCHARGE_ALLOWED:
                self.current_dc_charge_demand = charge_rate * 1000
                logger.info(
                    "[BASE-CTRL] OVERRIDE set DC charge demand to %s",
                    self.current_dc_charge_demand,
                )
        else:
            logger.error("[BASE-CTRL] OVERRIDE invalid mode %s", mode)

    def clear_mode_override(self):
        """
        Clears the current mode overrideand trigger a state change.
        """
        self.override_active = False
        self.override_end_time = 0
        self.current_ac_charge_demand = self.current_ac_charge_demand_no_override
        self.current_dc_charge_demand = self.current_dc_charge_demand_no_override
        self.__set_current_overall_state()
        # reset the override end time to 0
        logger.info("[BASE-CTRL] cleared mode override")

    def __start_update_service(self):
        """
        Starts the background thread to periodically update the charging state.
        """
        if self._update_thread is None or not self._update_thread.is_alive():
            self._stop_event.clear()
            self._update_thread = threading.Thread(
                target=self.__update_base_control_loop, daemon=True
            )
            self._update_thread.start()
            logger.info("[BASE-CTRL] Update service started.")

    def shutdown(self):
        """
        Stops the background thread and shuts down the update service.
        """
        if self._update_thread and self._update_thread.is_alive():
            self._stop_event.set()
            self._update_thread.join()
            logger.info("[BASE-CTRL] Update service stopped.")

    def __update_base_control_loop(self):
        """
        The loop that runs in the background thread to update the charging state.
        """
        while not self._stop_event.is_set():
            self.__set_current_overall_state()

            sleep_interval = self.update_interval
            while sleep_interval > 0:
                if self._stop_event.is_set():
                    return  # Exit immediately if stop event is set
                time.sleep(min(1, sleep_interval))  # Sleep in 1-second chunks
                sleep_interval -= 1

        self.__start_update_service()
