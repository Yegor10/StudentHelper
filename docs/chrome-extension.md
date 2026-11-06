# Chrome extension

The extension replaces the separate Playwright browser with the normal Chrome profile. Google sign-in happens in Chrome itself; no automated Chromium login or service-account key is used.

## Load the extension

1. Open `chrome://extensions`.
2. Turn on **Developer mode**.
3. Select **Load unpacked** and choose the repository's `extension/chrome` folder.
4. Copy the extension ID shown by Chrome.

## Configure OAuth for this extension

The Google Classroom API key or service-account JSON is **not** an extension sign-in credential. The extension requires a Chrome-specific OAuth client:

1. In Google Cloud Console, open the project where the Classroom API is enabled. Enable the **Google Drive API** too; it is used only to upload a work file that you select.
2. Configure the OAuth consent screen. While the app is in testing mode, add your own Google account as a test user.
3. Create an OAuth client with application type **Chrome Extension**. Enter the extension ID copied from `chrome://extensions`.
4. Copy the generated public Client ID into `oauth2.client_id` in `extension/chrome/manifest.json`, replacing the placeholder. Do not copy a client secret into the extension.
5. Reload the unpacked extension at `chrome://extensions`, then open StudentHelper and select **Підключити Google**.

The OAuth Client ID previously supplied in chat is not embedded: Google `identity.getAuthToken` requires a Chrome Extension client associated with this extension's ID. A client secret is never needed or safe to bundle. Google may show an unverified-app warning until the OAuth consent screen is configured and, for a public release, verified.

The extension requests access to active courses, your coursework/submissions, and files created by StudentHelper. School-admin policies may block these scopes. Classroom's attachment/turn-in API also enforces its developer-project permissions; an API `PERMISSION_DENIED` message is surfaced in the extension.

## Use Classroom

1. Connect your Google account and refresh assignments. The list is ordered by the nearest deadline; submissions already turned in or returned and assignments past their deadline are hidden. Assignments due today without a specific time remain visible through the end of the day.
2. Choose a course assignment and select a work file from your PC (maximum 12 MB).
3. Choose **Прикріпити файл** and review the confirmation that it is attached.
4. Only when ready, choose **Перевірити й здати** and confirm the dialog. Attaching a file does not submit it automatically.

AI help is optional. Add a Gemini key under **Налаштування AI** if you want an explanation of assignment text. The key is stored in the extension's local browser storage, which is not an encrypted secrets vault. Gemini receives the assignment text only after you explicitly request help. You can download the answer as a text file and select it as an attachment, but it is not submitted automatically.

## Schedule

The five-day schedule is pre-filled for Group 151, first shift, and stored in Chrome local storage. Edit it under **Розклад**. Chrome schedules alarms for links over a rolling two-week period and opens meeting links one minute before class.

The extension opens a normal Meet tab; it does not automatically click **Join**, mute the microphone, or disable the camera. Check the meeting tab and confirm those controls yourself. Chrome can delay alarms while the computer sleeps, so the extension is not a substitute for checking your class schedule.

## Privacy and credential safety

- Never put an OAuth client secret, service-account JSON, or private key in extension source.
- A Gemini key stored in browser extension storage is accessible to this browser profile and its extensions; use a dedicated key and revoke it if exposed.
- The service-account JSON file in the project is ignored by Git. Do not commit or distribute it. Student Classroom access must use your own Google account's OAuth consent, not that service-account key.
- Disconnecting Google can be done from your Google Account's third-party connections page.
