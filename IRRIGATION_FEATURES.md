# Wyze Sprinkler Controller - Feature Guide

Quick reference guide for all irrigation features in ha-wyzeapi.

---

## 🎮 Control Entities (Already Working)

### Zone Start Buttons
- **Entity:** `button.sprinkler_zone_name`
- **Action:** Starts the zone with configured duration
- **Example:** `button.sprinkler_sidewalk`

### Stop All Button
- **Entity:** `button.sprinkler_stop_all_zones`
- **Action:** Immediately stops all running zones
- **Use:** Emergency stop or manual override

### Duration Settings
- **Entity:** `number.sprinkler_zone_name`
- **Range:** 1-180 minutes
- **Default:** 10 minutes
- **Example:** Set to 15 minutes, then press zone button to water for 15 minutes

---

## 📊 Monitoring Sensors (New Features)

### 🌱 Soil Moisture (Per Zone) ⭐ FLAGSHIP FEATURE
**Entity:** `sensor.sprinkler_zone_name_soil_moisture`

Shows Wyze's AI-calculated soil moisture percentage.

**Value:** 0-100%
**Icon:**
- 🔴 `water-alert` (< 20% - needs water)
- 🟡 `water-minus` (20-50% - moderate)
- 🟢 `water-check` (> 50% - good)

**Automation Example:**
```yaml
automation:
  - alias: "Water if soil is dry"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sprinkler_zone_1_soil_moisture
        below: 25
    action:
      - service: button.press
        target:
          entity_id: button.sprinkler_zone_1
```

**Configuration Details (in attributes):**
- Crop type (grass, flowers, vegetables)
- Soil type (clay, loam, sand)
- Slope (flat, slight, moderate, steep)
- Sun exposure (full sun, some shade, lots of shade)
- Nozzle type (rotor head, spray head, drip)
- Area (square feet)
- Flow rate (gallons per minute)
- Root depth (inches)

---

### 🧠 Smart Duration (Per Zone)
**Entity:** `sensor.sprinkler_zone_name_smart_duration`

Wyze's AI recommendation for optimal watering time.

**Value:** Minutes
**Calculation:** Based on weather, soil moisture, crop type, and historical data

**Use Case:** Compare your manual settings to Wyze's recommendations

---

### ⏱️ Remaining Time (Per Zone)
**Entity:** `sensor.sprinkler_zone_name_remaining_time`

Time left in current watering cycle.

**Value:**
- 0 minutes (when idle)
- 1-180 minutes (when running)

**Automation Example:**
```yaml
automation:
  - alias: "Notify when watering almost done"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sprinkler_zone_1_remaining_time
        below: 2
    action:
      - service: notify.mobile_app
        data:
          message: "Zone 1 watering will finish in 2 minutes"
```

---

### 🕐 Last Watered (Per Zone)
**Entity:** `sensor.sprinkler_zone_name_last_watered`

Timestamp of the last watering event.

**Value:** Date/time or "unknown"
**Attributes:**
- Recent watering history (last 10 events)
- Last duration (seconds)
- Last schedule name

**Dashboard Use:**
```yaml
type: entity
entity: sensor.sprinkler_zone_1_last_watered
format: relative  # Shows "2 hours ago"
```

---

### 💧 Running Status (Per Zone)
**Entity:** `binary_sensor.sprinkler_zone_name_running`

Indicates if the zone is currently watering.

**Value:**
- On (watering now)
- Off (idle)

**Automation Example:**
```yaml
automation:
  - alias: "Turn off outdoor lights while watering"
    trigger:
      - platform: state
        entity_id: binary_sensor.sprinkler_zone_1_running
        to: "on"
    action:
      - service: light.turn_off
        target:
          entity_id: light.backyard_lights
```

---

### 🎯 Current Zone (Device)
**Entity:** `sensor.sprinkler_current_zone`

Shows which zone is currently running.

**Value:**
- Zone name (e.g., "Sidewalk")
- "Idle" (nothing running)

---

### 📅 Next Scheduled Run (Device)
**Entity:** `sensor.sprinkler_next_scheduled_run`

Next scheduled watering time.

**Value:** Date/time or "unknown"
**Attributes:**
- Schedule name
- Zones that will run

**Dashboard Card:**
```yaml
type: entity
entity: sensor.sprinkler_next_scheduled_run
format: relative  # Shows "in 6 hours"
```

---

### 📋 Active Schedules (Device)
**Entity:** `sensor.sprinkler_active_schedules`

Count of enabled schedules.

**Value:** Number (0-10+)
**Attributes:** List of schedule names and enabled status

---

### ⏱️ Last Run Duration (Device)
**Entity:** `sensor.sprinkler_last_run_duration`

Duration of the last completed watering cycle.

**Value:** Minutes
**Attributes:**
- Zones that ran
- End time

---

## 🌦️ Weather Delay Sensors (Diagnostic)

These sensors show if watering is being skipped due to weather conditions.

**Note:** Diagnostic category = disabled by default. Enable manually if needed.

### ☔ Rain Delay
**Entity:** `binary_sensor.sprinkler_rain_delay_active`
**On:** Watering skipped due to rain
**Icon:** 🌧️ rainy / ☀️ sunny

### 💨 Wind Delay
**Entity:** `binary_sensor.sprinkler_wind_delay_active`
**On:** Watering skipped due to high winds
**Icon:** 💨 windy / ☀️ sunny

### ❄️ Freeze Delay
**Entity:** `binary_sensor.sprinkler_freeze_delay_active`
**On:** Watering skipped due to freezing temperatures
**Icon:** ❄️ snowflake / ☀️ sunny

### 💧 Saturation Delay
**Entity:** `binary_sensor.sprinkler_saturation_delay_active`
**On:** Watering skipped due to soil saturation
**Icon:** 💧 water-alert / ✓ water-check

---

## 🔧 Diagnostic Sensors (Already Existing)

### WiFi Signal Strength
**Entity:** `sensor.sprinkler_rssi`
**Value:** dBm (e.g., -45 dBm)
**Note:** Disabled by default, enable if needed

### IP Address
**Entity:** `sensor.sprinkler_ip_address`
**Value:** Local IP (e.g., 192.168.1.100)
**Note:** Disabled by default

### WiFi Network
**Entity:** `sensor.sprinkler_ssid`
**Value:** WiFi network name
**Note:** Disabled by default

---

## 💡 Automation Ideas

### 1. Smart Watering Based on Soil Moisture
```yaml
automation:
  - alias: "Smart watering - only if dry"
    trigger:
      - platform: time
        at: "06:00:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.sprinkler_zone_1_soil_moisture
        below: 30
    action:
      - service: button.press
        target:
          entity_id: button.sprinkler_zone_1
```

### 2. Notify When Watering Starts
```yaml
automation:
  - alias: "Watering notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.sprinkler_zone_1_running
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Sprinkler Alert"
          message: "Zone 1 is now watering for {{ states('sensor.sprinkler_zone_1_remaining_time') }} minutes"
```

### 3. Dashboard Warning for Low Soil Moisture
```yaml
automation:
  - alias: "Low soil moisture alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sprinkler_zone_1_soil_moisture
        below: 20
        for: "06:00:00"  # Stable for 6 hours
    action:
      - service: persistent_notification.create
        data:
          title: "Low Soil Moisture"
          message: "Zone 1 soil moisture is {{ states('sensor.sprinkler_zone_1_soil_moisture') }}%. Consider watering soon."
```

### 4. Prevent Lawn Mowing During Watering
```yaml
automation:
  - alias: "Pause robot mower when watering"
    trigger:
      - platform: state
        entity_id: binary_sensor.sprinkler_zone_2_running
        to: "on"
    action:
      - service: vacuum.pause
        target:
          entity_id: vacuum.lawn_mower
```

### 5. Track Watering History
```yaml
automation:
  - alias: "Log watering events"
    trigger:
      - platform: state
        entity_id: binary_sensor.sprinkler_zone_1_running
        to: "off"
        from: "on"
    action:
      - service: logbook.log
        data:
          name: "Sprinkler System"
          message: "Zone 1 completed watering"
```

---

## 📊 Dashboard Examples

### Simple Status Card
```yaml
type: entities
title: Sprinkler Status
entities:
  - entity: sensor.sprinkler_current_zone
    name: Currently Running
  - entity: sensor.sprinkler_next_scheduled_run
    name: Next Scheduled
  - entity: sensor.sprinkler_active_schedules
    name: Active Schedules
```

### Zone Monitoring Card
```yaml
type: entities
title: Zone 1 - Sidewalk
entities:
  - entity: binary_sensor.sprinkler_zone_1_running
    name: Status
  - entity: sensor.sprinkler_zone_1_remaining_time
    name: Time Remaining
  - entity: sensor.sprinkler_zone_1_soil_moisture
    name: Soil Moisture
  - entity: sensor.sprinkler_zone_1_last_watered
    name: Last Watered
  - type: divider
  - entity: button.sprinkler_zone_1
    name: Start Watering
  - entity: number.sprinkler_zone_1
    name: Duration
```

### Soil Moisture Gauge
```yaml
type: gauge
entity: sensor.sprinkler_zone_1_soil_moisture
name: Zone 1 Soil Moisture
min: 0
max: 100
needle: true
severity:
  red: 0
  yellow: 20
  green: 50
```

### All Zones Overview
```yaml
type: grid
cards:
  - type: sensor
    entity: sensor.sprinkler_zone_1_soil_moisture
    name: Zone 1
    graph: line
  - type: sensor
    entity: sensor.sprinkler_zone_2_soil_moisture
    name: Zone 2
    graph: line
  - type: sensor
    entity: sensor.sprinkler_zone_3_soil_moisture
    name: Zone 3
    graph: line
```

---

## ⚙️ Configuration Tips

### Enable Diagnostic Sensors
1. Go to **Settings** → **Devices & Services** → **Wyze**
2. Click on your Sprinkler Controller
3. Find disabled entities (weather delays, RSSI, IP, SSID)
4. Click entity → Enable

### Customize Entity Names
```yaml
# configuration.yaml
homeassistant:
  customize:
    sensor.sprinkler_zone_1_soil_moisture:
      friendly_name: "Front Lawn Moisture"
      icon: mdi:grass
```

### Create Groups
```yaml
# configuration.yaml
group:
  front_yard_zones:
    name: Front Yard Sprinklers
    entities:
      - binary_sensor.sprinkler_zone_1_running
      - binary_sensor.sprinkler_zone_2_running
      - button.sprinkler_zone_1
      - button.sprinkler_zone_2
```

---

## 🐛 Troubleshooting

### Sensors Show "Unknown" or "Unavailable"
**Reason:** wyzeapy library not yet updated with new API methods
**Solution:** Wait for wyzeapy update or manually update the library
**Status:** See WYZEAPY_IRRIGATION_API_REQUIREMENTS.md

### Soil Moisture Not Updating
**Reason:** Wyze calculates soil moisture overnight
**Solution:** Check again after 24 hours, values update daily

### Weather Delays Not Working
**Reason:** May require schedule to be configured in Wyze app
**Solution:** Ensure schedule has weather delay features enabled

### Zone Running Status Always Off
**Reason:** Requires real-time schedule monitoring from wyzeapy
**Solution:** Will work automatically once wyzeapy library is updated

---

## 📚 More Information

- **API Documentation:** `wyze_sprinkler_api_documentation.md`
- **Implementation Details:** `IMPLEMENTATION_SUMMARY.md`
- **Library Requirements:** `WYZEAPY_IRRIGATION_API_REQUIREMENTS.md`
- **GitHub Issue:** [#230](https://github.com/SecKatie/ha-wyzeapi/issues/230)

---

## 🎯 Quick Start Checklist

- [ ] Ensure ha-wyzeapi is updated to latest version
- [ ] Restart Home Assistant
- [ ] Verify new sensor entities appear
- [ ] Enable diagnostic sensors if desired
- [ ] Create dashboard cards for monitoring
- [ ] Set up automations for smart watering
- [ ] Enjoy comprehensive sprinkler control! 🌿

---

**Need Help?** Open an issue at https://github.com/SecKatie/ha-wyzeapi/issues
