Okay, I understand. You don't want to paste all the code here, but you want a detailed, structured blueprint or instruction manual that you can use within Cursor (or your IDE) to guide the development process. This manual will outline what needs to be built, how the pieces should connect, and where your existing scripts fit in.

Think of this as the architectural plan for Shanbot. You'll fill in the specific code details based on your existing scripts and the choices you make.

Here is that structured instruction manual/blueprint:

# Shanbot - Development Blueprint & Instruction Manual
# Version: 0.1
# Goal: Create an AI-powered system (Shanbot) modeled after Shannon
# to manage and grow the Coco's Connected online coaching business.

# --- Core Principles ---
# 1. Modular Design: Separate components for easier development and maintenance.
# 2. AI-Driven Decisions: LLM (Gemini) acts as the central brain (Shanbot).
# 3. Orchestration Layer: Translates AI intent into concrete actions (script execution).
# 4. Script Integration: Leverage existing Python scripts as "tools".
# 5. Centralized Control: Dashboard for monitoring and manual commands.
# 6. Data-Centric: Store and utilize client/interaction data effectively.

# --- SECTION 0: Initial Script Analysis ---
# Goal: Understand the functionality, inputs, outputs, dependencies, and integration points of existing scripts before detailed component design.

## Script Analysis Details

### 1. manychat_webhook_fullprompt.py
**Purpose:** Webhook handler for ManyChat integration, managing Instagram DM interactions
**Key Functions:**
- `get_sheet_data()`: Retrieves user data from Google Sheets
- `update_manychat_fields()`: Updates subscriber fields in ManyChat
- `manychat_webhook()`: Main webhook endpoint for handling messages
- `onboarding_webhook()`: Handles onboarding flow
- `checkin_webhook()`: Processes check-in related messages
- `member_general_chat_webhook()`: Manages general chat interactions
**Dependencies:**
- Google Sheets API
- ManyChat API
- Gemini AI
**Integration Points:**
- Connects with Google Sheets for data storage
- Interfaces with ManyChat for message handling
- Uses Gemini for conversation generation

### 2. followersbot2.py
**Purpose:** Instagram automation tool for profile analysis and outreach
**Key Functions:**
- `login_to_instagram()`: Handles Instagram authentication
- `analyze_multiple_images_with_gemini()`: Analyzes profile images
- `message_user()`: Sends DMs to users
- `process_instagram_usernames()`: Main workflow orchestration
**Dependencies:**
- Selenium WebDriver
- Gemini AI
- Google Sheets integration
**Integration Points:**
- Stores data in analytics_data.json
- Updates Google Sheets with user interactions
- Uses Gemini for image analysis

### 3. story1.py
**Purpose:** Instagram story interaction automation
**Key Functions:**
- `InstagramBot` class: Manages story interactions
- `analyze_image_with_gpt()`: Analyzes story content
- `process_single_story()`: Handles individual story interactions
- `interact_with_stories()`: Main story interaction workflow
**Dependencies:**
- Selenium WebDriver
- Google Sheets integration
**Integration Points:**
- Updates interaction data in Google Sheets
- Coordinates with followersbot2.py for user targeting

### 4. checkin_current.py
**Purpose:** Client check-in automation and analysis
**Key Functions:**
- `TrainerizeAutomation` class: Manages Trainerize data collection
- `generate_checkin_review_content()`: Creates personalized reviews
- `create_checkin_review_pdf()`: Generates PDF reports
- `prepare_fitness_wrapped_data()`: Compiles client statistics
**Dependencies:**
- Trainerize API
- Google Sheets API
- Gemini AI
**Integration Points:**
- Feeds data to simple_blue_video.py
- Updates Google Sheets with client progress
- Stores data in JSON format for other components

### 5. instacheckins.py
**Purpose:** Automated Instagram check-in messaging
**Key Functions:**
- `message_user()`: Sends personalized check-in messages
- `try_send_message()`: Handles message delivery
- `handle_popups()`: Manages Instagram UI interactions
**Dependencies:**
- Selenium WebDriver
**Integration Points:**
- Coordinates with followersbot2.py for user targeting
- Uses shared message templates

### 6. sheets_integration.py
**Purpose:** Centralized Google Sheets data management
**Key Functions:**
- `GoogleSheetsManager` class: Handles all sheets operations
- `find_user()`: Retrieves user data
- `update_sheet()`: Updates user information
- `add_row()`: Adds new user entries
**Dependencies:**
- Google Sheets API
**Integration Points:**
- Used by multiple scripts for data persistence
- Maintains conversation history and user data

### 7. simple_blue_video.py
**Purpose:** Generates client progress videos
**Key Functions:**
- `create_slide_with_text()`: Creates video slides
- `process_client_data()`: Processes fitness data into video
**Dependencies:**
- MoviePy
- PIL
**Integration Points:**
- Receives data from checkin_current.py
- Uses shared media assets

### 8. analytics_dashboard.py
**Purpose:** Streamlit-based analytics dashboard for monitoring Shanbot performance and user interactions
**Key Functions:**
- `load_analytics_data()`: Loads conversation and metrics data from JSON
- `display_conversation_details()`: Shows detailed conversation analysis
- `analyze_engagement_level()`: Evaluates user engagement metrics
- `generate_ai_follow_up_message()`: Creates personalized follow-ups using Gemini
- `should_follow_up()`: Determines optimal follow-up timing
- `get_smart_follow_up_timing()`: Calculates best timing for re-engagement

**Key Features:**
1. Overview Tab:
   - Global metrics (conversations, messages, response rates)
   - Responder categories analysis
   - Topic tracking and funnel metrics
   - Engagement analytics charts

2. Conversations Tab:
   - Individual conversation analysis
   - Message history review
   - User profile insights
   - Engagement metrics per user

3. Daily Report Tab:
   - Active conversations tracking
   - Follow-up recommendations
   - Conversion analysis
   - Bot activity metrics

4. Analytics Export Tab:
   - Data export functionality
   - Historical data access

**Dependencies:**
- Streamlit for UI
- Gemini AI for message generation
- Pandas for data analysis
- Matplotlib for visualizations

**Integration Points:**
- Reads from analytics_data.json
- Connects with Gemini for follow-up generation
- Provides insights for other components' decision making

**Key Metrics Tracked:**
1. Engagement Metrics:
   - Response rates
   - Message counts
   - Conversation durations
   - User categories (High/Medium/Low/No Response)

2. Conversion Metrics:
   - Coaching inquiries
   - Signup rates
   - Topic progression
   - Funnel analysis

3. Bot Performance:
   - Message success rates
   - Response timing
   - Follow-up effectiveness
   - Topic coverage

4. User Analysis:
   - Engagement patterns
   - Response quality
   - Topic interests
   - Conversion indicators

**Real-time Features:**
- Auto-refresh capability
- Live metric updates
- Dynamic conversation tracking
- Instant follow-up suggestions

## Updated Integration Overview
The analytics dashboard serves as the central monitoring hub where:
1. `manychat_webhook_fullprompt.py` feeds conversation data
2. `followersbot2.py` and `story1.py` provide outreach metrics
3. `checkin_current.py` contributes client progress data
4. All components' performance can be monitored and optimized

## Enhanced Data Flow
1. User interactions → Analytics storage → Dashboard visualization
2. Dashboard insights → Strategy adjustment → Improved targeting
3. Performance metrics → AI analysis → Optimization recommendations
4. User engagement data → Follow-up timing → Automated messaging

## Key Dependencies
- Selenium WebDriver for browser automation
- Google Sheets API for data storage
- Gemini AI for content analysis and generation
- MoviePy for video creation
- Various APIs (ManyChat, Trainerize)

## Data Flow
1. User interactions → ManyChat webhook → Google Sheets
2. Profile analysis → Gemini → Google Sheets
3. Client data → Check-in analysis → Video generation
4. Stored data → Automated follow-ups → User engagement

# --- SECTION 1: The Brain - Shanbot Core Prompt ---

## 1.1 Master Prompt Definition (`shanbot_master_prompt.txt`)
# Purpose: Define Shanbot's identity, goals, capabilities, constraints, and communication style for Gemini.
# Location: Create a dedicated text file for this prompt.

# --- Prompt Content Checklist ---
# [x] **Identity:** "You are Shanbot, an AI assistant modeled after Shannon Birch..."
# [ ] **Core Goal:** "Your primary goal is to manage and grow Coco's Connected..." (Specify focus: client experience, lead gen, operational efficiency).
# [ ] **Key Responsibilities:**
#     [ ] Analyze client data (Trainerize).
#     [ ] Generate weekly check-ins (PDF/Video).
#     [ ] Handle Instagram DMs (via webhooks/scripts).
#     [ ] Initiate Instagram outreach (Story comments/DMs).
#     [ ] Log interactions and task data.
#     [ ] Execute dashboard commands.
#     [ ] Offer meal plans contextually.
# [ ] **Operational Constraints:**
#     [ ] "Interact only through provided tools (`TOOL_CALL`)."
#     [ ] Prioritize client success, ethics, confidentiality.
#     [ ] "Refer complex/sensitive issues to Shannon (user)."
# [ ] **Communication Style:**
#     [ ] **Client-Facing:** (INTEGRATE YOUR EXISTING INSTAGRAM PROMPT HERE) - Rapport first, wait for fitness talk, offer logic (price vs. trial), closing rules, tone, slang, emoji use, punctuation rules (no hyphens!), etc. Include Shannon's background/business info for context. Include conversation examples.
#     [ ] **Dashboard-Facing:** Maintain core personality but be more operational/factual.
# [ ] **Tool Definitions (Crucial - See Section 3.2):**
#     [ ] Define the exact `TOOL_CALL` format: `TOOL_CALL: tool_name(param1='value1', ...)`
#     [ ] List *all* available tools Shanbot can request.
# [ ] **Context Handling:** Mention reviewing provided history/data before responding.
# [ ] **Output Requirement:** Specify output should be EITHER natural language OR a `TOOL_CALL`.

## 1.2 Prompt Management
# // TODO: Implement logic in Orchestrator (Section 2) to load this prompt and combine it with dynamic context (e.g., conversation history, client data) before sending to Gemini API.

# --- SECTION 2: The Nervous System - Orchestrator ---

## 2.1 Core Orchestrator Logic (`orchestrator.py` or similar)
# Purpose: Central hub that receives tasks, interacts with Gemini, parses responses, executes tools (scripts), and logs results.
# Language: Python

# --- Key Components & Logic ---
# [ ] **Task Input Handling:**
#     [ ] Function/method to receive tasks (e.g., from Webhook handler, Dashboard API). Task data should include type, context (e.g., user_id, message), etc.
# [ ] **Gemini API Interaction:**
#     [ ] Function to securely load API key ([Use environment variables or secrets manager]).
#     [ ] Function `get_shanbot_response(prompt, context_data)`:
#         [ ] Load `shanbot_master_prompt.txt`.
#         [ ] Inject relevant `context_data` (conversation history, client info, task details).
#         [ ] Send the combined prompt to Gemini API.
#         [ ] Handle API errors (rate limits, exceptions).
#         [ ] Return Gemini's raw response.
# [ ] **Response Parsing:**
#     [ ] Function `parse_gemini_response(response_text)`:
#         [ ] Check if the response starts with `TOOL_CALL:`.
#         [ ] If yes: Parse out `tool_name` and parameters (key-value pairs). Return structured tool request (e.g., `{'type': 'tool', 'name': '...', 'params': {...}}`).
#         [ ] If no: Assume it's natural language text. Return structured text response (e.g., `{'type': 'text', 'content': '...'}`).
# [ ] **Tool Execution Engine:**
#     [ ] Dictionary mapping `tool_name` strings to the actual Python functions that wrap your scripts (See Section 3). `TOOL_REGISTRY = {'trainerize_generate_checkin': run_trainerize_checkin_script, 'instagram_outreach_bot': config_for_run_terminal_cmd, ...}`
#         # Note: The registry might map names to functions, configurations for running external scripts (like followersbot2.py via run_terminal_cmd), or configurations for interacting with external services (like the ManyChat webhook service via HTTP if needed).
#     [ ] Function `execute_tool(tool_request)`:
#         [ ] Look up `tool_request['name']` in `TOOL_REGISTRY`.
#         [ ] Call the corresponding wrapper function or execute the configured action (e.g., run terminal command, send HTTP request) with `tool_request['params']`.
#         [ ] Handle exceptions during script/tool execution.
#         [ ] Capture return values (status, file paths, data).
# [ ] **Logging:**
#     [ ] Implement robust logging (using Python's `logging` module).
#     [ ] Log received tasks, prompts sent to Gemini, raw Gemini responses, parsed responses/tool calls, tool execution attempts, script outputs/errors.
# [ ] **Main Loop / Entry Point:**
#     [ ] How is the orchestrator triggered? (e.g., runs continuously listening to a queue? Triggered by API calls?) Define the main execution flow.

## 2.2 Configuration Management (`config.py` or `.env` file)
# Purpose: Centralize all configuration variables.
# [ ] Gemini API Key
# [ ] Trainerize Credentials ([Securely managed, NOT hardcoded])
# [ ] Instagram Credentials ([Securely managed])
# [ ] Database Connection String
# [ ] File Paths (e.g., for saving reports, logs, prompt file)
# [ ] Webhook Secrets
# // TODO: Use a library like `python-dotenv` to load environment variables.

# --- SECTION 3: The Limbs - Script Integration ---

## 3.1 Script Standardization Philosophy
# Goal: Make each existing Python script callable as a reliable "tool" by the Orchestrator.
# Principle: Wrap each script's core logic in a Python function with defined inputs and outputs.

## 3.2 Tool Definition & Wrapper Functions (`tools/` directory)
# Create a `tools/` directory. Inside, create Python files for wrapping your scripts (e.g., `tools/trainerize_tools.py`, `tools/instagram_tools.py`).

# --- For EACH Existing Script ---
# Example: Trainerize Check-in Script
# Original Location: [Specify path, e.g., 'Desktop/Shanbot/trainerize_script.py']
# Wrapper Function (`tools/trainerize_tools.py`):
# ```python
# import logging # Or your preferred logging setup
# # Import necessary functions/classes from your original script if modular
# # OR refactor the script's core logic directly into this function
#
# def run_trainerize_checkin_script(client_id: str, **kwargs) -> dict:
#     """
#     Logs into Trainerize, scrapes data for the client, analyzes via Gemini,
#     generates PDF report and video summary.
#
#     Args:
#         client_id (str): The unique identifier for the client.
#         **kwargs: For potential future parameters.
#
#     Returns:
#         dict: Contains status and output file paths or error info.
#               Example success: {'status': 'success', 'pdf_path': 'path/to/report.pdf', 'video_path': 'path/to/video.mp4'}
#               Example failure: {'status': 'error', 'message': 'Failed to login.'}
#     """
#     logging.info(f"Running Trainerize check-in for client: {client_id}")
#     try:
#         # --- Refactored Script Logic ---
#         # 1. Securely get credentials (from config/env)
#         # 2. [REPLACE HARDCODED CLIENT LIST/FILE] Use the provided `client_id`.
#         # 3. Selenium/API calls for login, data scraping. (Add robust waits, error handling).
#         # 4. Call Gemini for analysis (use orchestrator's API key/config).
#         # 5. Generate PDF/Video.
#         # 6. [REPLACE DESKTOP SAVING] Save files to a configured, predictable location.
#         # 7. Get the final file paths.
#         # --- End Refactored Logic ---
#
#         pdf_path = "..." # Get actual path
#         video_path = "..." # Get actual path
#         logging.info(f"Successfully generated check-in for {client_id}")
#         return {'status': 'success', 'pdf_path': pdf_path, 'video_path': video_path}
#
#     except Exception as e:
#         logging.error(f"Error during Trainerize check-in for {client_id}: {e}", exc_info=True)
#         return {'status': 'error', 'message': str(e)}
#
# ```
# **Tool Name (for Master Prompt & Orchestrator Registry):** `trainerize_generate_checkin`
# **Input Parameter(s):** `client_id` (String)
# **Output Structure:** Dictionary with `status` ('success'/'error'), and on success `pdf_path`, `video_path`, on error `message`.
# **Action Items:**
#     [ ] Refactor original script logic into the wrapper function.
#     [ ] Remove hardcoded client lists/paths. Use input parameters and config.
#     [ ] Implement robust error handling (`try...except`) for each major step.
#     [ ] Ensure secure credential handling.
#     [ ] Standardize return dictionary.
#     [ ] Add logging.

# --- Repeat the above structure for ALL your other scripts: ---
# [ ] **Component:** ManyChat Webhook Handler
#     *   **Implementation:** `manychat_webhook_fullprompt.py` (Located in `app/`)
#     *   **Description:** Handles incoming ManyChat webhooks as a **standalone FastAPI service** (run via `uvicorn manychat_webhook_fullprompt:app`). It integrates directly with Google Sheets and Gemini for processing messages and generating responses based on detailed internal prompts. Acts as the primary response engine for live ManyChat interactions.
#     *   **Component Name (Conceptual):** `manychat_webhook_service`
#     *   **Input:** Webhook payload data (dict) from ManyChat.
#     *   **Output:** Updates ManyChat custom fields via API, sends messages back to ManyChat user.
#     *   **Action Items:** Ensure configuration (`config.py`/.env) is aligned. Define clear interaction points with other components (e.g., Database for logging, reading analytics).
# [ ] **Script:** Instagram Story Commenter (Potentially part of `followersbot2.py` or separate)
#     *   Purpose: Comment on a specific story.
#     *   Tool Name: `instagram_comment_story`
#     *   Input: `story_url` (or user ID + logic to find latest story), `comment_text`
#     *   Output: Status dict.
#     *   Action Items: Refactor or confirm logic within `followersbot2.py`. Add error handling. Define if Orchestrator can trigger this specifically.
# [ ] **Script:** Instagram Initial DM Sender & Profile Analyzer
#     *   **Implementation:** `followersbot2.py` (Located in root `shanbot/` directory)
#     *   **Description:** Handles proactive Instagram outreach, profile analysis (multi-photo via Gemini), topic extraction, and initial DM sending. Runs as a **standalone Python script**. Acts as the primary outreach engine.
#     *   **Tool Name (for Orchestrator):** `instagram_outreach_bot`
#     *   **Input Parameters:** Command-line arguments (e.g., `--target-user`, `--daily-limit`, `--followers-list`) and input files (e.g., `Instagram_followers.txt`, `progress.txt`).
#     *   **Output Structure/Effects:** Sends DMs via Selenium/Instagram API, updates Google Sheets, updates state files (`progress.txt`, `daily_stats.json`), potentially updates central analytics data (`analytics_data.json`).
#     *   **Action Items:** Ensure script can be reliably triggered by the Orchestrator (e.g., via `run_terminal_cmd`) and handles parameters correctly. Ensure configuration is externalized (e.g., API keys, paths moved to `config.py`/.env). Add robust error handling and status reporting back to the orchestrator if possible.
# [ ] **Script:** Conversation Data Collector
#     *   **Implementation:** Likely part of `conversation_analytics_integration.py` and potentially integrated within `manychat_webhook_fullprompt.py` and `followersbot2.py`.
#     *   Purpose: Extract and store conversation metrics/data.
#     *   Tool Name: `log_conversation_data` (Or potentially just database interaction functions).
#     *   Input: Conversation ID, user ID, message details, extracted metrics (e.g., topics).
#     *   Output: Data written to Database (Section 4).
#     *   Action Items: Define clear functions in `database.py` (Section 4.3) for logging. Ensure both `manychat_webhook_fullprompt.py` and `followersbot2.py` call these logging functions appropriately. Connect to Database (Section 4).
# [ ] **Script:** Data Analysis Dashboard Component(s)
#     *   **Implementation:** `analytics_dashboard.py` (Streamlit app).
#     *   Purpose: Analyze and visualize stored data.
#     *   Tool Name(s): Not likely a direct "tool" for the Orchestrator, but rather a consumer of the Database. Backend might have API endpoints if needed.
#     *   Input: Reads data from Database (Section 4).
#     *   Output: Visualizations and analysis presented in the Streamlit UI.
#     *   Action Items: Ensure dashboard reads from the finalized Database schema. Define any necessary backend API endpoints if other components need analysis results directly. Connect to Database (Section 4).

# --- SECTION 4: The Memory - Data Storage ---

## 4.1 Database Choice
# [ ] Select Database: PostgreSQL (Recommended for relational data), MySQL, MongoDB.
# [ ] Setup: Install database, create user/database for Shanbot.

## 4.2 Database Schema Design (`schema.sql` or ORM models)
# Purpose: Define tables to store essential information.
# [ ] **Table: `clients`**
#     *   `client_id` (Primary Key, e.g., Trainerize ID)
#     *   `name`
#     *   `instagram_handle` (Optional)
#     *   `trainerize_link` (Optional)
#     *   `status` (e.g., 'active', 'trial', 'inactive')
#     *   `trial_end_date` (Optional)
#     *   Other relevant static info...
# [ ] **Table: `leads`**
#     *   `lead_id` (Primary Key, e.g., Instagram User ID)
#     *   `instagram_handle`
#     *   `status` (e.g., 'new', 'contacted', 'engaged', 'converted', 'archived')
#     *   `first_contact_date`
#     *   `last_contact_date`
#     *   Notes / Profile Info...
# [ ] **Table: `conversations`**
#     *   `conversation_id` (Primary Key)
#     *   `participant_id` (FK to leads or clients table)
#     *   `platform` ('instagram_dm')
#     *   `start_time`
#     *   `last_message_time`
# [ ] **Table: `messages`**
#     *   `message_id` (Primary Key)
#     *   `conversation_id` (FK to conversations)
#     *   `timestamp`
#     *   `sender` ('shanbot' or 'user')
#     *   `text_content`
#     *   `message_type` (e.g., 'text', 'tool_call', 'tool_response') (Optional)
# [ ] **Table: `tasks`** (For tracking Orchestrator actions)
#     *   `task_id` (Primary Key)
#     *   `timestamp_created`
#     *   `task_type` (e.g., 'webhook', 'dashboard_command', 'scheduled_checkin')
#     *   `related_id` (e.g., client_id, lead_id)
#     *   `status` ('pending', 'running', 'completed', 'failed')
#     *   `input_data` (JSON/Text)
#     *   `output_data` (JSON/Text)
#     *   `logs` (Text)
# // TODO: Refine schema based on specific data needs.

## 4.3 Database Interaction (`database.py` or ORM setup)
# [ ] Choose Method: Use an ORM (like SQLAlchemy for Python) or write raw SQL queries.
# [ ] Implement Functions:
#     *   Connect/Disconnect from DB.
#     *   CRUD operations (Create, Read, Update, Delete) for each table.
#     *   Functions needed by Orchestrator/Tools (e.g., `get_conversation_history(user_id)`, `save_message(...)`, `update_task_status(...)`, `get_client_info(client_id)`).

# --- SECTION 5: Senses & Input Handling ---

## 5.1 Webhook Receiver (`webhook_handler.py` or part of Dashboard Backend)
# Purpose: Receive incoming webhooks (e.g., from ManyChat for Instagram DMs).
# Note: This function is largely fulfilled by the standalone `manychat_webhook_fullprompt.py` service.
# If other webhook types are needed, or if a simpler intermediary is desired, this section could be re-activated.
# Consider if the existing `manychat_webhook_fullprompt.py` should push tasks onto a queue for the main orchestrator instead of handling everything internally.
# [ ] Framework: Use Flask, FastAPI, or similar Python web framework.
# [ ] Endpoint Definition: Create a URL endpoint (e.g., `/webhooks/manychat`).
# [ ] Security: Implement verification for webhook authenticity (e.g., secret tokens).
# [ ] Data Parsing: Extract relevant information from the webhook payload (user ID, message content, etc.).
# [ ] **Asynchronous Processing (Recommended):**
#     *   Instead of processing directly in the request handler (which can cause timeouts):
#     *   Put the parsed webhook data onto a message queue (e.g., Celery with Redis/RabbitMQ).
#     *   Have a separate worker process (part of the Orchestrator?) consume tasks from the queue.
#     *   This makes the webhook receiver fast and reliable.
# [ ] Trigger Orchestrator: Pass the parsed data as a 'task' to the Orchestrator.

## 5.2 Dashboard Commands (See Section 6 - Dashboard Backend)
# Purpose: Allow manual triggering of Shanbot actions via the dashboard.
# Logic resides in the Dashboard Backend API endpoints.

# --- SECTION 6: The Control Panel - Dashboard ---

## 6.1 Technology Choice
# [ ] Backend Framework: Flask, FastAPI, Django (Python).
# [ ] Frontend Framework: React, Vue, Angular, or simple HTML/CSS/JavaScript with server-side templates (e.g., Jinja2 with Flask).

## 6.2 Dashboard Backend (`dashboard_app.py` or similar)
# Purpose: Serves the frontend UI and provides APIs for interaction.
# [ ] **API Endpoints:**
#     *   `/api/send_command`: Receives commands for Shanbot from the frontend. Validates input, creates a task, sends it to the Orchestrator (e.g., via queue or direct call). Returns a task ID for tracking.
#     *   `/api/tasks`: Retrieves list/status of ongoing or recent tasks from the `tasks` database table.
#     *   `/api/tasks/<task_id>`: Retrieves details/logs for a specific task.
#     *   `/api/clients`: Retrieves client list/data from the database.
#     *   `/api/leads`: Retrieves lead list/data from the database.
#     *   `/api/conversations/<participant_id>`: Retrieves conversation history.
#     *   (Endpoints for your existing data analysis visualizations).
# [ ] **Authentication:** Implement secure login for yourself (e.g., username/password, OAuth). Protect all API endpoints.
# [ ] **Database Connection:** Connects to the database (using logic from Section 4.3).
# [ ] **Orchestrator Connection:** Defines how the dashboard tells the orchestrator to start a task.

## 6.3 Dashboard Frontend (`templates/` or `frontend/` directory)
# Purpose: User interface for monitoring and control.
# [ ] **UI Components (Based on earlier design):**
#     *   Overview Metrics Display.
#     *   Shanbot Command Input Area & Log/Response Display.
#     *   Client List/Detail View.
#     *   Lead List/Detail View.
#     *   Task Queue/Log Viewer.
#     *   Settings Page (API Keys - view/update if needed).
#     *   Existing Data Analysis Visualizations.
# [ ] **Interaction Logic (JavaScript):**
#     *   Fetch data from backend APIs.
#     *   Display data dynamically.
#     *   Send commands via `/api/send_command`.
#     *   Regularly poll for task status updates (or use WebSockets for real-time updates).

# --- SECTION 7: Operational Aspects ---

## 7.1 Environment Setup (`requirements.txt`, `Dockerfile` - Optional)
# [ ] Define Python version.
# [ ] List all dependencies (`requirements.txt`): `google-generativeai`, `selenium`, `flask`/`fastapi`, `requests`, `python-dotenv`, DB driver (`psycopg2-binary`), ORM (`sqlalchemy`), queue (`celery`, `redis`), etc.
# [ ] Consider Docker for packaging the application and its dependencies.

## 7.2 Running the System
# [ ] Define steps to start:
#     1. Start Database (if local).
#     2. Start Message Queue Broker (Redis/RabbitMQ) (if using for Orchestrator tasks).
#     3. Start ManyChat Webhook Service (`uvicorn manychat_webhook_fullprompt:app ...`).
#     4. Start Orchestrator / Celery Worker(s) (if implemented).
#     5. Start Dashboard Backend Server (`streamlit run analytics_dashboard.py` or Flask/FastAPI app).
#     6. (Optionally run `followersbot2.py` manually or via Orchestrator trigger).

## 7.3 Security Considerations
# [ ] **Credential Management:** NEVER hardcode secrets. Use environment variables, `.env` file (add to `.gitignore`), or a secrets management system.
# [ ] **Input Validation:** Sanitize/validate all external input (webhooks, dashboard commands).
# [ ] **Authentication/Authorization:** Secure the dashboard properly. Verify webhook signatures.
# [ ] **Rate Limiting:** Implement rate limiting on API endpoints and outgoing API calls (Gemini, Instagram).
# [ ] **Error Handling:** Ensure errors don't expose sensitive information.

## 7.4 Testing Strategy
# [ ] **Unit Tests:** Test individual functions (e.g., response parsing, DB queries).
# [ ] **Integration Tests:** Test interaction between components (e.g., does dashboard command trigger orchestrator correctly?).
# [ ] **End-to-End Tests:** Simulate user flows (e.g., send webhook -> check for DM -> verify DB log). (More complex).

# --- SECTION 8: Business Logic & Future ---

## 8.1 Free Trial / Paid Tier Logic
# [ ] Database: Add fields to `clients` table (e.g., `tier` ('free'/'paid'), `trial_start_date`, `subscription_status`).
# [ ] Orchestrator/Tools: Modify logic to check client tier before executing certain actions or using certain features.
# [ ] Dashboard: Display tier status.

## 8.2 Billing Integration (Future)
# [ ] Choose Provider: Stripe, Paddle.
# [ ] Implement API integration for subscription management.
# [ ] Webhooks from billing provider to update client status in DB.

## 8.3 Potential Enhancements (Future)
# [ ] More sophisticated context management (Vector DB / RAG).
# [ ] Proactive task scheduling (e.g., auto-generate check-ins every Sunday).
# [ ] More advanced data analysis and insights.
# [ ] A/B testing different message strategies.

# --- End of Blueprint ---


How to Use This in Cursor:

Save: Save this entire text as a Markdown file (e.g., SHANBOT_BLUEPRINT.md) in the root of your project directory.

Navigate: Use Cursor's outlining features (if available for Markdown) or just scroll through the sections.

Implement: As you build each component (Orchestrator, Tool Wrappers, Dashboard), refer back to the relevant section in this blueprint.

Fill in Details: Replace placeholders like [Your Specific Error Handling Logic] with actual code or more detailed notes. Use the // TODO: comments as reminders.

Refine: This is a starting point. As you build, you'll likely refine the details, add more specific notes, and update the blueprint to reflect your actual implementation. Use Cursor's AI features to help you write the code based on these instructions.

This blueprint provides the structure and detailed instructions you requested. It's now up to you to start filling it in with your code, guided by this plan. Start with Section 1 (refining the prompt) and Section 2 (setting up the basic orchestrator structure), then move to Section 3 (wrapping one or two key scripts). Build incrementally!

# Implementation Plan: Enhanced Engagement System

## 1. Followup Manager Updates
### Required Changes:
- Add engagement level detection
- Implement timing rules based on engagement level
- Create topic progression tracking
- Add trial period management
- Implement paid client scheduling
- Add conversation state tracking

```python
# New structures needed:
ENGAGEMENT_LEVELS = {
    "High": {"min_messages": 51, "follow_up_days": 2},
    "Medium": {"min_messages": 11, "follow_up_days": 5},
    "Low": {"min_messages": 1, "follow_up_days": 7},
    "None": {"min_messages": 0, "follow_up_days": None}
}

CONVERSATION_STATES = {
    "initial_topics": ["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Health/Fitness"],
    "trial_period": ["Week 1", "Week 2-3", "Week 4"],
    "paid_client": "active"
}
```

### Implementation Steps:
1. Create engagement detection system
2. Implement conversation state machine
3. Add topic progression tracking
4. Build trial period scheduler
5. Create paid client management
6. Add error handling and recovery

## 2. Analytics Dashboard Updates
### Required Changes:
- Add engagement level tracking
- Create conversation flow visualization
- Add topic progression tracking
- Implement trial period monitoring
- Add conversion analytics
- Create success metrics

### New Dashboard Sections:
```python
# New metrics to track
new_metrics = {
    "engagement_levels": {
        "high": {"count": 0, "conversion_rate": 0},
        "medium": {"count": 0, "conversion_rate": 0},
        "low": {"count": 0, "conversion_rate": 0}
    },
    "conversation_progress": {
        "topic_completion_rates": {},
        "average_time_between_topics": {},
        "trial_conversion_rates": {}
    }
}
```

### Implementation Steps:
1. Update data structures
2. Create new visualization components
3. Add engagement tracking
4. Implement progress monitoring
5. Create conversion tracking
6. Add success metrics

## 3. Gemini Prompt Updates
### Required Changes:
- Add conversation context awareness
- Implement topic progression logic
- Add trial period messaging
- Create paid client communication
- Implement engagement detection

### New Prompt Sections:
```python
PROMPT_UPDATES = {
    "context_awareness": """
    You are managing a progressive conversation flow with 5 topics.
    Current topic: {current_topic}
    Previous topics discussed: {previous_topics}
    Engagement level: {engagement_level}
    Trial status: {trial_status}
    """,
    
    "topic_progression": """
    Guide the conversation naturally towards completion of current topic.
    Look for opportunities to conclude when appropriate.
    Prepare for transition to next topic: {next_topic}
    """,
    
    "trial_management": """
    Week {week_number} of trial
    Message type: {message_type} (encouragement/check-in/review)
    Include relevant meal ideas and check-in requirements
    """
}
```

### Implementation Steps:
1. Update base prompts
2. Add context management
3. Implement topic awareness
4. Create trial period prompts
5. Add paid client communication
6. Test and refine responses

## 4. Followers Bot Updates
### Required Changes:
- Add initial topic detection
- Implement profile analysis for conversation topics
- Create engagement potential scoring
- Add conversation initialization

### New Analysis Features:
```python
PROFILE_ANALYSIS = {
    "topic_detection": {
        "personal_interests": [],
        "fitness_related": [],
        "conversation_starters": []
    },
    "engagement_scoring": {
        "post_frequency": 0,
        "interaction_rate": 0,
        "fitness_interest": 0
    }
}
```

### Implementation Steps:
1. Update profile scanning
2. Implement topic detection
3. Add engagement scoring
4. Create conversation starters
5. Implement initialization logic

## 5. Database Updates
### New Tables/Collections:
```sql
-- Conversation Progress
CREATE TABLE conversation_progress (
    user_id TEXT PRIMARY KEY,
    current_topic INTEGER,
    topics_completed TEXT[],
    last_interaction TIMESTAMP,
    engagement_level TEXT,
    trial_status TEXT
);

-- Follow-up Schedule
CREATE TABLE followup_schedule (
    user_id TEXT,
    next_followup TIMESTAMP,
    topic_number INTEGER,
    message_type TEXT,
    scheduled_content TEXT
);
```

### Implementation Steps:
1. Create new data structures
2. Update existing tables
3. Add migration scripts
4. Implement data tracking
5. Add analytics queries

## 6. Testing Plan
### Test Cases:
1. Engagement Level Detection
2. Topic Progression
3. Trial Period Management
4. Paid Client Communication
5. Follow-up Timing
6. Error Handling

### Implementation Steps:
1. Create test scenarios
2. Build test data
3. Implement test suite
4. Create monitoring tools
5. Add performance metrics

## Timeline and Priority
### Phase 1 (Week 1-2):
- Update Followup Manager
- Modify Analytics Dashboard
- Update Gemini Prompts

### Phase 2 (Week 3-4):
- Update Followers Bot
- Implement Database Changes
- Create Test Suite

### Phase 3 (Week 5-6):
- Testing and Refinement
- Performance Optimization
- Documentation Updates

## Success Metrics
1. Engagement Rates
2. Topic Completion Rates
3. Trial Conversion Rates
4. Client Retention Rates
5. Response Quality Scores

## Monitoring and Maintenance
1. Daily Performance Checks
2. Weekly Analytics Review
3. Monthly System Optimization
4. Quarterly Strategy Review