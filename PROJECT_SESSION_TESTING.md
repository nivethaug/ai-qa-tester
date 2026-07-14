# Project Creation and Session Chat Testing

This guide explains how to use the QA tester to validate DreamAgent project creation and follow-up edits through the same session chat flow used by the web app.

## 1. Configure Auth

The backend is auth-gated. Set a DreamAgent user token before running tests.

PowerShell:

```powershell
$env:BACKEND_AUTH_TOKEN="YOUR_TOKEN"
```

Bash:

```bash
export BACKEND_AUTH_TOKEN="YOUR_TOKEN"
```

The token controls which account owns the test projects. The tester only sees and edits projects available to that account.

## 2. Create A Project

Run a website-only smoke test:

```bash
python main.py --stability-suite --types 1
```

Run all active creation flows:

```bash
python main.py --stability-suite --types 1,2,3,5
```

Project type IDs:

- `1` Website
- `2` Telegram Bot
- `3` Discord Bot
- `5` Scheduler

The tester calls:

```text
POST /projects
GET /projects/{project_id}/status
```

It waits until the project reaches a terminal success status:

```text
ready
verified
running
```

If the project reaches `failed`, `error`, `deleted`, or times out, the suite marks creation as failed.

## 3. Edit The Project Via Session Chat

When `STABILITY_RUN_FEATURE_EDIT=true`, the tester creates a project session and sends an edit prompt through the session chat API.

The tester calls:

```text
POST /projects/{project_id}/sessions
POST /chat
GET /sessions/{session_id}/messages
POST /sessions/{session_id}/release-lock
```

The `/chat` request uses the same streaming mode as the web chatbox:

```json
{
  "session_key": "SESSION_KEY",
  "messages": [
    {
      "role": "user",
      "content": "Add a small QA release notes section..."
    }
  ],
  "stream": true,
  "acp_mode": true,
  "mode": "dream"
}
```

The tester reads Server-Sent Events from the stream. If the HTTP stream drops but the backend continues in the background, the tester polls `GET /sessions/{session_id}/messages` and uses the saved assistant message as the final result.

The tester always attempts to release the session lock after the edit test, so a failed QA run does not leave the project blocked.

## 4. Environment Variable Testing

Enable create-time env var testing with:

```env
STABILITY_USE_INITIAL_ENV=true
```

Add up to two env rows:

```env
STABILITY_ENV1_KEY=EXAMPLE_API_KEY
STABILITY_ENV1_VALUE=replace-with-test-key
STABILITY_ENV1_DOCS_URL=https://example.com/docs
STABILITY_ENV1_DESCRIPTION=Example API used during QA project generation

STABILITY_ENV2_KEY=SECOND_API_KEY
STABILITY_ENV2_VALUE=replace-with-test-key
STABILITY_ENV2_DOCS_URL=https://example.com/docs
STABILITY_ENV2_DESCRIPTION=Optional second integration
```

Rules:

- Maximum two custom env vars.
- `KEY`, `VALUE`, and `DOCS_URL` are required.
- `DOCS_URL` must start with `http://` or `https://`.
- Incomplete rows are skipped and logged.
- Raw values are sent only to the backend create API, not written into report summaries.

## 5. Useful Test Modes

Create projects only, without edit-session testing:

```powershell
$env:STABILITY_RUN_FEATURE_EDIT="false"
python main.py --stability-suite --types 1
```

Run website creation and edit-session testing:

```powershell
$env:STABILITY_RUN_FEATURE_EDIT="true"
python main.py --stability-suite --types 1
```

Run all active types but edit only websites:

```powershell
$env:STABILITY_PROJECT_TYPES="1,2,3,5"
$env:STABILITY_EDIT_PROJECT_TYPES="1"
python main.py --stability-suite
```

## 6. Read The Report

Reports are written to:

```text
reports/stability_YYYYMMDD_HHMMSS.json
```

Important fields:

- `created`: project create API succeeded.
- `ready`: project reached a success status.
- `feature_edit.ok`: session chat edit succeeded.
- `feature_edit.lock_released`: tester released the session lock after the run.
- `feature_edit.response_source`: `stream_response` or `saved_session_message`.
- `feature_edit.transport_error`: stream transport dropped, but backend may still have completed.
- `feature_edit.failure_class`: stable failure reason if the edit failed.

Common `failure_class` values:

- `edit_runtime_missing`: backend edit runtime is missing or unavailable.
- `session_busy`: another message is already running for the session.
- `insufficient_credits`: account does not have enough credits.
- `editor_initialization_failed`: backend could not initialize the project editor session.
- `edit_failed`: generic edit failure.
- `no_response`: no stream output or saved assistant response was found.

## 7. Expected Healthy Result

A healthy website smoke test should look like this in the terminal:

```text
DreamAgent stability suite
Result: PASS
- PASS website project=1234 domain=qa-premium-site-...
```

For a full run, every selected project type should pass creation. Edit-session testing should pass for any type included in `STABILITY_EDIT_PROJECT_TYPES`.
