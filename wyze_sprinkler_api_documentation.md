# Wyze Sprinkler Controller API Documentation
**Reverse-Engineered from Wyze App Traffic**
**Device Model:** Wyze Sprinkler Controller (WSPRK1)
**Date Captured:** November 6, 2025
**Contributor:** steyncd@gmail.com
**For:** ha-wyzeapi GitHub Issue #230

---

## 🔑 Authentication

All API calls require:
- **Access Token:** JWT Bearer token obtained from Wyze authentication
- **App Headers:** Specific headers to mimic the Wyze mobile app

### Required Headers
```
Content-Type: application/json
appid: BSSC_83d270f3a6124d87
appinfo: wyze_ios_3.8.5.11
appversion: 3.8.5.11
env: prod
access_token: [JWT_TOKEN]
signature2: [CALCULATED_SIGNATURE]
phoneid: [DEVICE_UUID]
requestid: [UNIQUE_REQUEST_ID]
```

---

## 📍 Base URL
```
https://wyze-lockwood-service.wyzecam.com
```

---

## 🚿 API Endpoints

### 1. Quick Run (Start Zones)
**Purpose:** Start one or more sprinkler zones with specified durations

**Endpoint:**
```
POST /plugin/irrigation/quickrun
```

**Request Payload:**
```json
{
    "nonce": "1762461722893",
    "device_id": "BS_WK1_7C78B20702C7",
    "zone_runs": [
        {
            "zone_number": 1,
            "duration": 600
        }
    ]
}
```

**Payload Fields:**
- `nonce` (string): Unix timestamp in milliseconds
- `device_id` (string): Sprinkler controller device ID (format: BS_WK1_XXXXXXXXXX)
- `zone_runs` (array): Array of zone run configurations
  - `zone_number` (integer): Zone number (1-8 for 8-zone controller)
  - `duration` (integer): Duration in seconds (e.g., 600 = 10 minutes)

**Response (Success):**
```json
{
    "code": 1,
    "current": 1,
    "data": {
        "result": true
    },
    "hash": "1",
    "instance_id": "dc80bf708e29eeaaa16dadb7f68acda6",
    "isShowToast": 0,
    "message": "Success",
    "toastMsg": null,
    "total": 1,
    "version": 1
}
```

**Response Fields:**
- `code` (integer): Status code (1 = success)
- `message` (string): Result message
- `data.result` (boolean): true if zone started successfully

---

### 2. Stop Running Schedule/Zones
**Purpose:** Stop all currently running zones

**Endpoint:**
```
POST /plugin/irrigation/runningschedule
```

**Request Payload:**
```json
{
    "nonce": "1762461766430",
    "device_id": "BS_WK1_7C78B20702C7",
    "action": "STOP"
}
```

**Payload Fields:**
- `nonce` (string): Unix timestamp in milliseconds
- `device_id` (string): Sprinkler controller device ID
- `action` (string): "STOP" to stop all running zones

**Response (Success):**
```json
{
    "code": 1,
    "current": 0,
    "data": null,
    "hash": "1",
    "instance_id": "6b164ea8756e024ebba82ab43d6aa7dd",
    "isShowToast": 0,
    "message": "Success",
    "toastMsg": null,
    "total": 0,
    "version": 1
}
```

---

### 3. Get Schedule Runs (History & Upcoming)
**Purpose:** Get recent watering history and upcoming scheduled runs

**Endpoint:**
```
GET /plugin/irrigation/schedule_runs
```

**Query Parameters:**
- `device_id` (string): Sprinkler controller device ID
- `limit` (integer): Number of records to return (e.g., 2)
- `nonce` (string): Unix timestamp in milliseconds

**Request Example:**
```
GET /plugin/irrigation/schedule_runs?device_id=BS_WK1_7C78B20702C7&limit=2&nonce=1762461767158
```

**Response (Success):**
```json
{
    "code": 1,
    "data": {
        "schedules": [
            {
                "schedule_id": "App Quick Run",
                "schedule_name": "App Quick Run",
                "schedule_type": "MANUAL",
                "schedule_state": "past",
                "device_id": "BS_WK1_7C78B20702C7",
                "start_local": "2025-11-06T22:38:43",
                "end_local": "2025-11-06T22:38:50",
                "start_utc": "2025-11-06T20:38:43Z",
                "end_utc": "2025-11-06T20:38:50Z",
                "duration": 7,
                "duration_str": "00:00:07",
                "zone_count": 1,
                "zone_runs": [
                    {
                        "zone_number": 1,
                        "zone_id": "417ff3ac4b5b48099b6477aea7f427df",
                        "zone_name": "Sidewalk",
                        "type": "IRRIGATE",
                        "start_local": "2025-11-06T22:38:43",
                        "end_local": "2025-11-06T22:38:50",
                        "start_utc": "2025-11-06T20:38:43Z",
                        "end_utc": "2025-11-06T20:38:50Z"
                    }
                ]
            },
            {
                "schedule_id": "a222fb271df2458f83b252db45c6d5fc",
                "schedule_name": "Default Schedule",
                "schedule_type": "FIXED",
                "schedule_state": "upcoming",
                "device_id": "BS_WK1_7C78B20702C7",
                "start_local": "2025-11-07T06:15:00",
                "end_local": "2025-11-07T06:25:00",
                "start_utc": "2025-11-07T04:15:00Z",
                "end_utc": "2025-11-07T04:25:00Z",
                "duration": 600,
                "zone_count": 1,
                "cycle_soak": true,
                "run_days": {
                    "frequency": "day",
                    "every": 1,
                    "config_date": "2025-10-21"
                },
                "run_times": {
                    "type": "start_at",
                    "specific": "06:15"
                },
                "zone_info": [
                    {
                        "zone_number": 1,
                        "zone_id": "417ff3ac4b5b48099b6477aea7f427df",
                        "zone_name": "Sidewalk",
                        "duration": 600,
                        "smart_duration": 0,
                        "order_id": 0
                    }
                ]
            }
        ]
    },
    "message": "Success"
}
```

**Response Fields:**
- `schedules` (array): List of schedule runs (past and upcoming)
  - `schedule_id` (string): Unique schedule identifier
  - `schedule_name` (string): Display name
  - `schedule_type` (string): "MANUAL" (quick run) or "FIXED" (recurring schedule)
  - `schedule_state` (string): "past", "running", "upcoming"
  - `start_local` (string): Start time in local timezone
  - `end_local` (string): End time in local timezone
  - `duration` (integer): Total duration in seconds
  - `zone_count` (integer): Number of zones in this run
  - `cycle_soak` (boolean): Whether cycle & soak is enabled
  - `run_days` (object): Schedule frequency configuration
    - `frequency` (string): "day", "week", etc.
    - `every` (integer): Run every N days/weeks
  - `run_times` (object): When to start
    - `type` (string): "start_at"
    - `specific` (string): Time in HH:MM format
  - `zone_runs` (array): Individual zone run details
    - `zone_number` (integer): Zone number
    - `zone_id` (string): Unique zone identifier
    - `zone_name` (string): Zone display name
    - `type` (string): "IRRIGATE"

---

### 4. Get All Schedules (Full Configuration)
**Purpose:** Get complete list of all configured schedules with full settings

**Endpoint:**
```
GET /plugin/irrigation/schedule
```

**Query Parameters:**
- `device_id` (string): Sprinkler controller device ID
- `nonce` (string): Unix timestamp in milliseconds

**Request Example:**
```
GET /plugin/irrigation/schedule?device_id=BS_WK1_7C78B20702C7&nonce=1762461852049
```

**Response (Success):**
```json
{
    "code": 1,
    "data": {
        "schedules": [
            {
                "schedule_id": "a222fb271df2458f83b252db45c6d5fc",
                "schedule_type": "FIXED",
                "name": "Default Schedule",
                "enabled": true,
                "device_id": "BS_WK1_7C78B20702C7",
                "start_date": "2025-10-21",
                "end_date": "2099-12-31",
                "run_days": {
                    "frequency": "day",
                    "every": 1,
                    "config_date": "2025-10-21"
                },
                "run_times": {
                    "type": "start_at",
                    "specific": "06:15"
                },
                "cycle_soak": true,
                "cycle_time": 10,
                "soak_time": 15,
                "smart_cycle": false,
                "seasonal_shift": false,
                "rain_delay_enabled": true,
                "wind_delay_enabled": true,
                "freeze_delay_enabled": true,
                "saturation_delay_enabled": true,
                "total_duration": 600,
                "zone_info": [
                    {
                        "zone_number": 1,
                        "zone_id": "417ff3ac4b5b48099b6477aea7f427df",
                        "zone_name": "Sidewalk",
                        "duration": 600,
                        "smart_duration": 0,
                        "order_id": 0
                    }
                ]
            }
        ]
    },
    "message": "Success"
}
```

**Response Fields:**
- `schedules` (array): List of all configured schedules
  - `schedule_id` (string): Unique schedule identifier
  - `schedule_type` (string): "FIXED" (manual durations), "SMART" (AI-calculated durations)
  - `name` (string): Schedule display name
  - `enabled` (boolean): Whether schedule is active
  - `device_id` (string): Associated device
  - `start_date` (string): When schedule becomes active
  - `end_date` (string): When schedule expires
  - `run_days` (object): Frequency configuration
    - `frequency` (string): "day" or "week"
    - `every` (integer): For daily - run every N days
    - `week_day` (array): For weekly - days of week [1=Mon, 7=Sun]
  - `run_times` (object): Start time configuration
    - `type` (string): "start_at"
    - `specific` (string): Time in HH:MM format (24-hour)
  - **Weather Skip Features:**
    - `rain_delay_enabled` (boolean): Skip when rain detected
    - `wind_delay_enabled` (boolean): Skip when windy
    - `freeze_delay_enabled` (boolean): Skip when freezing
    - `saturation_delay_enabled` (boolean): Skip when soil saturated
  - **Cycle & Soak:**
    - `cycle_soak` (boolean): Enable cycle & soak mode
    - `cycle_time` (integer): Minutes to water before soaking
    - `soak_time` (integer): Minutes to wait between cycles
    - `smart_cycle` (boolean): AI-optimized cycle times
  - **Smart Watering:**
    - `seasonal_shift` (boolean): Adjust for seasons
  - `total_duration` (integer): Total schedule duration in seconds
  - `zone_info` (array): Zones included in schedule
    - `zone_number` (integer): Zone number (1-8)
    - `zone_id` (string): Unique zone identifier
    - `zone_name` (string): Custom zone name
    - `duration` (integer): Manual duration in seconds
    - `smart_duration` (integer): AI-calculated duration (when schedule_type="SMART")
    - `order_id` (integer): Run order

---

### 5. Get Zone Details (Configuration & Status)
**Purpose:** Get comprehensive zone information including soil moisture, history, and settings

**Endpoint:**
```
GET /plugin/irrigation/zone
```

**Query Parameters:**
- `device_id` (string): Sprinkler controller device ID
- `nonce` (string): Unix timestamp in milliseconds

**Request Example:**
```
GET /plugin/irrigation/zone?device_id=BS_WK1_7C78B20702C7&nonce=1762461893723
```

**Response (Success):**
```json
{
    "code": 1,
    "data": {
        "zones": [
            {
                "zone_number": 1,
                "zone_id": "417ff3ac4b5b48099b6477aea7f427df",
                "name": "Sidewalk",
                "device_id": "BS_WK1_7C78B20702C7",
                "enabled": true,
                "wired": true,
                "area": 800.0,
                "soil_moisture_level_at_end_of_day_pct": 0.198,
                "crop_type": "COOL_SEASON_GRASS",
                "soil_type": "CLAY",
                "slope_type": "FLAT",
                "exposure_type": "SOME_SHADE",
                "nozzle_type": "ROTOR_HEAD",
                "flow_rate": 1.0,
                "efficiency": 80.0,
                "root_depth": 6.0,
                "smart_duration": 1841,
                "latest_events": [
                    {
                        "duration": 44,
                        "end_local": "2025-11-06T22:42:47",
                        "end_ts": 1762461767,
                        "schedule_name": "App Quick Run",
                        "schedule_type": "MANUAL"
                    }
                ]
            }
        ]
    },
    "message": "Success"
}
```

**Response Fields:**
- `zones` (array): List of all zones with detailed configuration
  - **Zone Identity:**
    - `zone_number` (integer): Zone number (1-8)
    - `zone_id` (string): Unique zone identifier
    - `name` (string): Custom zone name
    - `enabled` (boolean): Whether zone is active
    - `wired` (boolean): Physical connection status
  - **🌱 Soil Moisture Data (KEY FEATURE!):**
    - `soil_moisture_level_at_end_of_day_pct` (float): Current soil moisture percentage (0-1 scale)
      - Example: 0.198 = 19.8% moisture
      - This is calculated based on watering history, weather, and soil properties
  - **Zone Properties:**
    - `area` (float): Zone area in square feet
    - `crop_type` (string): Vegetation type (e.g., "COOL_SEASON_GRASS")
    - `soil_type` (string): Soil classification ("CLAY", "LOAM", "SAND")
    - `slope_type` (string): Terrain slope ("FLAT", "SLIGHT", "MODERATE", "STEEP")
    - `exposure_type` (string): Sun exposure ("FULL_SUN", "SOME_SHADE", "LOTS_OF_SHADE")
    - `nozzle_type` (string): Sprinkler head type ("ROTOR_HEAD", "SPRAY_HEAD", "DRIP")
    - `flow_rate` (float): Flow rate in gallons per minute
    - `efficiency` (float): System efficiency percentage
    - `root_depth` (float): Root depth in inches
  - **Smart Watering:**
    - `smart_duration` (integer): AI-calculated duration in seconds
    - `available_water_capacity` (float): Soil water holding capacity
    - `manage_allow_depletion` (float): Allowed moisture depletion percentage
  - **Watering History:**
    - `latest_events` (array): Recent watering events (up to 10)
      - `duration` (integer): Seconds watered
      - `end_local` (string): End time local
      - `schedule_name` (string): Which schedule ran
      - `schedule_type` (string): "MANUAL" or "FIXED"

---

## 🔍 Potential Additional Endpoints (Not Yet Captured)

Based on Wyze app functionality, these endpoints likely exist but require additional traffic capture:

### Device Hardware Status
- **Purpose:** Get device health, battery, WiFi signal
- **Likely Endpoint:** `GET /plugin/irrigation/device/{device_id}/status`
- **Expected Data:**
  - Battery level (if applicable)
  - WiFi signal strength
  - Firmware version
  - Connection status

### Weather Data Integration
- **Purpose:** Get local weather affecting watering
- **Likely Endpoint:** `GET /plugin/irrigation/weather`
- **Expected Data:**
  - Current weather conditions
  - Rain forecast
  - Temperature
  - Wind conditions
  - Precipitation history

### Schedule CRUD Operations
- **Likely Endpoints:**
  - `POST /plugin/irrigation/schedule` - Create new schedule
  - `PUT /plugin/irrigation/schedule/{id}` - Update schedule
  - `DELETE /plugin/irrigation/schedule/{id}` - Delete schedule

---

## 💡 Implementation Notes for ha-wyzeapi

### Current Integration Limitations
The current ha-wyzeapi integration provides:
- ✅ Button entities to start zones
- ✅ Number entities to set durations
- ❌ No zone status sensors (currently running, remaining time)
- ❌ No schedule management
- ❌ No device status (battery, signal, etc.)
- ❌ No Sprinkler Plus features (moisture, weather)

### Proposed Enhancements

#### 1. Zone Status Sensors
Create binary_sensor or sensor entities for each zone:
```yaml
sensor.sprinkler_zone_1_status: "Running" | "Idle"
sensor.sprinkler_zone_1_remaining_time: 480  # seconds
```

#### 2. Device Health Sensors
```yaml
sensor.sprinkler_battery_level: 85  # percentage
sensor.sprinkler_wifi_signal: -45  # dBm
sensor.sprinkler_firmware_version: "1.2.3"
```

#### 3. Schedule Entities
```yaml
calendar.sprinkler_schedules: Shows upcoming scheduled runs
switch.sprinkler_schedule_1: Enable/disable specific schedules
```

#### 4. Sprinkler Plus Integration (if available)
```yaml
sensor.sprinkler_soil_moisture: 45  # percentage
binary_sensor.sprinkler_rain_delay: on/off
sensor.sprinkler_weather_skip_reason: "Rain forecast"
```

---

## 🧪 Testing Notes

- **Device Tested:** Wyze Sprinkler Controller (BS_WK1_7C78B20702C7)
- **App Version:** Wyze iOS 3.8.5.11
- **Zone Configuration:** 6 active zones
- **Traffic Capture Method:** mitmproxy with SSL certificate
- **Success Rate:** 100% for captured endpoints

---

## ⚠️ Important Security Notes

1. **Access Token:** JWT tokens expire after ~48 hours and must be refreshed
2. **Signature Calculation:** The `signature2` header appears to be an MD5 or SHA hash of request parameters - implementation needs investigation
3. **Device ID:** Each sprinkler controller has a unique device ID in format BS_WK1_XXXXXXXXXXXX
4. **API Rate Limiting:** Unknown - recommend conservative polling intervals (30-60 seconds for status)

---

## 📝 Additional Research Needed

To complete the API documentation, we need to capture:

1. **GET device status endpoint** - View sprinkler details in app while capturing
2. **Schedule list endpoint** - View schedules screen
3. **Schedule CRUD operations** - Create/edit/delete schedules
4. **Zone name updates** - Rename zones in app
5. **Moisture sensor data** (if Sprinkler Plus is present)
6. **Weather integration settings** (if applicable)

---

## 🤝 Contributing

This documentation was created for ha-wyzeapi GitHub Issue #230:
https://github.com/SecKatie/ha-wyzeapi/issues/230

**How to contribute:**
1. Capture additional API calls using mitmproxy
2. Document request/response formats
3. Test with different Wyze Sprinkler models
4. Validate signature2 calculation method
5. Submit findings to the ha-wyzeapi repository

---

## 📄 License

This documentation is provided as-is for the benefit of the open-source home automation community. The Wyze API is proprietary and reverse-engineered for integration purposes only.

**Disclaimer:** This is an unofficial API documentation. Wyze Labs, Inc. does not officially support third-party integrations. Use at your own risk.

---

**Generated:** November 6, 2025
**Contact:** steyncd@gmail.com
**Repository:** https://github.com/SecKatie/ha-wyzeapi
