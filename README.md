# AutoDoc

AutoDoc is an AI-powered documentation generator that runs automatically on every merged pull request. It analyzes changed source files, produces Markdown documentation via an LLM, and publishes the results to Confluence through a Jira-linked review workflow.

## Architecture overview

AutoDoc has three components that work together:

| Component | Location | Role |
|-----------|----------|------|
| **autodoc-backend** | `autodoc-backend/` | Python CLI + FastAPI server. Clones the repo, groups files into logical units, calls an LLM (via OpenRouter), and returns structured Markdown. |
| **Forge app** | `jira-confluence-app/autodoc-test/` | Atlassian Forge app. Receives generated docs via a signed webhook, stores them for review in Jira, and publishes approved docs to Confluence. |
| **GitHub Actions workflow** | `.github/workflows/autodoc.yml` | Reusable workflow. Triggers on PR merge, calls the backend API, polls for completion, then pushes results to the Forge webhook. |

For full C4 diagrams and a deeper architectural walkthrough, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Repository layout

```
Part3_Auto_Doc/
├── autodoc-backend/          # Python package: CLI + FastAPI server
│   ├── src/autodoc/          # Source: cli.py, server.py, config.py, llm.py, …
│   ├── tests/                # pytest test suite
│   └── pyproject.toml        # Entry points: autodoc, autodoc-server
│
├── jira-confluence-app/
│   └── autodoc-test/         # Atlassian Forge app
│       ├── src/index.js      # Webtrigger + resolver handlers
│       └── manifest.yml      # Forge app manifest
│
├── .github/
│   └── workflows/
│       └── autodoc.yml       # Reusable GitHub Actions workflow
│
└── README.md                 # This file
```

## Quick-start

### 1. Deploy the backend API server

See [`autodoc-backend/README.md`](autodoc-backend/README.md) for installation, configuration, and how to run `autodoc-server`.

### 2. Deploy the Forge app

See [`jira-confluence-app/autodoc-test/README.md`](jira-confluence-app/autodoc-test/README.md) for `forge deploy`, install instructions, and how to obtain the webhook URL.

### 3. Add the workflow to a target repository

In any repo you want to auto-document, create `.github/workflows/autodoc.yml`:

```yaml
name: AutoDoc

on:
  pull_request:
    types: [closed]

jobs:
  autodoc:
    uses: <your-org>/Part3_Auto_Doc/.github/workflows/autodoc.yml@main
    with:
      confluence_space_key: "DOCS"       # your Confluence space key
      # jira_issue_key: "PROJ-123"       # optional — auto-detected from PR body
    secrets:
      AUTODOC_API_URL:        ${{ secrets.AUTODOC_API_URL }}
      AUTODOC_API_KEY:        ${{ secrets.AUTODOC_API_KEY }}
      AUTODOC_WEBHOOK_URL:    ${{ secrets.AUTODOC_WEBHOOK_URL }}
      AUTODOC_WEBHOOK_SECRET: ${{ secrets.AUTODOC_WEBHOOK_SECRET }}
```

## Required secrets

Set these in the target repository's **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AUTODOC_API_URL` | Base URL of the hosted AutoDoc API server (e.g. `https://autodoc.example.com`) |
| `AUTODOC_API_KEY` | Bearer token for the AutoDoc API server (set via `AUTODOC_API_KEY` env var on the server) |
| `AUTODOC_WEBHOOK_URL` | Forge webtrigger URL (obtained from `forge webtrigger` after deployment) |
| `AUTODOC_WEBHOOK_SECRET` | HMAC secret shared between the workflow and the Forge app |

## How a PR triggers documentation

1. A pull request is **merged** into the target repository.
2. **GitHub Actions** (`autodoc.yml`) fires; it extracts the Jira issue key from the PR body.
3. The workflow sends a `POST /generate` request to the **autodoc-backend API server**, passing the repo name, GitHub token, and the base/head SHAs.
4. The server clones the repo, analyzes changed files, calls the LLM, and returns a job ID.
5. The workflow **polls** `GET /jobs/{job_id}` (up to 10 minutes) until the job status is `done`.
6. The workflow signs the result payload with HMAC-SHA256 and **POSTs to the Forge webtrigger**.
7. The **Forge app** verifies the `X-AutoDoc-Signature` header and stores each documentation unit in Atlassian KVS as a pending doc linked to the Jira issue.
8. A developer opens the **Jira issue panel**, reviews each doc, and clicks **Approve** or **Reject**.
9. On approval, the Forge app creates or updates the **Confluence page hierarchy** and adds a remote link on the Jira issue.
