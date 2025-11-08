# Available Irrigation Features in Home Assistant

## Summary

This document lists all irrigation features now available in the Home Assistant Wyze integration.

---

## Control Buttons (Per Device)

### Start Zone Buttons (Per Zone)
**Entity ID:** `button.helloeban_sprinkler_ZONE_NAME`
**Icon:** 🚿 `mdi:sprinkler`
**Function:** Starts the zone for the duration set in the corresponding number entity
**Example:** `button.helloeban_sprinkler_sidewalk`

### Stop All Zones
**Entity ID:** `button.helloeban_sprinkler_stop_all_zones`
**Icon:** 🛑 `mdi:octagon`
**Function:** Stops all currently running irrigation schedules

### Pause Irrigation ⚠️ NEW
**Entity ID:** `button.helloeban_sprinkler_pause_irrigation`
**Icon:** ⏸️ `mdi:pause-circle`
**Function:** Pauses currently running irrigation without canceling it

### Resume Irrigation ⚠️ NEW
**Entity ID:** `button.helloeban_sprinkler_resume_irrigation`
**Icon:** ▶️ `mdi:play-circle`
**Function:** Resumes previously paused irrigation

---

## Number Entities (Per Zone)

### Quickrun Duration
**Entity ID:** `number.helloeban_sprinkler_ZONE_NAME_quickrun_duration`
**Unit:** Minutes
**Range:** 1-120 minutes
**Function:** Sets the duration for manual zone starts
**Example:** `number.helloeban_sprinkler_sidewalk_quickrun_duration`

---

## Binary Sensors

### Zone Running Status (Per Zone)
**Entity ID:** `binary_sensor.helloeban_sprinkler_ZONE_NAME_running`
**Icon:** 🚿 `mdi:sprinkler-variant`
**Function:** Shows if zone is currently watering
**Updates:** Every 30 seconds
**Attributes:**
- `zone_number`
- `zone_id`
- `remaining_time_seconds`

### Weather Delay Sensors (Per Device)
❌ **Not Available** - API doesn't expose this data
- Rain delay active
- Wind delay active
- Freeze delay active
- Saturation delay active

---

## Sensors

### Device-Level Sensors

#### RSSI (Signal Strength)
**Entity ID:** `sensor.helloeban_sprinkler_rssi`
**Unit:** dBm
**Device Class:** Signal Strength
**Function:** Shows WiFi signal strength

#### IP Address
**Entity ID:** `sensor.helloeban_sprinkler_ip`
**Function:** Shows device IP address on local network

#### SSID
**Entity ID:** `sensor.helloeban_sprinkler_ssid`
**Function:** Shows connected WiFi network name

#### Current Zone
**Entity ID:** `sensor.helloeban_sprinkler_current_zone`
**Function:** Shows which zone is currently running
**Value:** Zone name or "Idle"

#### Next Scheduled Run ✅ WORKING
**Entity ID:** `sensor.helloeban_sprinkler_next_scheduled_run`
**Device Class:** Timestamp
**Function:** Shows when next watering schedule will start
**Format:** DateTime with timezone

#### Active Schedules Count
**Entity ID:** `sensor.helloeban_sprinkler_active_schedules`
**Function:** Number of enabled schedules
❌ **Not Available** - Requires additional API endpoint

#### Last Run Duration
**Entity ID:** `sensor.helloeban_sprinkler_last_run_duration`
**Unit:** Minutes
**Function:** Duration of last completed watering
❌ **Not Available** - Requires additional API endpoint

---

### Zone-Level Sensors (Per Zone)

#### Soil Moisture
**Entity ID:** `sensor.helloeban_sprinkler_ZONE_NAME_soil_moisture`
**Unit:** %
**Device Class:** Moisture
**Function:** Shows estimated soil moisture level
❌ **Not Available** - API endpoint unknown

#### Smart Duration
**Entity ID:** `sensor.helloeban_sprinkler_ZONE_NAME_smart_duration`
**Unit:** Minutes
**Function:** Shows Wyze's calculated optimal watering duration
✅ **WORKING**

#### Remaining Time ✅ WORKING
**Entity ID:** `sensor.helloeban_sprinkler_ZONE_NAME_remaining_time`
**Unit:** Minutes
**Function:** Countdown timer for active watering
**Updates:** Every 30 seconds
**Example:** `sensor.helloeban_sprinkler_sidewalk_remaining_time`

#### Last Watered ✅ WORKING
**Entity ID:** `sensor.helloeban_sprinkler_ZONE_NAME_last_watered`
**Device Class:** Timestamp
**Function:** Shows when zone last finished watering
**Format:** DateTime with timezone
**Example:** `sensor.helloeban_sprinkler_sidewalk_last_watered`

---

## Feature Matrix

| Feature | Status | Entity Type | Updates |
|---------|--------|-------------|---------|
| **Start Zone** | ✅ Working | Button | On demand |
| **Stop All Zones** | ✅ Working | Button | On demand |
| **Pause Irrigation** | ✅ NEW | Button | On demand |
| **Resume Irrigation** | ✅ NEW | Button | On demand |
| **Zone Running Status** | ✅ Working | Binary Sensor | 30 seconds |
| **Remaining Time** | ✅ Working | Sensor | 30 seconds |
| **Last Watered** | ✅ Working | Sensor (timestamp) | 30 seconds |
| **Next Scheduled Run** | ✅ Working | Sensor (timestamp) | 30 seconds |
| **Smart Duration** | ✅ Working | Sensor | On update |
| **RSSI** | ✅ Working | Sensor | On update |
| **IP Address** | ✅ Working | Sensor | On update |
| **SSID** | ✅ Working | Sensor | On update |
| **Quickrun Duration** | ✅ Working | Number | User set |
| **Current Zone** | ⚠️ Partial | Sensor | Need impl |
| **Active Schedules Count** | ❌ No API | Sensor | N/A |
| **Last Run Duration** | ❌ No API | Sensor | N/A |
| **Soil Moisture** | ❌ No API | Sensor | N/A |
| **Weather Delays** | ❌ No API | Binary Sensor | N/A |
| **Create Schedule** | ❌ No Endpoint | N/A | N/A |
| **Update Schedule** | ❌ No Endpoint | N/A | N/A |
| **Delete Schedule** | ❌ No Endpoint | N/A | N/A |
| **Create Zone** | ❌ No Endpoint | N/A | N/A |
| **Update Zone** | ❌ No Endpoint | N/A | N/A |
| **Delete Zone** | ❌ No Endpoint | N/A | N/A |

---

## Total Entity Count Per Device

**Per Sprinkler Controller:**
- **6 zones** × (1 button + 1 number + 1 binary sensor + 4 sensors) = **42 entities per zone**
- **Device buttons**: 3 (Stop All, Pause, Resume)
- **Device sensors**: 4 (RSSI, IP, SSID, Next Run)

**Total: ~46 entities per irrigation controller**

---

## Usage Examples

### Automation: Notify When Zone Starts
```yaml
automation:
  - alias: "Notify when front lawn starts watering"
    trigger:
      - platform: state
        entity_id: binary_sensor.helloeban_sprinkler_sidewalk_running
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Irrigation Started"
          message: "Front lawn is now watering for {{ state_attr('binary_sensor.helloeban_sprinkler_sidewalk_running', 'remaining_time_seconds') | int // 60 }} minutes"
```

### Automation: Pause Irrigation If Rain Detected
```yaml
automation:
  - alias: "Pause irrigation when it rains"
    trigger:
      - platform: state
        entity_id: binary_sensor.rain_sensor
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.helloeban_sprinkler_sidewalk_running
        state: "on"
    action:
      - service: button.press
        target:
          entity_id: button.helloeban_sprinkler_pause_irrigation
```

### Automation: Resume After Rain Stops
```yaml
automation:
  - alias: "Resume irrigation after rain"
    trigger:
      - platform: state
        entity_id: binary_sensor.rain_sensor
        to: "off"
        for:
          minutes: 30
    action:
      - service: button.press
        target:
          entity_id: button.helloeban_sprinkler_resume_irrigation
```

### Script: Water Front Lawn for 10 Minutes
```yaml
script:
  water_front_lawn:
    sequence:
      - service: number.set_value
        target:
          entity_id: number.helloeban_sprinkler_sidewalk_quickrun_duration
        data:
          value: 10
      - service: button.press
        target:
          entity_id: button.helloeban_sprinkler_sidewalk
```

### Dashboard Card
```yaml
type: entities
title: Irrigation Control
entities:
  - entity: binary_sensor.helloeban_sprinkler_sidewalk_running
    name: Sidewalk Status
  - entity: sensor.helloeban_sprinkler_sidewalk_remaining_time
    name: Time Remaining
  - entity: sensor.helloeban_sprinkler_sidewalk_last_watered
    name: Last Watered
  - entity: sensor.helloeban_sprinkler_next_scheduled_run
    name: Next Schedule
  - entity: number.helloeban_sprinkler_sidewalk_quickrun_duration
    name: Duration (min)
  - entity: button.helloeban_sprinkler_sidewalk
    name: Start
  - entity: button.helloeban_sprinkler_pause_irrigation
    name: Pause
  - entity: button.helloeban_sprinkler_resume_irrigation
    name: Resume
  - entity: button.helloeban_sprinkler_stop_all_zones
    name: Stop All
```

---

## Limitations

### API Limitations
These features cannot be implemented because the API doesn't expose them:
1. **Weather delay status** - Not available in API responses
2. **Soil moisture levels** - API endpoint unknown
3. **Schedule CRUD** - API endpoints not documented

### Missing Functionality
These would require reverse engineering the Wyze app:
1. **Create/Edit/Delete schedules** - Endpoint unknown
2. **Create/Edit/Delete zones** - Endpoint unknown
3. **Enable/Disable schedules** - Endpoint unknown

---

## What's New in This Release

### Added Features
- ✅ Pause Irrigation button
- ✅ Resume Irrigation button
- ✅ Next Scheduled Run timestamp
- ✅ Last Watered timestamp per zone
- ✅ Real-time running status
- ✅ Remaining time countdown

### Improved
- 🔄 All sensors now update every 30 seconds
- 🔄 Dispatcher pattern for efficient updates
- 🔄 Graceful degradation for missing API data

---

## Installation

### Via HACS
1. HACS → Integrations
2. Search for "Wyze"
3. Install/Update
4. Restart Home Assistant

### Configuration
No additional configuration needed. Once installed:
1. All entities automatically appear
2. Buttons work immediately
3. Sensors update every 30 seconds

---

## Troubleshooting

### Entities Not Updating
- Check Home Assistant logs for errors
- Verify wyzeapy is installed from fork: `wyzeapy @ git+https://github.com/steyncd/wyzeapy.git@main`
- Restart Home Assistant

### Buttons Not Working
- Ensure device is online (check `sensor.helloeban_sprinkler_rssi`)
- Check Home Assistant logs for error messages
- Verify API credentials are valid

### Missing Entities
- Check if zones are enabled in Wyze app
- Restart Home Assistant after adding new zones
- Check entity registry in Developer Tools

---

## Contributing

Found missing features or bugs? Please report them:
- **ha-wyzeapi**: https://github.com/steyncd/ha-wyzeapi/issues
- **wyzeapy**: https://github.com/steyncd/wyzeapy/issues

---

**Last Updated:** 2025-11-08
**Version:** 0.1.35+ (with irrigation enhancements)
