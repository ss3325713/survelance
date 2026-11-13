"""Test Suite for Exposure Shift Suppression and Static Object Rejection."""

import numpy as np
from wheat_watch.motion import motion_detector
from wheat_watch.audio import audio_manager
from wheat_watch.config import app_config


def test_exposure_jump_suppression():
    print("[1] Testing Exposure & Global Luminance Jump Suppression...")
    motion_detector.reset()

    # Create baseline frame (e.g., field scene with average luminance ~100)
    baseline_frame = np.full((720, 1280, 3), 100, dtype=np.uint8)

    # Prime the background subtractor with 15 frames of baseline
    for _ in range(15):
        motion_detector.process_frame(baseline_frame)

    # Case A: Massive exposure jump (e.g. camera exposed or brightness slider moved)
    # Average luminance jumps from 100 to 180 (delta = 80!)
    overexposed_frame = np.full((720, 1280, 3), 180, dtype=np.uint8)
    has_motion, boxes, pct, is_calibrating = motion_detector.process_frame(overexposed_frame)

    print(f"    Overexposure frame test: has_motion={has_motion}, pct={pct}%, is_calibrating={is_calibrating}")
    assert not has_motion, "ERROR: Overexposure jump triggered false motion alert!"
    assert is_calibrating, "ERROR: Overexposure jump was not marked as calibration/suppression!"
    print("    ✓ Overexposure jump successfully suppressed.")

    # Case B: Stabilization trigger test
    motion_detector.trigger_stabilization(count=10)
    has_motion_stab, _, _, is_calibrating_stab = motion_detector.process_frame(overexposed_frame)
    assert not has_motion_stab, "ERROR: Stabilization frame triggered false motion!"
    assert is_calibrating_stab, "ERROR: Frame during stabilization was not marked as calibrating!"
    print("    ✓ Camera control stabilization successfully suppresses alerts.")


def test_static_object_rejection():
    print("\n[2] Testing Static Object Rejection via Motion Mask...")
    motion_detector.reset()

    # Prepare frame with background
    frame1 = np.full((720, 1280, 3), 120, dtype=np.uint8)
    for _ in range(15):
        motion_detector.process_frame(frame1)

    # Frame 2: Moving object at top-left [50, 50, 200, 200]
    frame2 = frame1.copy()
    frame2[50:200, 50:200] = 220  # Moving target in top-left

    # Process 2 frames for temporal persistence
    motion_detector.process_frame(frame2)
    has_motion, boxes, pct, _ = motion_detector.process_frame(frame2)

    assert has_motion, "Localized motion was not detected!"
    print(f"    Localized motion detected: {len(boxes)} boxes, {pct}% area")

    # Now test two object bounding boxes:
    # 1. Moving object at top-left [50, 50, 200, 200]
    is_moving_1, ratio_1 = motion_detector.has_motion_in_box([50, 50, 200, 200], 1280, 720)
    print(f"    Moving box [50, 50, 200, 200]: is_moving={is_moving_1}, ratio={ratio_1:.3f}")
    assert is_moving_1, "ERROR: Actual moving target was not marked as moving!"

    # 2. Static object (e.g. Chair or Potted Plant) at bottom-right [800, 400, 1100, 650]
    is_moving_2, ratio_2 = motion_detector.has_motion_in_box([800, 400, 1100, 650], 1280, 720)
    print(f"    Static box [800, 400, 1100, 650]: is_moving={is_moving_2}, ratio={ratio_2:.3f}")
    assert not is_moving_2, "ERROR: Static object was falsely marked as moving!"
    print("    ✓ Static object correctly identified as stationary.")


def test_alarm_category_filtering():
    print("\n[3] Testing Audio Alert Category Filtering...")
    # Verify that 'General motion' and 'Unknown object' do not play sound by default
    assert not audio_manager.can_play("General motion"), "ERROR: General motion should not play sound by default!"
    assert not audio_manager.can_play("Unknown object"), "ERROR: Unknown object should not play sound by default!"
    print("    ✓ General motion sound suppressed by default.")
    print("    ✓ Unknown object (chair/plant) sound suppressed by default.")

    # Verify that target threats CAN play sound (Person, Bird, Animal, Monkey)
    assert audio_manager.can_play("Person"), "ERROR: Person alert should be allowed!"
    assert audio_manager.can_play("Bird"), "ERROR: Bird alert should be allowed!"
    assert audio_manager.can_play("Possible monkey"), "ERROR: Possible monkey alert should be allowed!"
    print("    ✓ High-priority targets (Person, Bird, Monkey, Animal) authorized for sound.")


if __name__ == "__main__":
    test_exposure_jump_suppression()
    test_static_object_rejection()
    test_alarm_category_filtering()
    print("\n[PASS] All Exposure Suppression and Static Object Rejection Tests Succeeded!")
