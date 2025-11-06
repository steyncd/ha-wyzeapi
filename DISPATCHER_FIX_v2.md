# Dispatcher Fix - Version 2

## Additional Fix Applied

Added `@callback` decorator to the callback_wrapper function to ensure it runs in Home Assistant's event loop context.

### The Issue

The `async_dispatcher_send` was being called from a regular function instead of a callback-decorated function, which could cause it to not execute properly.

### The Fix

**Before:**
```python
def callback_wrapper(irrigation: Irrigation):
    """Wrapper to dispatch updates to all entities."""
    async_dispatcher_send(self.hass, f"{IRRIGATION_UPDATED}-{self._device.mac}", irrigation)
```

**After:**
```python
@callback
def callback_wrapper(irrigation: Irrigation):
    """Wrapper to dispatch updates to all entities."""
    async_dispatcher_send(self.hass, f"{IRRIGATION_UPDATED}-{self._device.mac}", irrigation)
```

### Why This Matters

The `@callback` decorator tells Home Assistant that this function should be run in the event loop context, which is required for dispatcher operations to work correctly.

---

## Current Status Check

After this fix, **restart Home Assistant** and check:

### 1. Are entities updating at all?
Check the diagnostic sensors that already work:
- `sensor.sprinkler_rssi` (WiFi signal)
- `sensor.sprinkler_ip_address`
- `sensor.sprinkler_ssid`

**If these ARE updating:** The dispatcher is working! ✅

**If these are NOT updating:** There's a deeper issue with the updater registration.

### 2. What values do you see?

For the new sensors, you'll likely see:
- `sensor.sprinkler_current_zone`: "Idle" (default value)
- `sensor.sprinkler_zone_1_remaining_time`: 0 (default value)
- `sensor.sprinkler_zone_1_soil_moisture`: "unknown" (no data yet)
- `binary_sensor.sprinkler_zone_1_running`: Off (default value)

**This is EXPECTED** because the wyzeapy library doesn't provide this data yet!

---

## Debug: Enable Logging

Add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.wyzeapi.sensor: debug
    custom_components.wyzeapi.binary_sensor: debug
```

Restart Home Assistant and look for:
1. "Registering updater for device..." messages
2. Dispatcher send/receive activity
3. Entity state update calls

---

## What's Actually Updating?

### ✅ Should Update (Data Available from wyzeapy):
- RSSI (WiFi signal strength)
- IP Address
- SSID
- Zone names
- Zone enabled status

### ❌ Won't Update Yet (Requires wyzeapy library changes):
- **Running status** - Needs `zone.is_running` from API
- **Remaining time** - Needs `zone.remaining_time` from API
- **Soil moisture** - Needs `zone.soil_moisture_level_at_end_of_day_pct` from API
- **Current zone** - Needs `device.current_running_zone` from API
- **Schedule info** - Needs schedule API calls
- **Weather delays** - Needs schedule configuration API

---

## How to Tell if Dispatcher is Working

### Test Method 1: Check Diagnostic Sensors
1. Go to Developer Tools → States
2. Find `sensor.sprinkler_rssi`
3. Note the timestamp
4. Wait 30-60 seconds
5. Refresh and check if timestamp updated

**If timestamp updates**: Dispatcher is working! ✅

### Test Method 2: Check Logs
With debug logging enabled, you should see every 30 seconds:
```
DEBUG (MainThread) [custom_components.wyzeapi.sensor] Irrigation update received for device XX:XX:XX
DEBUG (MainThread) [custom_components.wyzeapi.sensor] Updating entity sensor.sprinkler_rssi
```

### Test Method 3: Add a Test Attribute
Temporarily add this to `WyzeIrrigationRSSI.extra_state_attributes`:
```python
@property
def extra_state_attributes(self) -> dict:
    return {
        "last_update": datetime.now().isoformat(),
    }
```

Check if this timestamp updates every 30 seconds.

---

## Expected Behavior After Full wyzeapy Update

Once the wyzeapy library is updated with the new API calls:

**Every 30 seconds, the updater will:**
1. Call Wyze API to get device status
2. Parse zone running status
3. Calculate remaining time
4. Get soil moisture data
5. Get schedule information
6. Fire callback_wrapper with updated device
7. callback_wrapper dispatches to all 38+ entities
8. Each entity receives update and refreshes its state

**Result:** All sensors show real-time data!

---

## Troubleshooting

### Issue: No entities updating at all
**Solution:** Check that binary_sensor is in PLATFORMS list in __init__.py (it is)

### Issue: Only first entity updates
**Solution:** This was the original problem - fixed with dispatcher pattern

### Issue: Entities show "unknown"
**Solution:** This is expected! wyzeapy library needs to provide the data first

### Issue: Entities show default values (0, "Idle", Off)
**Solution:** Working as designed! The hasattr checks return defaults when data is missing

---

## Next Steps

1. **Restart Home Assistant** with the `@callback` fix
2. **Verify dispatcher is working** using diagnostic sensors
3. **Wait for wyzeapy library update** with new API methods
4. **Test with real data** once wyzeapy is updated

The infrastructure is now complete and ready - we're just waiting for the wyzeapy library to provide the actual data!
