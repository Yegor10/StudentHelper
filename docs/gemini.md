# Configure the Gemini API

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Open StudentHelper's **Settings** tab.
3. Paste the key in the masked **Gemini API key** field and save.
4. Choose a Gemini model available to your API key. The default comes from `GEMINI_MODEL` in `.env` (initially `gemini-1.5-flash`).
5. Add a homework task in the Diary and select **Solve with AI**.

The API key is written to the project-local `.env` file, which is excluded by `.gitignore`. Keep it private and do not include it in screenshots or shared logs. If a model is no longer available to your account, change the model name in Settings to a currently supported Gemini model.

StudentHelper sends the homework prompt and any attached image to Google Gemini when you request a solution. Do not attach sensitive personal information.

If the key is missing or the API request fails, the app displays the error in the diary instead of treating it as a successful response.
