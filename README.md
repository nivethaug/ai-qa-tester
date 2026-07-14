# DreamAgent AI QA Tester

Backend-focused QA harness for release stability checks.

## Continuous tester

```bash
python main.py
```

Creates projects on an interval, polls status, and verifies website projects.

## Product stability suite

Run a controlled end-to-end release pass:

```bash
python main.py --stability-suite
```

Run only selected project types:

```bash
python main.py --stability-suite --types 1,2,3,5
```

Project type IDs:

- `1` Website
- `2` Telegram bot
- `3` Discord bot
- `5` Scheduler

The suite covers:

- New project creation through authenticated `POST /projects`
- Readiness polling through `GET /projects/{id}/status`
- Optional create-time environment variables
- Add-feature/edit session creation through `POST /projects/{id}/sessions`
- Session chat through `POST /chat`
- Session message persistence check through `GET /sessions/{id}/messages`

Reports are written to:

```text
reports/stability_YYYYMMDD_HHMMSS.json
```

## Environment variable integration testing

Creation-time env vars are optional and capped at two entries, matching DreamAgent backend rules.

```env
STABILITY_USE_INITIAL_ENV=true
STABILITY_ENV1_KEY=EXAMPLE_API_KEY
STABILITY_ENV1_VALUE=replace-with-test-key
STABILITY_ENV1_DOCS_URL=https://example.com/docs
STABILITY_ENV1_DESCRIPTION=Example API used to verify create-time env integration behavior

STABILITY_ENV2_KEY=SECOND_API_KEY
STABILITY_ENV2_VALUE=replace-with-test-key
STABILITY_ENV2_DOCS_URL=https://example.com/docs
STABILITY_ENV2_DESCRIPTION=Optional second integration
```

Only complete rows are sent. Incomplete rows are skipped and logged.

## Useful suite settings

```env
STABILITY_PROJECT_TYPES=1,2,3,5
STABILITY_EDIT_PROJECT_TYPES=1,2,3,5
STABILITY_RUN_FEATURE_EDIT=true
STABILITY_WAIT_TIMEOUT=2400
STABILITY_POLL_INTERVAL=20
```

For a faster smoke test:

```bash
STABILITY_PROJECT_TYPES=1 STABILITY_EDIT_PROJECT_TYPES=1 python main.py --stability-suite
```

## Required backend auth

Set one of:

```env
BACKEND_AUTH_TOKEN=...
AUTH_TOKEN=...
```

The token must belong to the user whose projects should be created and tested.
