# StudentHelper Chrome extension

## Development

1. Load `chrome` as an unpacked extension from `chrome://extensions`.
2. Create a Google Cloud OAuth client of type **Chrome Extension** for the displayed extension ID.
3. Replace the OAuth client ID placeholder in `chrome/manifest.json` and reload the extension.
4. Enable Google Classroom API and Google Drive API, and add your account as an OAuth test user.

See [the full setup and usage guide](../docs/chrome-extension.md).

No client secret or service-account credential belongs in this folder.
