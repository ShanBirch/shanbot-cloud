# Shannon Bot Analytics Dashboard

A comprehensive analytics dashboard for Shannon's Instagram fitness bot, built with Streamlit.

## Features

- 📊 **Overview Dashboard** - Key metrics and performance indicators
- 👥 **User Profiles** - Detailed user information and conversation history
- 📅 **Scheduled Follow-ups** - Automated follow-up management
- 📝 **Response Review Queue** - AI response review and approval system
- 📋 **Daily Reports** - Action items and task management
- 💬 **Recent Interactions** - 30-day conversation history
- 🤖 **AI Integration** - Powered by Google Gemini AI

## Cloud Deployment

This dashboard is deployed on Streamlit Cloud with the following integrations:

- **Google Sheets** - For client data and trial signups
- **Gemini AI** - For intelligent response generation
- **ManyChat API** - For message sending (local version only)
- **SQLite Database** - For conversation storage (local version only)

## Files

- `dashboard_cloud.py` - Cloud-compatible demo version
- `dashboard.py` - Full local version with SQLite integration
- `requirements.txt` - Python dependencies
- `.streamlit/secrets.toml` - Configuration secrets

## Local Development

To run locally:

```bash
streamlit run dashboard.py
```

## Demo Version

The cloud version (`dashboard_cloud.py`) includes:
- Sample data for demonstration
- All UI components and layouts
- Google Sheets and Gemini AI integration
- Responsive design for mobile access

## Author

Shannon - Fitness Coach & Bot Developer 