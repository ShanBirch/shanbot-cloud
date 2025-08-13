# Shannon Bot Analytics System

This analytics system provides comprehensive tracking and analysis for Shannon Bot conversations to improve engagement, detect patterns, and optimize performance.

## Features

- Track message metrics (counts, question frequency, response rates)
- Detect coaching inquiries and AI detection instances
- Analyze conversation engagement patterns
- Generate insights through a visual dashboard
- Export data for further analysis

## Installation

1. Install the requirements:
```bash
pip install -r analytics_requirements.txt
```

2. Integrate with webhook:
```bash
python integrate_analytics.py manychat_webhook.py
```
(Replace with your actual webhook file)

## Usage

### Running the Dashboard

After integrating analytics with your webhook, you can view the analytics dashboard:

```bash
streamlit run analytics_dashboard.py
```

This will open a web browser with the dashboard.

### Accessing Analytics API Directly

You can also access the analytics data directly through the API endpoints:

- `GET /analytics/global` - Overall metrics across all conversations
- `GET /analytics/conversation/{subscriber_id}` - Individual conversation metrics
- `GET /analytics/engagement/{subscriber_id}` - Detailed engagement analysis
- `POST /analytics/export` - Export analytics data to JSON file

Example:
```bash
curl http://localhost:8000/analytics/global
```

### Running the Demo

To see how the analytics system works without integrating with your webhook:

```bash
python analytics_demo.py
```

This will generate sample data and display metrics in the console.

## Components

- `analytics_integration.py` - Core analytics functionality
- `integrate_analytics.py` - Script to add analytics to webhook
- `analytics_dashboard.py` - Streamlit dashboard for visualization
- `analytics_demo.py` - Demo script to show analytics in action

## Using Analytics to Improve Shannon Bot

The analytics data can help improve Shannon Bot in several ways:

1. **Question Optimization**:
   - Identify which questions get better responses
   - Find the optimal number of questions per conversation

2. **AI Detection Prevention**:
   - Track when users suspect they're talking to an AI
   - Modify responses to maintain Shannon's persona

3. **Conversion Optimization**:
   - Find patterns in successful coaching inquiries
   - Optimize timing of coaching offers

4. **Engagement Enhancement**:
   - Compare response rates with/without questions
   - Identify topics that drive conversation

## Troubleshooting

- If the analytics endpoints are not accessible, make sure your FastAPI server is running with the integrated analytics.
- If the dashboard cannot connect to the server, check the URL settings in the sidebar.
- If you see "No data available", you may need to generate some conversation data first.

## Support

If you encounter any issues or have questions, contact your administrator. 