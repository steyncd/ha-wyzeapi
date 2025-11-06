# Irrigation README Section

**Suggested addition to the main README.md file**

---

## 🌿 Wyze Sprinkler Controller

Comprehensive support for Wyze Sprinkler Controllers with advanced monitoring and control features.

### Features

#### Control Features
- ✅ **Zone Start Buttons** - Start individual zones with custom durations
- ✅ **Stop All Button** - Emergency stop for all running zones
- ✅ **Duration Settings** - Configure watering time per zone (1-180 minutes)

#### Monitoring Features (New!)
- 🌱 **Soil Moisture Sensors** - Wyze's AI-calculated soil moisture per zone (0-100%)
- 🧠 **Smart Duration** - AI-recommended watering times based on weather and soil
- ⏱️ **Running Status** - Real-time zone status and remaining time
- 📅 **Schedule Tracking** - View upcoming and past watering schedules
- 🕐 **Watering History** - Last watered timestamp and duration per zone
- 🌦️ **Weather Delays** - Rain, wind, freeze, and saturation skip notifications
- 📊 **Zone Configuration** - Detailed zone properties (soil type, crop type, nozzle type, area, etc.)

### Entity Count

For an 8-zone controller with 6 enabled zones, you'll get:
- **7 Buttons** (6 zone starts + 1 stop all)
- **6 Number inputs** (duration settings)
- **30 Sensors** (status, soil moisture, schedules, history)
- **10 Binary sensors** (running status, weather delays)

**Total: ~53 entities** for comprehensive irrigation management!

### Quick Example

```yaml
# Automation: Smart watering based on soil moisture
automation:
  - alias: "Smart Water Zone 1"
    trigger:
      platform: time
      at: "06:00:00"
    condition:
      condition: numeric_state
      entity_id: sensor.sprinkler_zone_1_soil_moisture
      below: 30
    action:
      service: button.press
      target:
        entity_id: button.sprinkler_zone_1
```

### Dashboard Example

```yaml
type: entities
title: Sprinkler System
entities:
  - entity: sensor.sprinkler_current_zone
  - entity: sensor.sprinkler_next_scheduled_run
  - entity: sensor.sprinkler_zone_1_soil_moisture
  - entity: binary_sensor.sprinkler_zone_1_running
  - entity: button.sprinkler_zone_1
  - entity: number.sprinkler_zone_1
```

### Documentation
- **Feature Guide:** [IRRIGATION_FEATURES.md](IRRIGATION_FEATURES.md) - User guide with automation examples
- **API Reference:** [wyze_sprinkler_api_documentation.md](wyze_sprinkler_api_documentation.md) - Complete API documentation
- **Implementation:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details

### Requirements

**Note:** Advanced features (soil moisture, running status, schedules) require updates to the `wyzeapy` library. See [WYZEAPY_IRRIGATION_API_REQUIREMENTS.md](WYZEAPY_IRRIGATION_API_REQUIREMENTS.md) for details. Basic control features (start/stop zones) work immediately.

### Supported Models
- Wyze Sprinkler Controller (WSPRK1)
- All zone configurations (1-8 zones)

---

**Key Highlight:** The soil moisture sensor provides Wyze's proprietary AI-calculated moisture percentage based on weather data, watering history, soil properties, and crop types - data that's not available from any other source! 🌱
