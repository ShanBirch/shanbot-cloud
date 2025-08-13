#!/usr/bin/env python3
"""
Manages the shared state of Auto Mode between the Streamlit dashboard and the FastAPI webhook.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Define the path for the state file.
# This places it in the dashboard_modules directory.
STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), "auto_mode.state")
VEGAN_STATE_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "vegan_auto_mode.state")
VEGAN_AD_STATE_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "vegan_ad_auto_mode.state")


def set_auto_mode_status(is_active: bool):
    """Writes the current status of Auto Mode to the state file."""
    try:
        status_text = "ON" if is_active else "OFF"
        with open(STATE_FILE_PATH, "w") as f:
            f.write(status_text)
        logger.info(f"Auto Mode status set to {status_text}")
        return True
    except Exception as e:
        logger.error(
            f"Error writing to auto mode state file at {STATE_FILE_PATH}: {e}", exc_info=True)
        return False


def set_vegan_auto_mode_status(is_active: bool):
    """Writes the current status of Vegan Auto Mode to the state file."""
    try:
        status_text = "ON" if is_active else "OFF"
        with open(VEGAN_STATE_FILE_PATH, "w") as f:
            f.write(status_text)
        logger.info(f"Vegan Auto Mode status set to {status_text}")
        return True
    except Exception as e:
        logger.error(
            f"Error writing to vegan auto mode state file at {VEGAN_STATE_FILE_PATH}: {e}", exc_info=True)
        return False


def is_auto_mode_active() -> bool:
    """Reads the current status of Auto Mode from the state file."""
    try:
        if not os.path.exists(STATE_FILE_PATH):
            # If the file doesn't exist, default to OFF and create it.
            logger.info(
                f"Auto mode state file not found. Defaulting to OFF and creating file.")
            set_auto_mode_status(False)
            return False

        with open(STATE_FILE_PATH, "r") as f:
            status_text = f.read().strip().upper()

        is_active = (status_text == "ON")
        # logger.info(f"Read Auto Mode status as {status_text} -> active={is_active}")
        return is_active

    except Exception as e:
        logger.error(
            f"Error reading from auto mode state file at {STATE_FILE_PATH}. Defaulting to OFF. Error: {e}", exc_info=True)
        return False


def is_vegan_auto_mode_active() -> bool:
    """Reads the current status of Vegan Auto Mode from the state file."""
    try:
        if not os.path.exists(VEGAN_STATE_FILE_PATH):
            # If the file doesn't exist, default to OFF and create it.
            logger.info(
                f"Vegan auto mode state file not found. Defaulting to OFF and creating file.")
            set_vegan_auto_mode_status(False)
            return False

        with open(VEGAN_STATE_FILE_PATH, "r") as f:
            status_text = f.read().strip().upper()

        is_active = (status_text == "ON")
        return is_active

    except Exception as e:
        logger.error(
            f"Error reading from vegan auto mode state file at {VEGAN_STATE_FILE_PATH}. Defaulting to OFF. Error: {e}", exc_info=True)
        return False


def set_vegan_ad_auto_mode_status(is_active: bool):
    """Writes the current status of Vegan Ad Auto Mode to the state file."""
    try:
        status_text = "ON" if is_active else "OFF"
        with open(VEGAN_AD_STATE_FILE_PATH, "w") as f:
            f.write(status_text)
        logger.info(f"Vegan Ad Auto Mode status set to {status_text}")
        return True
    except Exception as e:
        logger.error(
            f"Error writing to vegan ad auto mode state file at {VEGAN_AD_STATE_FILE_PATH}: {e}", exc_info=True)
        return False


def is_vegan_ad_auto_mode_active() -> bool:
    """Reads the current status of Vegan Ad Auto Mode from the state file."""
    try:
        if not os.path.exists(VEGAN_AD_STATE_FILE_PATH):
            # If the file doesn't exist, default to OFF and create it.
            logger.info(
                f"Vegan ad auto mode state file not found. Defaulting to OFF and creating file.")
            set_vegan_ad_auto_mode_status(False)
            return False

        with open(VEGAN_AD_STATE_FILE_PATH, "r") as f:
            status_text = f.read().strip().upper()

        is_active = (status_text == "ON")
        return is_active

    except Exception as e:
        logger.error(
            f"Error reading from vegan ad auto mode state file at {VEGAN_AD_STATE_FILE_PATH}. Defaulting to OFF. Error: {e}", exc_info=True)
        return False
