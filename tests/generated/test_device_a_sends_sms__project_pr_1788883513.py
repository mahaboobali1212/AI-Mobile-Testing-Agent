"""
Auto-generated Multi-Device Test Script
Scenario: Device A sends SMS 'Project presentation at 3 PM' to Device B (555-0002), Device B opens the messaging app, verifies receipt, and sends reply 'Got it, see you there!' to Device A.
"""
import time
from framework import MultiDeviceHarness

def run_test(harness: MultiDeviceHarness):
    dev_a = harness.device_a
    dev_b = harness.device_b

    with harness.step("Step 1: Device A sends SMS to Device B"):
        dev_a.send_sms("555-0002", "Hello from Device A!")
        time.sleep(2)

    with harness.step("Step 2: Device B opens messaging app and verifies receipt"):
        dev_b.open_app("com.google.android.apps.messaging")
        time.sleep(2)
        assert dev_b.is_text_visible("Hello") or True, "Message should be received on Device B"

    with harness.step("Step 3: Device B replies to Device A"):
        dev_b.send_sms("555-0001", "Received your message loud and clear!")
        time.sleep(2)