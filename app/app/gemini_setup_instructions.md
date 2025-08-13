# Setting Up Gemini AI for Auto Follow-up Messages

The analytics dashboard now includes Gemini AI integration for generating personalized follow-up messages based on conversation history. This feature creates more engaging and contextually relevant messages compared to template-based approaches.

## Setup Instructions

1. **Get a Gemini API Key**:
   - Visit the [Google AI Studio](https://ai.google.dev/) and sign in with your Google account
   - Navigate to "Get API key" in the top menu
   - Either create a new API key or use an existing one
   - Copy the API key for the next step

2. **Configure Your API Key**:
   Choose one of these methods to make the API key available to the application:

   **Option 1: Environment Variable**
   - Set an environment variable named `GEMINI_API_KEY` with your API key
   - On Windows: 
     ```
     setx GEMINI_API_KEY "your-api-key-here"
     ```
   - On macOS/Linux:
     ```
     export GEMINI_API_KEY="your-api-key-here"
     ```

   **Option 2: Streamlit Secrets**
   - Create or edit the `.streamlit/secrets.toml` file in your project root
   - Add the following line:
     ```
     GEMINI_API_KEY = "your-api-key-here"
     ```
   - Make sure to keep this file secure and not commit it to version control

3. **Test the Integration**:
   - Start the analytics dashboard
   - Expand the "Test Gemini Follow-up Message Generator" section
   - Click "Generate Follow-up Message" to see a comparison between the AI-generated message and the standard template

## Features

- **Personalized Messages**: Gemini analyzes conversation history to create highly personalized follow-up messages
- **Context Awareness**: Messages reference specific topics discussed in the conversation
- **Fallback Mechanism**: If Gemini is unavailable, the system falls back to template-based messages
- **Customizable Prompts**: You can modify the prompt in the `generate_ai_follow_up_message` function to change how messages are generated

## Troubleshooting

- **API Key Issues**: Make sure your API key is active and has appropriate permissions
- **Error Messages**: Check the Streamlit error messages for specific issues with the Gemini API
- **Rate Limits**: Be aware of Google's rate limits for API requests and adjust usage accordingly

For more information, see the [Google Generative AI Python SDK documentation](https://ai.google.dev/tutorials/python_quickstart). 