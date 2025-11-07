#!/usr/bin/env python3
"""Test script to verify wyzeapy zone properties are being set correctly."""

import asyncio
import sys
import os

# Add the local wyzeapy to path if testing locally
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from wyzeapy import Wyzeapy
from wyzeapy.services.irrigation_service import IrrigationService

# Your credentials
USERNAME = "steyncd@gmail.com"
PASSWORD = "Dobby.1021"
KEY_ID = "02e46f64-3b3e-43cf-8d7a-9a7499a6b32d"
API_KEY = "TaJE8u99R9Li6hnR6euf7pQFh6IshaOOAlI2EVWaqW4gJQqenAJ9kf6T9L8d"

async def test_zone_properties():
    """Test that zone properties are being updated correctly."""

    print("=" * 60)
    print("Testing wyzeapy Zone Properties")
    print("=" * 60)

    # Create client
    client = await Wyzeapy.create()
    await client.login(USERNAME, PASSWORD, KEY_ID, API_KEY)

    # Get irrigation service
    irrigation_service: IrrigationService = await client.irrigation_service

    # Get devices
    devices = await irrigation_service.get_irrigations()

    if not devices:
        print("[ERROR] No irrigation devices found!")
        return

    device = devices[0]
    print(f"\n[OK] Found device: {device.nickname} ({device.mac})")
    print(f"   Model: {device.product_model}")

    # Initial state
    print("\n" + "=" * 60)
    print("INITIAL STATE (before update)")
    print("=" * 60)

    for zone in device.zones:
        print(f"\nZone {zone.zone_number}: {zone.name}")
        print(f"  - Enabled: {zone.enabled}")
        print(f"  - Smart Duration: {zone.smart_duration} seconds")

        # Check if properties exist
        has_is_running = hasattr(zone, 'is_running')
        has_remaining_time = hasattr(zone, 'remaining_time')

        print(f"  - has 'is_running' property: {has_is_running}")
        print(f"  - has 'remaining_time' property: {has_remaining_time}")

        if has_is_running:
            print(f"  - is_running value: {zone.is_running}")
        if has_remaining_time:
            print(f"  - remaining_time value: {zone.remaining_time}")

    # Call update
    print("\n" + "=" * 60)
    print("CALLING irrigation_service.update()...")
    print("=" * 60)

    device = await irrigation_service.update(device)

    print("\n[OK] Update complete!")

    # After update state
    print("\n" + "=" * 60)
    print("AFTER UPDATE")
    print("=" * 60)

    for zone in device.zones:
        print(f"\nZone {zone.zone_number}: {zone.name}")
        print(f"  - Enabled: {zone.enabled}")
        print(f"  - Smart Duration: {zone.smart_duration} seconds")

        # Check if properties exist
        has_is_running = hasattr(zone, 'is_running')
        has_remaining_time = hasattr(zone, 'remaining_time')

        print(f"  - has 'is_running' property: {has_is_running}")
        print(f"  - has 'remaining_time' property: {has_remaining_time}")

        if has_is_running:
            is_running = zone.is_running
            print(f"  - is_running value: {is_running}")
            if is_running:
                print(f"  [WARNING]  ZONE IS RUNNING!")

        if has_remaining_time:
            remaining = zone.remaining_time
            print(f"  - remaining_time value: {remaining} seconds")
            if remaining > 0:
                print(f"  [WARNING]  Time remaining: {remaining // 60} minutes, {remaining % 60} seconds")

    # Test schedule_runs directly
    print("\n" + "=" * 60)
    print("TESTING schedule_runs API DIRECTLY")
    print("=" * 60)

    try:
        schedule_data = await irrigation_service.get_schedule_runs(device, limit=5)
        schedules = schedule_data.get('data', {}).get('schedules', [])

        print(f"\n[OK] Found {len(schedules)} schedules")

        for idx, schedule in enumerate(schedules):
            state = schedule.get('schedule_state')
            print(f"\nSchedule {idx + 1}:")
            print(f"  - State: {state}")
            print(f"  - Start: {schedule.get('start_utc')}")
            print(f"  - End: {schedule.get('end_utc')}")

            if state == 'running':
                print(f"  [WARNING]  RUNNING SCHEDULE FOUND!")
                zone_runs = schedule.get('zone_runs', [])
                for zone_run in zone_runs:
                    print(f"    Zone {zone_run.get('zone_number')}: {zone_run.get('start_utc')} -> {zone_run.get('end_utc')}")

    except Exception as e:
        print(f"[ERROR] Error calling get_schedule_runs: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_zone_properties())
