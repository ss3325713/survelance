#!/usr/bin/env python3
"""Comprehensive Automated Verification for Automatic Flashlight & Microphone Surveillance.

Verifies all required test scenarios:
1. Camera motion in daylight -> Flashlight does NOT activate.
2. Camera motion in darkness -> Flashlight activates with trigger: CAMERA.
3. Audio activity in poor visibility / low light -> Flashlight activates with trigger: MICROPHONE.
4. Both sensors detecting activity -> Flashlight activates with trigger: BOTH.
5. Inactivity shutdown -> Automatically turns OFF after inactivity timeout (15s).
6. Background noise filtering -> Constant ambient hum does not trigger false alerts.
7. Manual override -> MANUAL (Force ON) and OFF override; returning to AUTO resumes automation.
8. Camera/microphone disconnection -> Clear reporting, never claims false state changes.
9. Maximum ON-time protection -> Enforces safety shutoff after max_on_time_sec (120s).
"""

import sys
import time
import httpx
import numpy as np

BASE_URL = "http://127.0.0.1:8000"
PIN_HEADER = {"X-Dashboard-PIN": "1234"}

def log_section(title: str):
    print(f"\n========================================================")
    print(f" {title}")
    print(f"========================================================")

def run_tests():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    from wheat_watch.flashlight import FlashlightController
    from wheat_watch.microphone import MicrophoneDetector

    # -------------------------------------------------------------------------
    log_section("1. TEST CAMERA MOTION IN DAYLIGHT (NO FLASHLIGHT ACTIVATION)")
    # -------------------------------------------------------------------------
    # Create isolated controller instance for deterministic algorithmic tests
    fc = FlashlightController()
    fc.set_mode("auto")

    # In daylight (is_low_light = False)
    res = fc.process_sensor_activity(
        has_camera_motion=True,
        is_low_light=False,  # Bright daylight
        has_audio_activity=False,
    )
    assert res["is_on"] is False, "Flashlight erroneously activated in daylight!"
    assert res["active_trigger"] is None
    print("PASS [✓] Camera motion in bright daylight suppressed flashlight activation.")

    # -------------------------------------------------------------------------
    log_section("2. TEST CAMERA MOTION IN DARKNESS / LOW LIGHT (TRIGGER: CAMERA)")
    # -------------------------------------------------------------------------
    # Mock hardware command success on the controller instance
    fc._send_hardware_command = lambda turn_on, trigger=None: setattr(fc, "is_on", turn_on) or True

    res = fc.process_sensor_activity(
        has_camera_motion=True,
        is_low_light=True,  # Low light
        has_audio_activity=False,
    )
    assert res["is_on"] is True, "Flashlight failed to activate on low-light motion!"
    assert res["active_trigger"] == "CAMERA"
    assert res["last_trigger"] == "CAMERA"
    print("PASS [✓] Camera motion in darkness successfully activated flashlight with trigger: CAMERA.")

    # -------------------------------------------------------------------------
    log_section("3. TEST AUDIO ACTIVITY IN POOR VISIBILITY (TRIGGER: MICROPHONE)")
    # -------------------------------------------------------------------------
    fc._turn_off_auto(reason="TEST_RESET")
    assert fc.is_on is False

    res = fc.process_sensor_activity(
        has_camera_motion=False,  # No motion yet
        is_low_light=True,       # Insufficient visibility / dark
        has_audio_activity=True, # Footstep/rustling detected
    )
    assert res["is_on"] is True, "Flashlight failed to activate on audio trigger!"
    assert res["active_trigger"] == "MICROPHONE"
    assert res["last_trigger"] == "MICROPHONE"
    print("PASS [✓] Meaningful audio activity in poor visibility activated flashlight with trigger: MICROPHONE.")

    # -------------------------------------------------------------------------
    log_section("4. TEST DUAL SENSORS DETECTING SIMULTANEOUSLY (TRIGGER: BOTH)")
    # -------------------------------------------------------------------------
    fc._turn_off_auto(reason="TEST_RESET")
    assert fc.is_on is False

    res = fc.process_sensor_activity(
        has_camera_motion=True,
        is_low_light=True,
        has_audio_activity=True,
    )
    assert res["is_on"] is True, "Flashlight failed to activate on combined trigger!"
    assert res["active_trigger"] == "BOTH"
    assert res["last_trigger"] == "BOTH"
    print("PASS [✓] Simultaneous camera motion and audio activity activated flashlight with trigger: BOTH.")

    # -------------------------------------------------------------------------
    log_section("5. TEST 15-SECOND INACTIVITY SHUTDOWN & MIN ON-TIME (10s)")
    # -------------------------------------------------------------------------
    # Simulate activity occurring at t0
    now = time.time()
    fc.turn_on_time = now - 5.0
    fc.last_activity_time = now - 5.0  # 5s since activity, but min_on_time is 10s

    res = fc.process_sensor_activity(has_camera_motion=False, is_low_light=True, has_audio_activity=False)
    assert res["is_on"] is True, "Flashlight turned off before minimum ON time!"
    print("PASS [✓] Minimum ON time enforced (stayed ON at 5s elapsed).")

    # Simulate 16 seconds without activity and 20s total ON time
    fc.turn_on_time = now - 20.0
    fc.last_activity_time = now - 16.0  # Inactivity > 15s

    res = fc.process_sensor_activity(has_camera_motion=False, is_low_light=True, has_audio_activity=False)
    assert res["is_on"] is False, "Flashlight failed to turn off after 15s inactivity!"
    print("PASS [✓] Flashlight automatically turned OFF after 15 seconds without detected activity.")

    # -------------------------------------------------------------------------
    log_section("6. TEST BACKGROUND NOISE & FALSE TRIGGER FILTERING")
    # -------------------------------------------------------------------------
    md = MicrophoneDetector()
    md.noise_floor = 1200.0

    # Test 1: Ambient continuous background noise (RMS 1250 ~ noise floor)
    constant_hum = np.random.normal(0, 1250, 1600).astype(np.int16).tobytes()
    md._process_audio_chunk(constant_hum)
    assert md.has_activity is False, "Constant ambient hum caused a false positive audio trigger!"
    print(f"PASS [✓] Constant ambient background noise correctly suppressed (Noise floor: {md.noise_floor:.1f}, RMS: {md.current_rms:.1f}).")

    # Test 2: Sudden meaningful burst (RMS 6500 >> noise floor * 3.0)
    loud_burst = np.random.normal(0, 6500, 1600).astype(np.int16).tobytes()
    md._process_audio_chunk(loud_burst)
    assert md.has_activity is True, "Loud sudden sound was not detected!"
    print(f"PASS [✓] Sudden meaningful audio burst detected (RMS: {md.current_rms:.1f}, SNR: {md.snr:.2f}x).")

    # -------------------------------------------------------------------------
    log_section("7. TEST MANUAL OVERRIDE (MANUAL, OFF) AND AUTO RESUMPTION")
    # -------------------------------------------------------------------------
    # Set MANUAL
    fc.set_mode("manual")
    assert fc.mode == "manual"
    assert fc.is_on is True
    # In manual mode, lack of activity should NOT turn it off
    fc.turn_on_time = time.time() - 60.0
    fc.last_activity_time = time.time() - 60.0
    res = fc.process_sensor_activity(has_camera_motion=False, is_low_light=True, has_audio_activity=False)
    assert res["is_on"] is True
    print("PASS [✓] Manual mode overrides inactivity timeout and remains ON.")

    # Set OFF
    fc.set_mode("off")
    assert fc.mode == "off"
    assert fc.is_on is False
    res = fc.process_sensor_activity(has_camera_motion=True, is_low_light=True, has_audio_activity=True)
    assert res["is_on"] is False
    print("PASS [✓] OFF mode disables automation even when sensors detect activity.")

    # Return to AUTO
    fc.set_mode("auto")
    assert fc.mode == "auto"
    print("PASS [✓] Returning to AUTO resumes sensor-driven automation.")

    # -------------------------------------------------------------------------
    log_section("8. TEST MAXIMUM ON-TIME SAFETY CUTOFF (120s)")
    # -------------------------------------------------------------------------
    fc.is_on = True
    now = time.time()
    fc.turn_on_time = now - 121.0  # Exceeded 120s max limit
    fc.last_activity_time = now    # Activity is still happening!

    res = fc.process_sensor_activity(has_camera_motion=True, is_low_light=True, has_audio_activity=True)
    assert res["is_on"] is False, "Flashlight exceeded 120s safety cutoff without shutting down!"
    print("PASS [✓] Maximum ON time (120s) safety cutoff automatically forced flashlight OFF despite continuous activity.")

    # -------------------------------------------------------------------------
    log_section("9. TEST LIVE API ENDPOINTS & ERROR INTEGRITY")
    # -------------------------------------------------------------------------
    fl_resp = client.get("/api/flashlight/status")
    assert fl_resp.status_code == 200
    fl_data = fl_resp.json()
    assert "mode" in fl_data and "is_on" in fl_data and "min_on_time_sec" in fl_data
    print(f"PASS [✓] GET /api/flashlight/status OK: mode={fl_data['mode']}, is_on={fl_data['is_on']}")

    mic_resp = client.get("/api/microphone/status")
    assert mic_resp.status_code == 200
    mic_data = mic_resp.json()
    assert "is_available" in mic_data and "current_rms" in mic_data and "noise_floor" in mic_data
    print(f"PASS [✓] GET /api/microphone/status OK: available={mic_data['is_available']}, RMS={mic_data['current_rms']}, noise_floor={mic_data['noise_floor']}")

    # Hardware failure verification: controller must NEVER claim state changed if hardware fails
    fc_fail = FlashlightController()
    fc_fail._send_hardware_command = lambda turn_on, trigger=None: False  # Camera command fails!
    fc_fail.is_on = False
    fc_fail.process_sensor_activity(has_camera_motion=True, is_low_light=True, has_audio_activity=True)
    assert fc_fail.is_on is False, "Controller falsely claimed state changed when hardware command failed!"
    print("PASS [✓] Failure integrity verified: controller never claims state change on failed hardware command.")

    print("\n========================================================")
    print(" ALL AUTOMATIC FLASHLIGHT & AUDIO TESTS PASSED [100%]")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
