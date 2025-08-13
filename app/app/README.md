# ManyChat Webhook Integration

A FastAPI-based webhook integration for ManyChat that handles multiple flows for fitness coaching automation, powered by Google's Gemini AI.

## Features

- **Dual Flow Support**: Handles both general chat conversations and client onboarding processes
- **Multiple Permission Controls**: Supports "general chat", "initial whats app check in", "Check in Monday", and "Member General Chat" permission flags
- **AI-Powered Responses**: Utilizes Google's Gemini AI for contextual responses
- **Google Sheets Integration**: Pulls client data from coaching onboarding sheet
- **Smart Message Handling**: Splits longer AI responses into multiple messages
- **Permission Controls**: Only responds when appropriate permission flags are set

## Setup Requirements

- Python 3.8+ 
- ManyChat account with API access
- Google Sheets credentials
- Gemini API key

## Configuration

Key configuration points in the code:

```python
# ManyChat API Key
MANYCHAT_API_KEY = "your_manychat_api_key"

# Google Sheets Configuration
SHEETS_CREDENTIALS_PATH = r"C:\\path\\to\\sheets_credentials.json"

# Lead Chat Sheet
SPREADSHEET_ID = "1nDVn6jhkYBubVTQqbYU3PKo_WooeuTsQzsaNNcQdJlo"
RANGE_NAME = "Sheet1!A:E"

# Coaching Onboarding Form
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key")
```

## Running the Server

Start the webhook server:

```bash
cd app
uvicorn manychat_webhook_fixed:app --reload
```

For public access, use ngrok:

```bash
ngrok http 8000
```

Use the ngrok URL (e.g., https://99f9-194-223-45-155.ngrok-free.app) as your webhook URL in ManyChat.

## Webhook Endpoints

- **General Chat**: `/webhook/manychat`
- **Onboarding**: `/webhook/onboarding`
- **Check-in**: `/webhook/checkin`
- **Member General Chat**: `/webhook/member_general_chat`
- **Health Check**: `/health`

## ManyChat Configuration

### Custom Fields

Required custom fields in ManyChat:

- `general chat` - Set to "true" to enable general chat flow
- `initial whats app check in` - Set to "true" to enable onboarding flow
- `Check in Monday` - Set to "true" to enable weekly check-in flow
- `Member General Chat` - Set to "true" to enable member general chat flow
- `CONVERSATION` - Stores conversation history
- `o1 Response` - First part of the AI response
- `o1 Response 2` - Second part of the AI response (if applicable)
- `o1 Response 3` - Third part of the AI response (if applicable)
- `Instagram Name` - Used to look up client data

### Webhook Setup

1. Create a Flow Starting Point in ManyChat
2. Set up a Content tool with an API Call
3. Point the API call to your ngrok URL + "/webhook/manychat"
4. Select POST as the method
5. Add appropriate headers (Content-Type: application/json)
6. In the API call payload, include required fields (id, custom_fields, ig_username)

## Key Functionalities

### General Chat Flow

- Takes the current user message from the "CONVERSATION" field
- Fetches previous conversation history from Google Sheets
- Sends both to Gemini AI for response generation
- Updates ManyChat fields with the AI response

### Onboarding Flow

- Triggered when "initial whats app check in" is true
- Searches for the client in the Coaching Onboarding Form
- Creates a summary highlighting:
  - Gym Access
  - Preferred Macro Split
  - Excluded Foods
- Generates an appropriate welcome message via Gemini
- Updates ManyChat fields with the response

### Check In Flow

- Triggered when "Check in Monday" is true
- Searches for the client in the Coaching Onboarding Form
- Retrieves comprehensive client data including:
  - Personal details (name, gender, weight, height, DOB)
  - Fitness information (goals, gym access, training frequency)
  - Dietary information (requirements, daily calories)
  - Exercise preferences
  - Previous conversation history and check-in status
- Gets the current check-in message from the "CONVERSATION" field
- Generates a personalized check-in message via Gemini
- Updates ManyChat fields with the response split across three message slots

### Member General Chat Flow

This flow is designed for existing members who need general assistance. It activates when:

1. The "Member General Chat" field is set to "true"
2. No other permission fields are active

The flow:
1. Retrieves client information from the Coaching Onboarding Sheet using the Instagram Name
2. Passes client information and current conversation to Gemini AI
3. Receives and processes the AI response
4. Splits the response across up to three message fields to accommodate longer responses
5. Returns the response for display in ManyChat

**Webhook Endpoint**: `/webhook/member_general_chat`

**Data Retrieved**: Same as Check-in Flow (client name, pronouns, primary goal, etc.)

**Response Fields**:
- o1 Response - First part of AI response
- o1 Response 2 - Second part (if applicable)
- o1 Response 3 - Third part (if applicable)

## Troubleshooting

- If message splitting isn't working, check the logs for the split sizes
- If fields aren't updating in ManyChat, verify field names match exactly
- For onboarding or check-in issues, confirm the Instagram username exists in column P
- For check-in flow issues, ensure "Check in Monday" field is set to "true"

## Additional Notes

- The webhook logs all interaction details for debugging
- Google Sheet format should match the expected schema
- Ensure ManyChat API key has sufficient permissions 