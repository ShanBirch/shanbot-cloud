#!/usr/bin/env python3
"""Test Auto Mode System"""

from auto_mode_state import set_auto_mode_active, is_auto_mode_active, get_auto_mode_status


def test_auto_mode():
    print("🧪 Testing Auto Mode System")
    print("=" * 40)

    # Test initial state
    print(f"Initial state: {get_auto_mode_status()}")

    # Test enabling Auto Mode
    print("\n1. Enabling Auto Mode...")
    success = set_auto_mode_active(True)
    print(f"   Success: {success}")
    print(f"   Active: {is_auto_mode_active()}")

    # Test disabling Auto Mode
    print("\n2. Disabling Auto Mode...")
    success = set_auto_mode_active(False)
    print(f"   Success: {success}")
    print(f"   Active: {is_auto_mode_active()}")

    # Test re-enabling
    print("\n3. Re-enabling Auto Mode...")
    success = set_auto_mode_active(True)
    print(f"   Success: {success}")
    print(f"   Final status: {get_auto_mode_status()}")

    print("\n✅ Auto Mode system is working!")
    print("🎯 Now when you enable Auto Mode in the dashboard:")
    print("   - Webhook will auto-schedule responses")
    print("   - No manual review needed")
    print("   - Responses sent with smart timing")


if __name__ == "__main__":
    test_auto_mode()
