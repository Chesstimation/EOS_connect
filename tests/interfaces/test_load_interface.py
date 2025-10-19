from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest
from requests.exceptions import RequestException
from src.interfaces.load_interface import LoadInterface


@pytest.fixture
def config_fixture():
    """Return a default configuration mapping used by tests.

    This fixture provides a dictionary of configuration values for the load
    interface tests. The mapping contains the following keys:

    - source (str): Identifier of the data source (e.g. "openhab").
    - url (str): Base URL used to access the source.
    - load_sensor (str): Sensor identifier to be queried (e.g. "sensor.test").
    - max_retries (int): Maximum number of retry attempts for operations.
    - retry_backoff (int): Backoff delay in seconds between retries. A value of
        0 disables sleeping so tests run quickly.
    - warning_threshold (int): Numeric threshold used to trigger warnings in tests.

    Returns:
            dict: Configuration dictionary used by the tests.
    """
    return {
        "source": "openhab",
        "url": "http://dummy",
        "load_sensor": "sensor.test",
        "max_retries": 3,
        "retry_backoff": 0,  # no sleep for test
        "warning_threshold": 2,
    }


def test_request_with_retries_logs_and_retries(config_fixture):
    """
    Verify that LoadInterface._LoadInterface__request_with_retries correctly retries on failure,
    logs warnings up to the configured warning threshold, then logs an error, and ultimately
    returns None after exhausting the maximum retries.
    """
    li = LoadInterface(config_fixture)

    with patch(
        "src.interfaces.load_interface.requests.get",
        side_effect=RequestException("fail"),
    ) as mock_get, patch(
        "src.interfaces.load_interface.time.sleep"
    ) as mock_sleep, patch(
        "src.interfaces.load_interface.logger"
    ) as mock_logger:
        resp = getattr(li, "_LoadInterface__request_with_retries")(
            "get", "http://dummy"
        )
        assert resp is None
        # Should try max_retries times
        assert mock_get.call_count == config_fixture["max_retries"]
        # Should log warning for first (warning_threshold-1) attempts, then error
        warning_calls = [call for call in mock_logger.warning.call_args_list]
        error_calls = [call for call in mock_logger.error.call_args_list]
        assert len(warning_calls) == 1
        assert len(error_calls) == 1


def test_fetch_historical_energy_data_from_openhab_success(config_fixture):
    """
    Test that LoadInterface.__fetch_historical_energy_data_from_openhab successfully
    retrieves and parses historical energy data from an OpenHAB endpoint.

    The test constructs a LoadInterface using the provided config_fixture and patches
    external dependencies (requests.get, time.sleep and logger) to provide a
    controlled, deterministic response. The mocked HTTP response returns JSON with
    entries containing "state" (string) and "time" (milliseconds since epoch).
    The private method under test is expected to:
    - call the OpenHAB endpoint for the given item and time range,
    - parse the JSON payload into a list of dictionaries,
    - convert the millisecond "time" values into a "last_updated" datetime or
        equivalent field on each entry.

    Assertions performed:
    - the returned result is a list,
    - the first item's "state" equals the expected value from the mocked response,
    - the first item includes a "last_updated" key indicating the time conversion.

    Args:
            config_fixture: pytest fixture providing configuration for LoadInterface.
    """
    li = LoadInterface(config_fixture)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"state": "10", "time": 1690000000000},
            {"state": "20", "time": 1690003600000},
        ]
    }
    with patch(
        "src.interfaces.load_interface.requests.get", return_value=mock_response
    ), patch("src.interfaces.load_interface.time.sleep"), patch(
        "src.interfaces.load_interface.logger"
    ):
        start = datetime(2023, 7, 1, 0, 0)
        end = datetime(2023, 7, 1, 1, 0)
        result = li._LoadInterface__fetch_historical_energy_data_from_openhab(
            "sensor.test", start, end
        )
        assert isinstance(result, list)
        assert result[0]["state"] == "10"
        assert "last_updated" in result[0]


def test_fetch_historical_energy_data_from_openhab_failure(config_fixture):
    """
    Test that the LoadInterface private method __fetch_historical_energy_data_from_openhab
    handles HTTP request failures by returning an empty list instead of raising.

    This test sets up a LoadInterface instance and patches:
    - src.interfaces.load_interface.requests.get to raise
        requests.exceptions.RequestException("fail")
    - src.interfaces.load_interface.time.sleep to avoid real delays
    - src.interfaces.load_interface.logger to silence logging

    It then calls the name-mangled private method for the sensor "sensor.test"
    over the interval 2023-07-01 00:00 to 2023-07-01 01:00 and asserts that the
    method returns an empty list, confirming that request errors are caught and
    result in an empty result rather than propagating an exception.
    """
    li = LoadInterface(config_fixture)
    with patch(
        "src.interfaces.load_interface.requests.get",
        side_effect=RequestException("fail"),
    ), patch("src.interfaces.load_interface.time.sleep"), patch(
        "src.interfaces.load_interface.logger"
    ):
        start = datetime(2023, 7, 1, 0, 0)
        end = datetime(2023, 7, 1, 1, 0)
        result = li._LoadInterface__fetch_historical_energy_data_from_openhab(
            "sensor.test", start, end
        )
        assert result == []


def test_fetch_historical_energy_data_from_homeassistant_success(config_fixture):
    """
    Test that __fetch_historical_energy_data_from_homeassistant returns parsed data on success.
    """
    li = LoadInterface(config_fixture)
    mock_response = MagicMock()
    mock_response.json.return_value = [
        [
            {"state": "5", "last_updated": "2023-07-01T00:00:00+00:00"},
            {"state": "6", "last_updated": "2023-07-01T01:00:00+00:00"},
        ]
    ]
    mock_response.status_code = 200
    with patch(
        "src.interfaces.load_interface.requests.get", return_value=mock_response
    ), patch("src.interfaces.load_interface.time.sleep"), patch(
        "src.interfaces.load_interface.logger"
    ):
        start = datetime(2023, 7, 1, 0, 0)
        end = datetime(2023, 7, 1, 1, 0)
        result = li._LoadInterface__fetch_historical_energy_data_from_homeassistant(
            "sensor.test", start, end
        )
        assert isinstance(result, list)
        assert result[0]["state"] == "5"
        assert "last_updated" in result[0]


def test_fetch_historical_energy_data_from_homeassistant_failure(config_fixture):
    """
    Test that __fetch_historical_energy_data_from_homeassistant returns empty list on failure.
    """
    li = LoadInterface(config_fixture)
    with patch(
        "src.interfaces.load_interface.requests.get",
        side_effect=RequestException("fail"),
    ), patch("src.interfaces.load_interface.time.sleep"), patch(
        "src.interfaces.load_interface.logger"
    ):
        start = datetime(2023, 7, 1, 0, 0)
        end = datetime(2023, 7, 1, 1, 0)
        result = li._LoadInterface__fetch_historical_energy_data_from_homeassistant(
            "sensor.test", start, end
        )
        assert result == []


def test_timezone_fallback_to_none(config_fixture):
    """
    Test that LoadInterface falls back to None timezone if an invalid tz_name is given.
    """
    li = LoadInterface(config_fixture, tz_name="Invalid/Timezone")
    assert getattr(li, "time_zone", None) is None


def test_empty_sensor_returns_empty_list(config_fixture):
    """
    Test that fetch methods return empty list if sensor/entity_id is empty.
    """
    li = LoadInterface(config_fixture)
    start = datetime(2023, 7, 1, 0, 0)
    end = datetime(2023, 7, 1, 1, 0)
    assert (
        li._LoadInterface__fetch_historical_energy_data_from_openhab("", start, end)
        == []
    )
    assert (
        li._LoadInterface__fetch_historical_energy_data_from_homeassistant(
            "", start, end
        )
        == []
    )


def test_get_load_profile_returns_expected_structure(config_fixture):
    """
    Test that get_load_profile returns a list of floats (energy values).
    """
    li = LoadInterface(config_fixture)
    with patch.object(
        li,
        "_LoadInterface__fetch_historical_energy_data_from_openhab",
        return_value=[
            {"state": "10", "last_updated": "2023-07-01T00:00:00+00:00"},
            {"state": "20", "last_updated": "2023-07-01T01:00:00+00:00"},
        ],
    ), patch("src.interfaces.load_interface.time.sleep"):
        result = li.get_load_profile(24, datetime(2023, 7, 1, 0, 0))
        assert isinstance(result, list)
        assert all(isinstance(item, (float, int)) for item in result)
        assert len(result) == 48


def test_get_load_profile_handles_empty_data(config_fixture):
    """
    Test that get_load_profile returns an empty list if no data is available.
    """
    li = LoadInterface(config_fixture)
    with patch.object(
        li, "_LoadInterface__fetch_historical_energy_data_from_openhab", return_value=[]
    ), patch("src.interfaces.load_interface.time.sleep"):
        result = li.get_load_profile(24, datetime(2023, 7, 1, 0, 0))
        assert isinstance(result, list)
        assert all(isinstance(item, (float, int)) for item in result)
        assert len(result) == 24 or len(result) == 48  # depending on your config


def test_get_load_profile_invalid_dates(config_fixture):
    """
    Test that get_load_profile returns a default profile for valid but empty input.
    """
    li = LoadInterface(config_fixture)
    with patch("src.interfaces.load_interface.time.sleep"), patch.object(
        li, "_LoadInterface__fetch_historical_energy_data_from_openhab", return_value=[]
    ):
        result = li.get_load_profile(24, datetime(2023, 7, 1, 0, 0))
        # Accept either 24 or 48 values, but all should be default profile values
        default_profile = li._get_default_profile()
        assert isinstance(result, list)
        assert all(isinstance(item, (float, int)) for item in result)
        assert len(result) in (24, 48)
        # Optionally, check that the first 24 match the default profile
        assert result[:24] == default_profile[:24]


def test_get_load_profile_with_none_sensor(config_fixture):
    config_fixture["load_sensor"] = ""
    li = LoadInterface(config_fixture)
    with patch("src.interfaces.load_interface.time.sleep"):

        result = li.get_load_profile(0, datetime(2023, 7, 1, 0, 0))
        assert result == []


def test_get_load_profile_handles_partial_data(config_fixture):
    """
    Test that get_load_profile can handle partial/malformed data from fetch.
    """
    li = LoadInterface(config_fixture)
    with patch.object(
        li,
        "_LoadInterface__fetch_historical_energy_data_from_openhab",
        return_value=[
            {"state": "10"},  # missing last_updated
            {"last_updated": "2023-07-01T01:00:00+00:00"},  # missing state
        ],
    ), patch("src.interfaces.load_interface.time.sleep"):
        result = li.get_load_profile(24, datetime(2023, 7, 1, 0, 0))
        assert isinstance(result, list)
        # Should not raise, but may skip or fill missing fields
