# Chrome posting capture

The `extension/` directory contains the Manifest V3 Jobbr extension. It captures only after you click **Capture current tab**, then lets you edit the URL and visible page text. **Save to Jobbr** sends the reviewed preview using the real `POST /jobbr/api/jobs` schema: `{url, text?}`. There are no background scripts, automatic captures, remote scripts, analytics, or scheduled scraping.

## Install

1. Use Chrome 109 or newer. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select this repository’s `extension/` directory (not `mini_extension/`).
3. Pin Jobbr from Chrome’s extensions menu, open a job posting, and click its icon.
4. Select **Local** (`http://localhost:8000/jobbr`) or **Production** (`https://jckail.com/jobbr`). Start the local backend before using Local.
5. Click **Capture current tab**. Review the URL and editable posting text; remove unrelated or personal information. Then click **Save to Jobbr** and keep the popup open until the result appears.

The extension requires no build step. Reload it on `chrome://extensions` after editing files. The legacy `mini_extension/` remains preserved and is not used by this extension.

## Permissions and data handling

- `activeTab` and `scripting` allow a one-time read of the current tab following your click. There are no persistent content scripts or broad posting-site host permissions.
- `storage` persists only your destination selection in local storage. API tokens stay in `chrome.storage.session`, restricted to trusted extension contexts and cleared on browser restart, extension reload/update, or **Forget token**. Tokens are separate for Local and Production; this extension never reads the app’s storage or exports a token to page scripts.
- Host permissions cover only `http://localhost:8000/*` and `https://jckail.com/*`. Chrome host patterns cannot restrict a port, but the request implementation and Content Security Policy restrict the local destination to port 8000. The app URLs are fixed constants and cannot be replaced with arbitrary destinations. Requests reject redirects and omit browser cookies.
- Captured previews stay in the popup’s memory until you save. Closing it discards the preview. The preview contains only the top page’s URL and rendered `document.body.innerText`, at most 60,000 characters. It does not read cookies, network traffic, iframe contents, HTML source, or input values deliberately.
- URL fragments are removed; query parameters remain visible for review. Do not send URLs or posting text containing access tokens, private messages, applicant data, or other material you do not want stored by the selected Jobbr instance. Jobbr’s configured extractor may send posting text to its configured LLM provider.

## Authentication

For a token-protected instance, expand **API token** and enter that instance’s `JOBBR_API_TOKEN`. Saves use `X-Jobbr-Token`. Never embed a token in the extension source, URL, or manifest. The token is transmitted to the selected approved instance only when saving.

Browser sign-in (OIDC) instances require authenticated HttpOnly sessions and CSRF protection with the application’s web origin. This extension checks `/jobbr/api/config` before saving and explains the limitation when `auth_enabled` is true. It does not impersonate that origin or bypass those protections. **Saving to an OIDC-enabled instance is currently unsupported**; use the signed-in Jobbr app’s paste/import flow. A separate, reviewed extension authorization flow is required to support that mode. The extension supports the backend’s token mode and open local mode; it does not promise that production accepts tokens if production uses OIDC.

## Limits and troubleshooting

- Chrome internal pages, extension pages, the Chrome Web Store, and other restricted tabs cannot be captured. Use the Jobbr app’s paste flow instead.
- Navigation menus and other visible page text can appear in the preview. Remove them before saving. Pages inside frames and closed shadow roots may be incomplete. Scroll or reveal the posting first if its text loads lazily.
- Text is capped at 60,000 characters, with a visible truncation message. Clearing it saves a URL-only payload, allowing Jobbr’s server to fetch the posting; login-protected sites generally need captured text.
- Capture does not save a screenshot or attachments. It captures the tab at the moment you click, not subsequent page changes.
- Closing the popup during a request can interrupt confirmation even if Jobbr saved the posting. A timeout or connection failure can also leave an unknown outcome: check Jobbr before retrying. The extension times out after 90 seconds.
- A locked message means the instance requires authentication. Check the selected destination and token; use the signed-in app for OIDC instances. A network error can mean the local server is stopped, the approved deployment path is unavailable, or a proxy blocked the request.

## Verification

Run from the repository root:

```sh
node --check extension/popup.mjs
node --check extension/core.mjs
node --test extension/core.test.mjs
```

Core tests verify destination restrictions, dangerous posting URLs, payload bounds, exact API routing, cookie omission, redirect rejection, and error handling. Chrome UI checks require loading the unpacked extension: verify a normal posting capture, preview edits, a restricted page error, local save, wrong-token rejection, destination switching, and token clearing after extension reload. No end-to-end browser result is claimed by the Node checks.
