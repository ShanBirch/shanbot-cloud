import os
import logging
import datetime
import json
import traceback
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment variables
SHEETS_SPREADSHEET_ID = os.getenv("MANYCHAT_SPREADSHEET_ID")
SHEETS_CREDS_PATH = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS", "service-account-credentials.json")


class GoogleSheetsService:
    """Service for interacting with Google Sheets"""

    def __init__(self):
        """Initialize the Google Sheets service"""
        self.client = None
        self.spreadsheet = None
        try:
            # Check if credentials file exists
            if not os.path.exists(SHEETS_CREDS_PATH):
                logger.warning(
                    f"Google Sheets credentials file not found at {SHEETS_CREDS_PATH}")
                return

            # Define the scopes
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
                      'https://www.googleapis.com/auth/drive']

            # Authenticate using the service account credentials
            creds = Credentials.from_service_account_file(
                SHEETS_CREDS_PATH, scopes=SCOPES)
            self.client = gspread.authorize(creds)

            # Open the spreadsheet
            if SHEETS_SPREADSHEET_ID:
                try:
                    self.spreadsheet = self.client.open_by_key(
                        SHEETS_SPREADSHEET_ID)
                    logger.info(
                        f"Connected to Google Sheets spreadsheet: {self.spreadsheet.title}")
                except Exception as e:
                    logger.error(
                        f"Error opening spreadsheet by ID {SHEETS_SPREADSHEET_ID}: {str(e)}")
                    logger.error(traceback.format_exc())
            else:
                logger.warning(
                    "MANYCHAT_SPREADSHEET_ID environment variable not set")

        except Exception as e:
            logger.error(f"Error initializing Google Sheets service: {str(e)}")
            logger.error(traceback.format_exc())

    def append_row(self, sheet_name, row_data):
        """
        Append a row to a sheet

        Args:
            sheet_name (str): The name of the sheet to append to
            row_data (list): The data to append

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.spreadsheet:
            logger.warning(
                "Google Sheets service not initialized, cannot append row")
            return False

        try:
            # Get the worksheet, creating it if it doesn't exist
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.info(f"Creating new sheet: {sheet_name}")
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name, rows=1, cols=len(row_data))

            # Append the row
            worksheet.append_row(row_data)
            logger.info(f"Appended row to sheet {sheet_name}")
            return True

        except Exception as e:
            logger.error(
                f"Error appending row to sheet {sheet_name}: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def lookup_or_add_instagram(self, instagram_username, additional_data=None):
        """
        Look up an Instagram username in the sheet, or add it if it doesn't exist

        Args:
            instagram_username (str): The Instagram username to look up
            additional_data (dict): Additional data to include if adding a new row

        Returns:
            dict: The result of the operation
        """
        if not self.spreadsheet:
            logger.warning(
                "Google Sheets service not initialized, cannot lookup Instagram username")
            return {"success": False, "error": "Sheets service not initialized"}

        if not instagram_username:
            return {"success": False, "error": "No Instagram username provided"}

        try:
            # Get the Instagram worksheet, creating it if it doesn't exist
            sheet_name = "Instagram Users"
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.info(f"Creating new sheet: {sheet_name}")
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name, rows=1, cols=5)
                # Add header row
                worksheet.append_row(
                    ["Instagram Username", "First Added", "Last Updated", "Data", "Notes"])

            # Look up the username
            try:
                cell = worksheet.find(instagram_username)
                # Username found, get the row data
                row_data = worksheet.row_values(cell.row)
                logger.info(
                    f"Found Instagram username {instagram_username} in row {cell.row}")

                # Update the "Last Updated" field
                now = datetime.datetime.now().isoformat()
                worksheet.update_cell(cell.row, 3, now)

                # If additional data is provided, update the "Data" field
                if additional_data:
                    data_json = json.dumps(additional_data)
                    worksheet.update_cell(cell.row, 4, data_json)

                return {
                    "success": True,
                    "found": True,
                    "row": cell.row,
                    "data": row_data
                }

            except gspread.exceptions.CellNotFound:
                # Username not found, add it
                logger.info(
                    f"Instagram username {instagram_username} not found, adding new row")
                now = datetime.datetime.now().isoformat()
                data_json = json.dumps(
                    additional_data) if additional_data else ""
                worksheet.append_row(
                    [instagram_username, now, now, data_json, ""])

                # Find the row we just added
                cell = worksheet.find(instagram_username)

                return {
                    "success": True,
                    "found": False,
                    "row": cell.row,
                    "added": True
                }

        except Exception as e:
            logger.error(
                f"Error looking up Instagram username {instagram_username}: {str(e)}")
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

    def get_all_records(self, sheet_name):
        """
        Get all records from a sheet as a list of dictionaries

        Args:
            sheet_name (str): The name of the sheet to get records from

        Returns:
            list: A list of dictionaries representing the records
        """
        if not self.spreadsheet:
            logger.warning(
                "Google Sheets service not initialized, cannot get records")
            return []

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            return worksheet.get_all_records()
        except Exception as e:
            logger.error(
                f"Error getting records from sheet {sheet_name}: {str(e)}")
            logger.error(traceback.format_exc())
            return []


# Create a singleton instance
sheets_service = GoogleSheetsService()
