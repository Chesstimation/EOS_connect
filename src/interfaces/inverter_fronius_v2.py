"""
Fronius GEN24 Inverter Interface V2 - Updated HTTP Authentication

Based on v1 but with updated authentication for firmware 1.38.6-1+
that fixes the SHA256 authentication issues discovered in the forum.

Key changes from v1:
- Updated authentication handling for firmware 1.38.6-1+
- Support for both MD5 (old passwords) and SHA256 (new passwords)
- Fixed "SHA256" vs "SHA-256" algorithm header bug
- Improved battery control reliability

Forum reference: https://www.photovoltaikforum.com/thread/251773-gen24-firmware-1-38-6-1/
GitHub reference: https://github.com/wiggal/GEN24_Ladesteuerung/blob/main/FUNCTIONS/httprequest.py
"""

import time
import os
import logging
import json
import hashlib
import re
import requests

logger = logging.getLogger("__main__").getChild("FroniusV2")
logger.setLevel(logging.INFO)
logger.info("[InverterV2] Loading Fronius GEN24 V2 with updated authentication")


def hash_utf8_md5(x):
    """Hash a string or bytes object with MD5 (legacy support)."""
    if isinstance(x, str):
        x = x.encode("utf-8")
    return hashlib.md5(x).hexdigest()


def hash_utf8_sha256(x):
    """Hash a string or bytes object with SHA256 (new firmware)."""
    if isinstance(x, str):
        x = x.encode("utf-8")
    return hashlib.sha256(x).hexdigest()


def strip_dict(original):
    """Strip all keys starting with '_' from a dictionary."""
    if not isinstance(original, dict):
        return original
    stripped_copy = {}
    for key in original.keys():
        if not key.startswith("_"):
            stripped_copy[key] = original[key]
    return stripped_copy


class FroniusWRV2:
    """
    Fronius GEN24 V2 Interface with updated HTTP authentication.

    Improvements over V1:
    - Fixed SHA256 authentication for firmware 1.38.6-1+
    - Automatic fallback from SHA256 to MD5 for old passwords
    - Better error handling and retry logic
    - Support for both old and new firmware versions
    """

    def __init__(self, config):
        """Initialize the Fronius V2 interface with updated authentication."""

        # Configuration
        self.address = config.get("address", "192.168.1.102")
        self.user = config.get("user", "customer").lower()  # Always lowercase
        self.password = config.get("password", "your_password")

        # Battery limits
        self.max_pv_charge_rate = config.get("max_pv_charge_rate", 15000)
        self.max_grid_charge_rate = config.get("max_grid_charge_rate", 10000)
        self.min_soc = config.get("min_soc", 15)
        self.max_soc = config.get("max_soc", 100)

        # HTTP session setup
        self.session = requests.Session()
        self.session.timeout = 10

        # Authentication state
        self.nonce = None
        self.is_authenticated = False
        self.algorithm = "SHA256"  # Default to new algorithm, fallback to MD5

        # API paths (auto-detected based on firmware)
        self.api_base = None  # Will be set to "/" or "/api/"

        # Battery backup config filename
        self.backup_filename = os.path.join(
            os.path.dirname(__file__), "..", "..", "battery_config_v2.json"
        )

        # Initialize inverter monitoring data storage
        self.inverter_current_data = {
            "DEVICE_TEMPERATURE_AMBIENTEMEAN_F32": 0.0,
            "MODULE_TEMPERATURE_MEAN_01_F32": 0.0,
            "MODULE_TEMPERATURE_MEAN_03_F32": 0.0,
            "MODULE_TEMPERATURE_MEAN_04_F32": 0.0,
            "FANCONTROL_PERCENT_01_F32": 0.0,
            "FANCONTROL_PERCENT_02_F32": 0.0,
        }

        logger.info(
            f"[InverterV2] Initialized for {self.address} with user '{self.user}'"
        )

        # Test connection and detect firmware
        self._detect_api_version()
        
        # Simple connection verification (non-intrusive)
        logger.info("[InverterV2] Interface initialized and ready")

    def _detect_api_version(self):
        """Detect API version and set correct base path."""
        try:
            # Test new API path first (firmware 1.36.5-1+)
            test_url = f"http://{self.address}/api/config/timeofuse"
            response = self.session.get(test_url, timeout=5)

            if response.status_code == 401:  # Needs auth but endpoint exists
                self.api_base = "/api/"
                logger.info(
                    "[InverterV2] Detected new firmware (1.36.5-1+) - using /api/ base"
                )
                return
        except (requests.RequestException, ValueError):
            pass

        try:
            # Test old API path
            test_url = f"http://{self.address}/config/timeofuse"
            response = self.session.get(test_url, timeout=5)

            if response.status_code == 401:  # Needs auth but endpoint exists
                self.api_base = "/"
                logger.info("[InverterV2] Detected old firmware - using / base")
                return
        except (requests.RequestException, ValueError):
            pass

        # Default fallback
        self.api_base = "/api/"
        logger.warning(
            "[InverterV2] Could not detect firmware version, defaulting to /api/"
        )

    def _get_nonce(self, response):
        """Extract nonce from authentication challenge response."""
        try:
            # Handle different header capitalizations (firmware bug)
            auth_header = None
            for header_name in [
                "X-WWW-Authenticate",
                "X-Www-Authenticate",
                "WWW-Authenticate",
            ]:
                if header_name in response.headers:
                    auth_header = response.headers[header_name]
                    break

            if not auth_header:
                logger.error("[InverterV2] No authentication header found")
                return None

            # Parse authentication header - FIXED parsing to preserve spaces
            auth_dict = {}

            # Remove 'Digest ' prefix first
            auth_content = auth_header.replace("Digest ", "", 1)

            # Split by comma but preserve quoted values
            pattern = r'(\w+)=(?:"([^"]*)"|([^,]*))'
            matches = re.findall(pattern, auth_content)

            for match in matches:
                key = match[0]
                value = match[1] if match[1] else match[2]  # Prefer quoted value
                auth_dict[key] = value

            # Extract algorithm and nonce
            self.algorithm = auth_dict.get("algorithm", "MD5")
            nonce = auth_dict.get("nonce")

            # Fix firmware bug: "SHA256" should be "SHA-256" but we'll handle both
            if self.algorithm == "SHA256":
                logger.info("[InverterV2] Firmware reports SHA256, treating as SHA-256")

            logger.debug(
                f"[InverterV2] Extracted nonce with algorithm: {self.algorithm}"
            )
            logger.debug(f"[InverterV2] Realm: '{auth_dict.get('realm', 'unknown')}'")
            return nonce

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Failed to extract nonce: {e}")
            return None

    def _create_auth_header(
        self, method, path, nonce, cnonce="7d5190133564493d953a7193d9d120a2"
    ):
        """Create digest authentication header with proper algorithm support."""
        try:
            realm = "Webinterface area"  # FIXED: Include the space
            nc = "00000001"
            qop = "auth"

            # Create digest auth components
            auth_a1 = f"{self.user}:{realm}:{self.password}"
            auth_a2 = f"{method}:{path}"

            # Choose hash function based on algorithm - FIXED logic
            if self.algorithm == "SHA256":  # Firmware reports SHA256
                hash_func = hash_utf8_sha256
                algorithm_header = "SHA256"  # Send what firmware expects
            elif self.algorithm == "SHA-256":  # Standard SHA-256
                hash_func = hash_utf8_sha256
                algorithm_header = "SHA-256"
            else:
                hash_func = hash_utf8_md5
                algorithm_header = "MD5"

            # Calculate hashes
            hash_a1 = hash_func(auth_a1)
            hash_a2 = hash_func(auth_a2)

            # Create response hash
            response_data = f"{hash_a1}:{nonce}:{nc}:{cnonce}:{qop}:{hash_a2}"
            response_hash = hash_func(response_data)

            # Build auth header
            auth_header = (
                f'Digest username="{self.user}", '
                f'realm="{realm}", '
                f'nonce="{nonce}", '
                f'uri="{path}", '
                f'algorithm="{algorithm_header}", '
                f"qop={qop}, "
                f"nc={nc}, "
                f'cnonce="{cnonce}", '
                f'response="{response_hash}"'
            )

            logger.debug(f"[InverterV2] Created auth header with {algorithm_header}")
            logger.debug(f"[InverterV2] A1: {auth_a1}")
            logger.debug(f"[InverterV2] HA1: {hash_a1}")
            return auth_header

        except (ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Failed to create auth header: {e}")
            return None

    def _make_authenticated_request(self, method, endpoint, data=None, max_retries=3):
        """Make an authenticated HTTP request with automatic retry and algorithm fallback."""

        for attempt in range(max_retries):
            try:
                url = f"http://{self.address}{self.api_base.rstrip('/')}{endpoint}"
                headers = {"Content-Type": "application/json"}

                # First attempt without auth to get nonce
                response = self.session.request(method, url, headers=headers, json=data)

                if response.status_code == 200:
                    return response

                if response.status_code == 401:
                    # Extract nonce and create auth header
                    nonce = self._get_nonce(response)
                    if not nonce:
                        logger.error(
                            f"[InverterV2] Could not get nonce on attempt {attempt + 1}"
                        )
                        continue

                    # Create auth header for the full endpoint path
                    full_path = f"{self.api_base.rstrip('/')}{endpoint}"
                    auth_header = self._create_auth_header(method, full_path, nonce)
                    if not auth_header:
                        logger.error(
                            f"[InverterV2] Could not create auth header on attempt {attempt + 1}"
                        )
                        continue

                    headers["Authorization"] = auth_header

                    # Make authenticated request
                    response = self.session.request(
                        method, url, headers=headers, json=data
                    )

                    if response.status_code == 200:
                        logger.debug(
                            f"[InverterV2] Authentication successful with {self.algorithm}"
                        )
                        return response
                    if response.status_code == 401 and self.algorithm == "SHA-256":
                        # Fallback to MD5 for old passwords
                        logger.info("[InverterV2] SHA256 failed, trying MD5 fallback")
                        self.algorithm = "MD5"
                        continue

                    if response.status_code == 401:
                        logger.error(
                            f"[InverterV2] Authentication failed: {response.status_code}"
                            " - Invalid credentials"
                        )
                        logger.error(
                            f"[InverterV2] TROUBLESHOOTING: If you recently updated your inverter"
                            f" firmware (to 1.38.x-y), you may need to reset your password in"
                            f" the WebUI (http://{self.address}/). New firmware versions require"
                            f" password reset after updates."
                        )
                        logger.error(
                            "[InverterV2] Go to WebUI -> Settings -> User Management -> "
                            "Change password for 'customer' user, then update your config."
                        )
                    else:
                        logger.error(
                            f"[InverterV2] Authentication failed: {response.status_code}"
                        )

                else:
                    # For non-auth errors, return the response so caller can handle it
                    if response.status_code == 404:
                        logger.debug(f"[InverterV2] Endpoint not found: {endpoint}")
                        return response  # Let caller handle 404
                    else:
                        logger.error(f"[InverterV2] HTTP error: {response.status_code}")

            except (requests.RequestException, ValueError, KeyError) as e:
                logger.error(
                    f"[InverterV2] Request failed on attempt {attempt + 1}: {e}"
                )

            if attempt < max_retries - 1:
                time.sleep(1)

        logger.error(f"[InverterV2] All {max_retries} attempts failed for {endpoint}")
        return None

    # Battery mode control methods (same interface as evcc)

    def set_battery_mode(self, mode):
        """
        Set battery mode (evcc-compatible).

        Args:
            mode (str): "normal", "hold", "charge"

        Returns:
            bool: True if successful
        """
        logger.info(f"[InverterV2] Setting battery mode: {mode}")

        if mode == "normal":
            return self._set_mode_normal()
        if mode == "hold":
            return self._set_mode_hold()
        if mode == "charge":
            return self._set_mode_charge()
        logger.error(f"[InverterV2] Invalid mode: {mode}")
        return False

    def _set_mode_normal(self):
        """Set normal battery operation (allow discharge)."""
        logger.info("[InverterV2] Setting normal mode")

        # Normal mode = allow charging from PV only, allow discharging
        timeofuse_list = []
        if self.max_pv_charge_rate > 0:
            timeofuse_list = [
                {
                    "Active": True,
                    "Power": int(self.max_pv_charge_rate),
                    "ScheduleType": "CHARGE_MAX",
                    "TimeTable": {"Start": "00:00", "End": "23:59"},
                    "Weekdays": {
                        "Mon": True,
                        "Tue": True,
                        "Wed": True,
                        "Thu": True,
                        "Fri": True,
                        "Sat": True,
                        "Sun": True,
                    },
                }
            ]

        return self._set_time_of_use(timeofuse_list)

    def _set_mode_hold(self):
        """Set hold mode (avoid discharge)."""
        logger.info("[InverterV2] Setting hold mode")

        # Hold mode = disable discharge (0W), allow PV charging only
        timeofuse_list = [
            {
                "Active": True,
                "Power": int(0),
                "ScheduleType": "DISCHARGE_MAX",
                "TimeTable": {"Start": "00:00", "End": "23:59"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                    "Sun": True,
                },
            }
        ]

        # Also allow PV charging if configured
        if self.max_pv_charge_rate > 0:
            timeofuse_list.append(
                {
                    "Active": True,
                    "Power": int(self.max_pv_charge_rate),
                    "ScheduleType": "CHARGE_MAX",
                    "TimeTable": {"Start": "00:00", "End": "23:59"},
                    "Weekdays": {
                        "Mon": True,
                        "Tue": True,
                        "Wed": True,
                        "Thu": True,
                        "Fri": True,
                        "Sat": True,
                        "Sun": True,
                    },
                }
            )

        return self._set_time_of_use(timeofuse_list)

    def _set_mode_charge(self):
        """Set charge mode (force charge from grid)."""
        logger.info("[InverterV2] Setting charge mode")

        # Force charge mode = minimum charge from grid
        charge_power = min(self.max_grid_charge_rate, 10000)  # Limit to 10kW

        timeofuse_list = [
            {
                "Active": True,
                "Power": int(charge_power),
                "ScheduleType": "CHARGE_MIN",
                "TimeTable": {"Start": "00:00", "End": "23:59"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                    "Sun": True,
                },
            }
        ]

        return self._set_time_of_use(timeofuse_list)

    def _set_time_of_use(self, timeofuse_list):
        """Set time of use configuration (core battery control method)."""
        try:
            config = {"timeofuse": timeofuse_list}
            endpoint = "/config/timeofuse"

            logger.debug(f"[InverterV2] Setting timeofuse config: {config}")

            response = self._make_authenticated_request("POST", endpoint, data=config)

            if response and response.status_code == 200:
                try:
                    response_dict = response.json()
                    expected_write_successes = ["timeofuse"]

                    for expected_write_success in expected_write_successes:
                        if expected_write_success not in response_dict.get(
                            "writeSuccess", []
                        ):
                            logger.error(
                                f"[InverterV2] Failed to set {expected_write_success}"
                            )
                            return False

                    logger.info(
                        "[InverterV2] Time of use configuration successfully updated"
                    )
                    return True

                except (ValueError, KeyError, TypeError) as e:
                    logger.error(f"[InverterV2] Failed to parse response: {e}")
                    return False
            else:
                logger.error(
                    (
                        "[InverterV2] Failed to set time of use: "
                        f"{response.status_code if response else 'No response'}"
                    )
                )
                return False

        except (requests.RequestException, ValueError) as e:
            logger.error(f"[InverterV2] Error setting time of use: {e}")
            return False

    # EOS Connect compatibility layer

    def set_mode_force_charge(self, charge_power_w):
        """EOS Connect compatibility: Force charge mode with specific power."""
        logger.info(f"[InverterV2] Setting force charge mode with {charge_power_w}W")

        # Validate power limit
        max_power = min(self.max_grid_charge_rate, 10000)
        charge_power = min(int(charge_power_w), max_power)

        if charge_power != charge_power_w:
            logger.warning(
                f"[InverterV2] Charge power limited from {charge_power_w}W to {charge_power}W"
            )

        # Create timeofuse configuration for specific charge power
        timeofuse_list = [
            {
                "Active": True,
                "Power": charge_power,
                "ScheduleType": "CHARGE_MIN",
                "TimeTable": {"Start": "00:00", "End": "23:59"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                    "Sun": True,
                },
            }
        ]

        return self._set_time_of_use(timeofuse_list)

    def set_mode_avoid_discharge(self):
        """EOS Connect compatibility: Avoid discharge mode."""
        return self.set_battery_mode("hold")

    def set_mode_allow_discharge(self):
        """EOS Connect compatibility: Allow discharge mode."""
        return self.set_battery_mode("normal")

    def get_battery_info(self):
        """Get battery status information."""
        try:
            battery_info = {
                "soc_percentage": 0,
                "capacity_wh": 0,
                "charge_rate_w": 0,
                "discharge_rate_w": 0,
                "mode": self.get_battery_mode(),
                "status": "v2_ready",
                "authentication": self.algorithm,
                "api_base": self.api_base,
                "available_modes": ["normal", "hold", "charge"],
            }

            # Try to get current timeofuse configuration
            try:
                current_config = self._get_current_timeofuse()
                if current_config:
                    battery_info["current_timeofuse"] = current_config
                    battery_info["status"] = "v2_connected"

            except (requests.RequestException, ValueError, KeyError) as e:
                logger.debug(f"[InverterV2] Could not get timeofuse config: {e}")

            # Try to get storage realtime data
            try:
                storage_data = self._get_storage_realtime_data()
                if storage_data:
                    battery_info.update(storage_data)
                    battery_info["status"] = "v2_full_data"

            except (requests.RequestException, ValueError, KeyError) as e:
                logger.debug(f"[InverterV2] Could not get storage data: {e}")

            return battery_info

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Failed to get battery info: {e}")
            return {"status": "error", "mode": "unknown"}

    def get_battery_mode(self):
        """Get current battery mode by analyzing timeofuse configuration."""
        try:
            current_config = self._get_current_timeofuse()
            if not current_config:
                return "unknown"

            # Analyze the configuration to determine mode
            has_charge_min = False
            has_discharge_max_zero = False
            has_charge_max = False

            for rule in current_config:
                if not rule.get("Active", False):
                    continue

                schedule_type = rule.get("ScheduleType", "")
                power = rule.get("Power", 0)

                if schedule_type == "CHARGE_MIN":
                    has_charge_min = True
                elif schedule_type == "DISCHARGE_MAX" and power == 0:
                    has_discharge_max_zero = True
                elif schedule_type == "CHARGE_MAX":
                    has_charge_max = True

            # Determine mode based on active rules
            if has_charge_min:
                return "charge"  # Force charge from grid
            if has_discharge_max_zero:
                return "hold"  # Prevent discharge
            if has_charge_max or len(current_config) == 0:
                return "normal"  # Normal operation or no rules
            return "unknown"

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Failed to get battery mode: {e}")
            return "unknown"

    def _get_current_timeofuse(self):
        """Get current time of use configuration."""
        try:
            endpoint = "/config/timeofuse"
            response = self._make_authenticated_request("GET", endpoint)

            if response and response.status_code == 200:
                result = response.json()
                return result.get("timeofuse", [])
            status_code = response.status_code if response else "No response"
            logger.error(f"[InverterV2] Failed to get timeofuse: {status_code}")
            return None

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Error getting timeofuse: {e}")
            return None

    def _get_storage_realtime_data(self):
        """Get storage realtime data from the inverter."""
        try:
            # Use the old API endpoint for storage data (no auth required)
            url = f"http://{self.address}/solar_api/v1/GetStorageRealtimeData.cgi"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                result = response.json()
                body = result.get("Body", {})
                data = body.get("Data", {})

                storage_info = {}

                # Parse storage data if available
                for _, device_data in data.items():
                    controller = device_data.get("Controller", {})

                    # Battery capacity
                    if "DesignedCapacity" in controller:
                        storage_info["capacity_wh"] = controller["DesignedCapacity"]

                    # State of charge
                    if "StateOfCharge_Relative" in controller:
                        storage_info["soc_percentage"] = controller[
                            "StateOfCharge_Relative"
                        ]

                    # Power flow (positive = charging, negative = discharging)
                    if "PowerReal_P" in controller:
                        power = controller["PowerReal_P"]
                        if power >= 0:
                            storage_info["charge_rate_w"] = power
                            storage_info["discharge_rate_w"] = 0
                        else:
                            storage_info["charge_rate_w"] = 0
                            storage_info["discharge_rate_w"] = abs(power)

                    break  # Use first device

                return storage_info
            logger.debug(
                f"[InverterV2] Storage data request failed: {response.status_code}"
            )
            return None

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.debug(f"[InverterV2] Error getting storage data: {e}")
            return None

    def backup_current_config(self):
        """Backup current timeofuse configuration for restoration."""
        try:
            current_config = self._get_current_timeofuse()
            if current_config:
                with open(self.backup_filename, "w", encoding="utf-8") as f:
                    json.dump(current_config, f, indent=2)
                logger.info(
                    f"[InverterV2] Configuration backed up to {self.backup_filename}"
                )
                return True
            logger.warning("[InverterV2] No configuration to backup")
            return False

        except (OSError, ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Failed to backup configuration: {e}")
            return False

    def restore_backup_config(self):
        """Restore previously backed up timeofuse configuration."""
        try:
            if not os.path.exists(self.backup_filename):
                logger.warning(
                    f"[InverterV2] No backup file found: {self.backup_filename}"
                )
                return False

            with open(self.backup_filename, "r", encoding="utf-8") as f:
                backup_config = json.load(f)

            success = self._set_time_of_use(backup_config)

            if success:
                # Remove backup file after successful restoration
                try:
                    os.remove(self.backup_filename)
                    logger.info("[InverterV2] Backup restored and backup file removed")
                except OSError as e:
                    logger.warning(f"[InverterV2] Could not remove backup file: {e}")

            return success

        except (OSError, ValueError, KeyError) as e:
            logger.error(f"[InverterV2] Failed to restore backup: {e}")
            return False

    def fetch_inverter_data(self):
        """Get inverter data for monitoring (temperatures, fan control, etc.)."""
        try:
            # Get inverter component data (try different endpoint paths for different firmware)
            response = self._make_authenticated_request(
                "GET", "/components/inverter/readable"
            )

            if not response:
                logger.debug("[InverterV2] Inverter monitoring endpoint not available")
                return None
                
            if response.status_code == 404:
                logger.debug("[InverterV2] Inverter monitoring not supported by this firmware")
                return None
                
            if response.status_code != 200:
                logger.debug(f"[InverterV2] Inverter monitoring returned {response.status_code}")
                return None

            data = response.json()
            channels = data.get("Body", {}).get("Data", {}).get("0", {}).get("channels", {})

            # Store inverter monitoring data compatible with V1 format
            self.inverter_current_data = {
                "DEVICE_TEMPERATURE_AMBIENTEMEAN_F32": round(
                    channels.get("DEVICE_TEMPERATURE_AMBIENTMEAN_01_F32", 0), 2
                ),
                "MODULE_TEMPERATURE_MEAN_01_F32": round(
                    channels.get("MODULE_TEMPERATURE_MEAN_01_F32", 0), 2
                ),
                "MODULE_TEMPERATURE_MEAN_03_F32": round(
                    channels.get("MODULE_TEMPERATURE_MEAN_03_F32", 0), 2
                ),
                "MODULE_TEMPERATURE_MEAN_04_F32": round(
                    channels.get("MODULE_TEMPERATURE_MEAN_04_F32", 0), 2
                ),
                "FANCONTROL_PERCENT_01_F32": round(
                    channels.get("FANCONTROL_PERCENT_01_F32", 0), 2
                ),
                "FANCONTROL_PERCENT_02_F32": round(
                    channels.get("FANCONTROL_PERCENT_02_F32", 0), 2
                ),
            }

            logger.debug(f"[InverterV2] Inverter data: {self.inverter_current_data}")
            return self.inverter_current_data

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.debug(f"[InverterV2] Inverter monitoring unavailable: {e}")
            # Initialize with zeros if fetch fails
            self.inverter_current_data = {
                "DEVICE_TEMPERATURE_AMBIENTEMEAN_F32": 0.0,
                "MODULE_TEMPERATURE_MEAN_01_F32": 0.0,
                "MODULE_TEMPERATURE_MEAN_03_F32": 0.0,
                "MODULE_TEMPERATURE_MEAN_04_F32": 0.0,
                "FANCONTROL_PERCENT_01_F32": 0.0,
                "FANCONTROL_PERCENT_02_F32": 0.0,
            }
            return None

    def get_inverter_current_data(self):
        """Get the current inverter monitoring data."""
        if not hasattr(self, 'inverter_current_data'):
            self.fetch_inverter_data()
        return getattr(self, 'inverter_current_data', {})

    def api_set_max_pv_charge_rate(self, max_pv_charge_rate: int):
        """Set the maximum power in W that can be used to charge the battery from PV.
        
        Args:
            max_pv_charge_rate: Maximum PV charge power in watts
        """
        if max_pv_charge_rate < 0:
            logger.warning(
                f"[InverterV2] API: Invalid max_pv_charge_rate {max_pv_charge_rate}W"
            )
            return

        logger.info(
            f"[InverterV2] API: Setting max_pv_charge_rate: {max_pv_charge_rate}W"
        )
        self.max_pv_charge_rate = max_pv_charge_rate

    def api_set_max_grid_charge_rate(self, max_grid_charge_rate: int):
        """Set the maximum power in W that can be used to charge the battery from grid.
        
        Args:
            max_grid_charge_rate: Maximum grid charge power in watts
        """
        if max_grid_charge_rate < 0:
            logger.warning(
                f"[InverterV2] API: Invalid max_grid_charge_rate {max_grid_charge_rate}W"
            )
            return

        logger.info(
            f"[InverterV2] API: Setting max_grid_charge_rate: {max_grid_charge_rate}W"
        )
        self.max_grid_charge_rate = max_grid_charge_rate

    def shutdown(self):
        """Clean shutdown: restore backup config and close session."""
        logger.info("[InverterV2] Shutting down - reverting battery config changes")

        # Restore the original battery configuration
        self.restore_backup_config()

        # Close session
        self.disconnect()

    def disconnect(self):
        """Clean up session."""
        if self.session:
            self.session.close()
            logger.info("[InverterV2] Session closed")
