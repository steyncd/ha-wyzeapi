# Entity Update Fix - Dispatcher Pattern Implementation

## Problem Identified

The irrigation entities were not updating because **multiple entities were overwriting each other's callback functions**.

### Root Cause

When multiple entities share the same device object, each entity was calling:
```python
self._device.callback_function = self.async_update_callback
```

This meant:
- Entity 1 registers: `device.callback_function = entity1.callback`
- Entity 2 registers: `device.callback_function = entity2.callback` ← **OVERWRITES Entity 1!**
- Entity 3 registers: `device.callback_function = entity3.callback` ← **OVERWRITES Entity 2!**
- ... and so on

**Result:** Only the LAST entity registered would receive updates. All other 37+ entities would never update.

---

## Solution: Dispatcher Pattern

Implemented Home Assistant's **dispatcher pattern** to broadcast updates to all entities listening to a device.

### How It Works

1. **Single Callback Registration**
   - Only ONE callback function is registered per device (checked via `hasattr`)
   - This callback dispatches updates to ALL entities

2. **Dispatcher Broadcasts**
   - When device updates, callback sends: `async_dispatcher_send(hass, f"IRRIGATION_UPDATED-{mac}", device)`
   - ALL entities listening receive the update

3. **Entity Subscriptions**
   - Each entity subscribes: `async_dispatcher_connect(hass, f"IRRIGATION_UPDATED-{mac}", handler)`
   - Entities receive updates independently without interfering

---

## Files Modified

### 1. [const.py](custom_components/wyzeapi/const.py)
**Added:**
```python
IRRIGATION_UPDATED = f"{DOMAIN}.irrigation_updated"
```

### 2. [sensor.py](custom_components/wyzeapi/sensor.py)
**Changes:**
- Added `IRRIGATION_UPDATED` import
- Added `async_dispatcher_send` import
- Updated `WyzeIrrigationBaseSensor.async_added_to_hass()`:
  - Changed from direct callback to dispatcher subscription
  - Added registration check to prevent duplicate updaters
  - Wrapped callback to dispatch to all entities
- Updated `WyzeIrrigationZoneBaseSensor` with same pattern

**Before:**
```python
async def async_added_to_hass(self) -> None:
    self._device.callback_function = self.async_update_callback  # ← OVERWRITES!
    self._irrigation_service.register_updater(self._device, 30)
    await self._irrigation_service.start_update_manager()
```

**After:**
```python
async def async_added_to_hass(self) -> None:
    # Subscribe to dispatcher
    self.async_on_remove(
        async_dispatcher_connect(
            self.hass,
            f"{IRRIGATION_UPDATED}-{self._device.mac}",
            self.handle_irrigation_update,
        )
    )

    # Register updater ONCE per device
    if not hasattr(self._irrigation_service, f"_updater_registered_{self._device.mac}"):
        setattr(self._irrigation_service, f"_updater_registered_{self._device.mac}", True)

        def callback_wrapper(irrigation: Irrigation):
            """Broadcast to all entities."""
            async_dispatcher_send(self.hass, f"{IRRIGATION_UPDATED}-{self._device.mac}", irrigation)

        self._device.callback_function = callback_wrapper
        self._irrigation_service.register_updater(self._device, 30)
        await self._irrigation_service.start_update_manager()
```

### 3. [binary_sensor.py](custom_components/wyzeapi/binary_sensor.py)
**Changes:**
- Added `IRRIGATION_UPDATED` import
- Added dispatcher imports
- Updated `WyzeIrrigationBaseBinarySensor.async_added_to_hass()` with dispatcher pattern
- Updated `WyzeIrrigationZoneRunning.async_added_to_hass()` with dispatcher pattern

---

## Update Flow (After Fix)

### Initialization
```
1. Entity 1 adds itself
   ├─ Subscribes to dispatcher: IRRIGATION_UPDATED-{mac}
   ├─ Checks: No updater registered yet
   └─ Registers updater with callback wrapper

2. Entity 2 adds itself
   ├─ Subscribes to dispatcher: IRRIGATION_UPDATED-{mac}
   ├─ Checks: Updater already registered
   └─ Skips registration (reuses existing)

3. Entity 3-38 add themselves
   ├─ Each subscribes to dispatcher: IRRIGATION_UPDATED-{mac}
   └─ Each skips updater registration (already exists)
```

### Runtime Updates (Every 30 seconds)
```
1. Updater calls device.callback_function(irrigation_device)
   ↓
2. callback_wrapper receives update
   ↓
3. Dispatches: async_dispatcher_send("IRRIGATION_UPDATED-{mac}", device)
   ↓
4. ALL 38 entities receive update simultaneously
   ├─ Entity 1: Updates state
   ├─ Entity 2: Updates state
   ├─ Entity 3: Updates state
   └─ ... all entities update
```

---

## Benefits

✅ **All entities update** - No more callback overwrites
✅ **Efficient** - Only one API poll per device (not per entity)
✅ **Scalable** - Works with any number of entities
✅ **Standard pattern** - Same approach used by locks, cameras, etc.
✅ **Clean lifecycle** - Proper subscription cleanup on entity removal

---

## Testing Checklist

After restarting Home Assistant:

- [ ] All irrigation sensors appear
- [ ] Sensors update every 30 seconds
- [ ] Check Home Assistant logs for dispatcher messages
- [ ] Verify no "callback overwrite" issues
- [ ] Test with multiple zones enabled
- [ ] Monitor for 5+ minutes to confirm continuous updates

### Debug Logging

Add to `configuration.yaml` to verify dispatcher activity:
```yaml
logger:
  default: info
  logs:
    custom_components.wyzeapi.sensor: debug
    custom_components.wyzeapi.binary_sensor: debug
```

Look for:
- "Registering updater for device {mac}"
- Dispatcher send/receive messages
- Entity state update confirmations

---

## Performance Impact

**Before Fix:**
- 38 entities × 1 registration attempt = 38 callback registrations
- Result: 37 overwrites, 1 working entity
- API Calls: 1 per 30 seconds per device ✅ (unchanged)

**After Fix:**
- 38 entities × 1 dispatcher subscription = 38 listeners
- 1 updater registration per device
- All 38 entities receive updates
- API Calls: 1 per 30 seconds per device ✅ (unchanged)

**Conclusion:** Same API load, all entities now functional!

---

## Comparison with Other Device Types

| Device Type | Update Pattern | Entities per Device |
|-------------|----------------|---------------------|
| Locks | Dispatcher | ~10 entities |
| Cameras | Dispatcher | ~5 entities |
| **Irrigation (Before)** | ❌ Direct callback (broken) | **38+ entities** |
| **Irrigation (After)** | ✅ Dispatcher (fixed) | **38+ entities** |
| Thermostats | Direct callback | 1 entity (works fine) |
| Lights | Direct callback | 1 entity (works fine) |

**Key Insight:** Direct callback works fine for single-entity devices, but multi-entity devices MUST use dispatcher pattern.

---

## Future Improvements

1. **Dynamic Polling Rate**
   - Poll every 15 seconds when zones are running
   - Poll every 60 seconds when idle
   - Reduces API load by ~50% during idle periods

2. **Shared Update Manager**
   - Consider creating a singleton update manager per device type
   - Prevents hasattr checks and service attribute manipulation

3. **Entity Availability**
   - Add availability based on last update timestamp
   - Mark entities unavailable if no update in >2 minutes

---

## Related Documentation

- **Implementation Summary:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Feature Guide:** [IRRIGATION_FEATURES.md](IRRIGATION_FEATURES.md)
- **API Requirements:** [WYZEAPY_IRRIGATION_API_REQUIREMENTS.md](WYZEAPY_IRRIGATION_API_REQUIREMENTS.md)

---

## Conclusion

The dispatcher pattern fix ensures **all 38+ irrigation entities update simultaneously** every 30 seconds, without interfering with each other. This is the standard Home Assistant approach for devices with multiple entities and is now properly implemented for irrigation devices.

**Status:** ✅ Fixed and ready for testing!
