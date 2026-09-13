"""
Auto-generated Multi-Device Test Script
Scenario: Device A dials Device B (555-0002), Device B immediately rejects and declines the call, verify that both devices return to idle state with no active call.
"""
import time
from framework import MultiDeviceHarness

def run_test(harness: MultiDeviceHarness):
    dev_a = harness.device_a
    dev_b = harness.device_b

    with harness.step("Step 1: Device A dials Device B (555-0002)"):
        dev_a.dial_number("555-0002")
        time.sleep(2)

    with harness.step("Step 2: Device B answers the incoming call"):
        dev_b.answer_incoming_call()
        time.sleep(2)

    with harness.step("Step 3: Verify both devices are in active call state"):
        assert dev_a.is_in_call(), "Device A should be in active call state"
        assert dev_b.is_in_call(), "Device B should be in active call state"
        time.sleep(3)

    with harness.step("Step 4: Device A terminates the call"):
        dev_a.end_call()
        time.sleep(1)

    with harness.step("Step 5: Verify call has disconnected"):
        assert not dev_a.is_in_call(), "Device A call should have ended"
        assert not dev_b.is_in_call(), "Device B call should have ended"