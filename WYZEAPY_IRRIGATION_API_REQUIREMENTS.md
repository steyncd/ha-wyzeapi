# WyzeaPy Library - Irrigation Service API Requirements

This document outlines the required additions to the `wyzeapy` library's `IrrigationService` class to support the enhanced irrigation features implemented in ha-wyzeapi.

## Overview

The ha-wyzeapi integration has been enhanced with comprehensive irrigation monitoring and control features based on the reverse-engineered Wyze Sprinkler Controller API. To fully enable these features, the following properties and methods need to be added to the wyzeapy library.

## Reference Documentation

See `wyze_sprinkler_api_documentation.md` for complete API endpoint documentation including:
- Request/response formats
- Authentication requirements
- Field descriptions
- Example payloads

## Required Changes to wyzeapy Library

### 1. Irrigation Device Class Additions

The `Irrigation` class needs the following new properties:

```python
class Irrigation:
    # ... existing properties ...

    # Schedule tracking properties
    current_running_zone: Optional[str] = None
    next_scheduled_run: Optional[datetime] = None
    next_schedule_name: Optional[str] = None
    next_schedule_zones: Optional[List[str]] = None
    active_schedules_count: int = 0
    schedule_list: Optional[List[dict]] = None

    # Last run tracking
    last_run_duration: int = 0  # seconds
    last_run_zones: Optional[List[str]] = None
    last_run_end_time: Optional[datetime] = None

    # Weather delay status
    rain_delay_active: bool = False
    wind_delay_active: bool = False
    freeze_delay_active: bool = False
    saturation_delay_active: bool = False
```

### 2. Zone Class Additions

The `Zone` class needs the following new properties:

```python
class Zone:
    # ... existing properties ...

    # Running status
    is_running: bool = False
    remaining_time: int = 0  # seconds

    # Soil moisture data (from GET /plugin/irrigation/zone endpoint)
    soil_moisture_level_at_end_of_day_pct: Optional[float] = None  # 0-1 scale

    # Zone configuration details
    area: Optional[float] = None  # square feet
    crop_type: Optional[str] = None  # e.g., "COOL_SEASON_GRASS"
    soil_type: Optional[str] = None  # e.g., "CLAY", "LOAM", "SAND"
    slope_type: Optional[str] = None  # e.g., "FLAT", "SLIGHT", "MODERATE", "STEEP"
    exposure_type: Optional[str] = None  # e.g., "FULL_SUN", "SOME_SHADE", "LOTS_OF_SHADE"
    nozzle_type: Optional[str] = None  # e.g., "ROTOR_HEAD", "SPRAY_HEAD", "DRIP"
    flow_rate: Optional[float] = None  # gallons per minute
    efficiency: Optional[float] = None  # percentage
    root_depth: Optional[float] = None  # inches

    # Smart watering
    smart_duration: Optional[int] = None  # seconds (AI-calculated)
    available_water_capacity: Optional[float] = None
    manage_allow_depletion: Optional[float] = None

    # Watering history
    last_watered_time: Optional[datetime] = None
    last_watered_duration: Optional[int] = None  # seconds
    last_schedule_name: Optional[str] = None
    latest_events: Optional[List[dict]] = None  # Recent watering events
```

### 3. IrrigationService Method Additions

Add the following methods to the `IrrigationService` class:

#### 3.1 Get Schedule Runs (History & Upcoming)

```python
async def get_schedule_runs(self, device: Irrigation, limit: int = 10) -> dict:
    """
    Get recent watering history and upcoming scheduled runs.

    API Endpoint: GET /plugin/irrigation/schedule_runs

    Args:
        device: The irrigation device
        limit: Number of records to return (default 10)

    Returns:
        dict: Response containing schedules array with past and upcoming runs

    Response Structure:
        {
            "schedules": [
                {
                    "schedule_id": str,
                    "schedule_name": str,
                    "schedule_type": str,  # "MANUAL" or "FIXED"
                    "schedule_state": str,  # "past", "running", "upcoming"
                    "start_local": str,  # ISO timestamp
                    "end_local": str,
                    "duration": int,  # seconds
                    "zone_count": int,
                    "zone_runs": [...]
                }
            ]
        }
    """
    nonce = str(int(time.time() * 1000))
    url = f"https://wyze-lockwood-service.wyzecam.com/plugin/irrigation/schedule_runs"
    params = {
        "device_id": device.device_id,
        "limit": limit,
        "nonce": nonce
    }
    # Implementation details...
```

#### 3.2 Get All Schedules (Configuration)

```python
async def get_schedules(self, device: Irrigation) -> dict:
    """
    Get complete list of all configured schedules with full settings.

    API Endpoint: GET /plugin/irrigation/schedule

    Args:
        device: The irrigation device

    Returns:
        dict: Response containing schedules array with full configuration

    Response Structure:
        {
            "schedules": [
                {
                    "schedule_id": str,
                    "schedule_type": str,  # "FIXED" or "SMART"
                    "name": str,
                    "enabled": bool,
                    "start_date": str,
                    "end_date": str,
                    "run_days": {...},
                    "run_times": {...},
                    "cycle_soak": bool,
                    "rain_delay_enabled": bool,
                    "wind_delay_enabled": bool,
                    "freeze_delay_enabled": bool,
                    "saturation_delay_enabled": bool,
                    "zone_info": [...]
                }
            ]
        }
    """
    nonce = str(int(time.time() * 1000))
    url = f"https://wyze-lockwood-service.wyzecam.com/plugin/irrigation/schedule"
    params = {
        "device_id": device.device_id,
        "nonce": nonce
    }
    # Implementation details...
```

#### 3.3 Get Zone Details

```python
async def get_zone_details(self, device: Irrigation) -> dict:
    """
    Get comprehensive zone information including soil moisture, history, and settings.

    API Endpoint: GET /plugin/irrigation/zone

    Args:
        device: The irrigation device

    Returns:
        dict: Response containing zones array with detailed information

    Response Structure:
        {
            "zones": [
                {
                    "zone_number": int,
                    "zone_id": str,
                    "name": str,
                    "enabled": bool,
                    "wired": bool,
                    "area": float,
                    "soil_moisture_level_at_end_of_day_pct": float,  # 0-1 scale
                    "crop_type": str,
                    "soil_type": str,
                    "slope_type": str,
                    "exposure_type": str,
                    "nozzle_type": str,
                    "flow_rate": float,
                    "efficiency": float,
                    "root_depth": float,
                    "smart_duration": int,
                    "latest_events": [...]
                }
            ]
        }
    """
    nonce = str(int(time.time() * 1000))
    url = f"https://wyze-lockwood-service.wyzecam.com/plugin/irrigation/zone"
    params = {
        "device_id": device.device_id,
        "nonce": nonce
    }
    # Implementation details...
```

#### 3.4 Enhanced Update Method

Enhance the existing `update()` method to populate the new properties:

```python
async def update(self, device: Irrigation) -> Irrigation:
    """
    Update device with comprehensive status including zones, schedules, and weather delays.

    This should call:
    1. Existing device update logic
    2. get_zone_details() to populate zone properties
    3. get_schedule_runs() to populate schedule tracking
    4. get_schedules() to populate weather delay status
    """
    # Existing update logic...

    # Get zone details including soil moisture
    zone_details = await self.get_zone_details(device)
    if zone_details and "zones" in zone_details.get("data", {}):
        for zone_data in zone_details["data"]["zones"]:
            zone_number = zone_data["zone_number"]
            for zone in device.zones:
                if zone.zone_number == zone_number:
                    # Populate zone properties
                    zone.soil_moisture_level_at_end_of_day_pct = zone_data.get("soil_moisture_level_at_end_of_day_pct")
                    zone.area = zone_data.get("area")
                    zone.crop_type = zone_data.get("crop_type")
                    zone.soil_type = zone_data.get("soil_type")
                    zone.slope_type = zone_data.get("slope_type")
                    zone.exposure_type = zone_data.get("exposure_type")
                    zone.nozzle_type = zone_data.get("nozzle_type")
                    zone.flow_rate = zone_data.get("flow_rate")
                    zone.efficiency = zone_data.get("efficiency")
                    zone.root_depth = zone_data.get("root_depth")
                    zone.smart_duration = zone_data.get("smart_duration")

                    # Process latest events for watering history
                    latest_events = zone_data.get("latest_events", [])
                    if latest_events:
                        zone.latest_events = latest_events
                        most_recent = latest_events[0]
                        zone.last_watered_time = datetime.fromisoformat(most_recent["end_local"])
                        zone.last_watered_duration = most_recent["duration"]
                        zone.last_schedule_name = most_recent["schedule_name"]

    # Get schedule runs to determine running status
    schedule_runs = await self.get_schedule_runs(device, limit=5)
    if schedule_runs and "schedules" in schedule_runs.get("data", {}):
        schedules = schedule_runs["data"]["schedules"]

        # Check for currently running zones
        for schedule in schedules:
            if schedule.get("schedule_state") == "running":
                device.current_running_zone = schedule["zone_runs"][0]["zone_name"] if schedule.get("zone_runs") else None
                # Update zone running status
                for zone_run in schedule.get("zone_runs", []):
                    zone_number = zone_run["zone_number"]
                    for zone in device.zones:
                        if zone.zone_number == zone_number:
                            zone.is_running = True
                            # Calculate remaining time if available
                            # (requires comparing current time to end_utc)

            # Find next upcoming schedule
            elif schedule.get("schedule_state") == "upcoming":
                if device.next_scheduled_run is None:
                    device.next_scheduled_run = datetime.fromisoformat(schedule["start_utc"].replace("Z", "+00:00"))
                    device.next_schedule_name = schedule["schedule_name"]
                    device.next_schedule_zones = [zr["zone_name"] for zr in schedule.get("zone_runs", [])]

            # Track last completed run
            elif schedule.get("schedule_state") == "past":
                if device.last_run_duration == 0:  # First past schedule is most recent
                    device.last_run_duration = schedule["duration"]
                    device.last_run_zones = [zr["zone_name"] for zr in schedule.get("zone_runs", [])]
                    device.last_run_end_time = datetime.fromisoformat(schedule["end_utc"].replace("Z", "+00:00"))

    # Get schedules to check weather delays
    schedules_config = await self.get_schedules(device)
    if schedules_config and "schedules" in schedules_config.get("data", {}):
        schedules = schedules_config["data"]["schedules"]
        device.active_schedules_count = sum(1 for s in schedules if s.get("enabled", False))
        device.schedule_list = [{"name": s["name"], "enabled": s["enabled"]} for s in schedules]

        # Check if any weather delays are currently preventing watering
        # This would require additional API calls or logic to determine active delays
        # For now, we expose the settings but actual active status needs more investigation

    return device
```

## API Implementation Notes

### Authentication Headers

All API calls require these headers (already implemented in wyzeapy):

```python
headers = {
    "Content-Type": "application/json",
    "appid": "BSSC_83d270f3a6124d87",
    "appinfo": "wyze_ios_3.8.5.11",
    "appversion": "3.8.5.11",
    "env": "prod",
    "access_token": self.token,
    "signature2": self._calculate_signature(...),
    "phoneid": self.phone_id,
    "requestid": str(uuid.uuid4()),
}
```

### Base URL

```
https://wyze-lockwood-service.wyzecam.com
```

### Polling Frequency

- Recommended: 30 seconds (current implementation)
- When zones are running: Consider reducing to 15 seconds for better responsiveness
- When idle: Can increase to 60 seconds to reduce API load

## Implementation Priority

### Phase 1: Critical Features (Immediate Value)
1. ✅ **get_zone_details()** - Enables soil moisture sensors (unique feature!)
2. ✅ **Update Zone class** - Add soil moisture and configuration properties
3. ✅ **get_schedule_runs()** - Enables running status and remaining time

### Phase 2: Enhanced Monitoring
4. ✅ **get_schedules()** - Enables weather delay sensors
5. ✅ **Update Irrigation class** - Add schedule tracking properties
6. ✅ **Enhanced update()** - Integrate all new data sources

### Phase 3: Advanced Features (Future)
7. Schedule management (enable/disable schedules)
8. Weather data integration
9. Create/modify schedules programmatically

## Testing Requirements

When implementing in wyzeapy, please test:

1. **Zone Details Parsing**
   - Verify soil moisture percentage conversion (API returns 0-1, display as 0-100%)
   - Handle missing optional fields gracefully
   - Test with different crop types, soil types, nozzle types

2. **Schedule Runs Parsing**
   - Test with running schedules
   - Test with no upcoming schedules
   - Test with multiple zones in one schedule
   - Verify timezone handling (local vs UTC)

3. **Schedule Configuration**
   - Test with multiple schedules (enabled/disabled)
   - Verify weather delay settings parsing
   - Test cycle & soak configuration

4. **Edge Cases**
   - Device offline
   - No zones configured
   - All schedules disabled
   - API rate limiting
   - Authentication token expiration

## Example Usage (After Implementation)

```python
# Get irrigation device
irrigation_service = await client.irrigation_service
devices = await irrigation_service.get_irrigations()
device = devices[0]

# Update with enhanced data
device = await irrigation_service.update(device)

# Access new properties
print(f"Current zone: {device.current_running_zone}")
print(f"Next scheduled: {device.next_scheduled_run}")
print(f"Active schedules: {device.active_schedules_count}")

# Access zone details
for zone in device.zones:
    if zone.enabled:
        print(f"Zone {zone.name}:")
        print(f"  Soil moisture: {zone.soil_moisture_level_at_end_of_day_pct * 100}%")
        print(f"  Smart duration: {zone.smart_duration // 60} minutes")
        print(f"  Last watered: {zone.last_watered_time}")
        print(f"  Crop type: {zone.crop_type}")
        print(f"  Soil type: {zone.soil_type}")
```

## Benefits of These Enhancements

1. **Soil Moisture Monitoring** - Unique Wyze-calculated data not available elsewhere
2. **Running Status** - Know which zones are active and for how long
3. **Schedule Visibility** - See upcoming watering schedules in Home Assistant
4. **Weather Integration** - Understand why watering was skipped
5. **Historical Data** - Track watering history for each zone
6. **Zone Configuration** - Display detailed zone settings and properties

## Related Files in ha-wyzeapi

- `custom_components/wyzeapi/sensor.py` - New sensor entities (lines 626-1020)
- `custom_components/wyzeapi/binary_sensor.py` - New binary sensors (lines 252-485)
- `wyze_sprinkler_api_documentation.md` - Complete API reference

## Questions?

For questions or clarifications on the API endpoints, refer to:
- GitHub Issue: https://github.com/SecKatie/ha-wyzeapi/issues/230
- API Documentation: `wyze_sprinkler_api_documentation.md`
- Contact: steyncd@gmail.com

---

**Note:** Once these additions are made to the wyzeapy library, all the sensor entities in ha-wyzeapi will automatically populate with real data. Currently, they use `getattr()` with defaults to gracefully handle missing properties.
