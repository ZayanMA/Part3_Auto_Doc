# AutoDoc — Forge App

Atlassian Forge app that receives auto-generated documentation from the autodoc-backend
and publishes it to Confluence, then attaches it to the correct Jira ticket.

## How it works

```
GitHub PR opened / updated
        │
        ▼
GitHub Actions (.github/workflows/autodoc.yml)
  1. Runs autodoc-backend to generate markdown docs
  2. POSTs each doc to the Forge webtrigger endpoint
        │
        ▼
Forge Webtrigger  (src/index.js → webhookHandler)
  1. Validates webhookSecret
  2. Creates / updates a Confluence page with the markdown
  3. Attaches a remote link on the Jira issue → Confluence page
        │
        ▼
Jira Issue Panel  (static/hello-world/src/App.js)
  Shows all AutoDoc-linked Confluence pages directly on the ticket
```

## First-time setup

### 1. Install dependencies and build the frontend

```bash
npm install
cd static/hello-world && npm install && npm run build && cd ../..
```

### 2. Deploy and install the Forge app

```bash
forge deploy --non-interactive --e development
forge install --non-interactive --site <your-site>.atlassian.net --product jira --environment development
forge install --non-interactive --upgrade --site <your-site>.atlassian.net --product confluence --environment development
```

### 3. Get the webtrigger URL

```bash
forge webtrigger
```

Copy the URL for `autodoc-webhook` — this becomes your `FORGE_WEBHOOK_URL` GitHub secret.

### 4. Set the webhook secret (recommended)

```bash
forge variables set WEBHOOK_SECRET your-chosen-secret
```

### 5. Configure GitHub Actions secrets

| Secret | Description |
|---|---|
| `FORGE_WEBHOOK_URL` | Webtrigger URL from `forge webtrigger` |
| `AUTODOC_WEBHOOK_SECRET` | Same value set with `forge variables set` |
| `CONFLUENCE_SPACE_KEY` | Key of the target Confluence space (e.g. `DOCS`) |
| `CONFLUENCE_PARENT_PAGE_ID` | (Optional) ID of a parent Confluence page |
| `ANTHROPIC_API_KEY` | Your Anthropic API key for autodoc-backend |

### 6. PR title convention

The GitHub pipeline extracts the Jira ticket key from the PR title.
Format PR titles as:

```
PROJ-123: Brief description of changes
```

## Webhook payload format

If calling the endpoint manually or from a custom system:

```json
{
  "jiraKey": "PROJ-123",
  "docTitle": "Module: Authentication",
  "docContent": "# Authentication\n...(markdown)...",
  "confluenceSpaceKey": "DOCS",
  "parentPageId": "12345678",
  "webhookSecret": "your-chosen-secret"
}
```

`parentPageId` is optional. `webhookSecret` is required if you set one via `forge variables set`.

## Local development

```bash
forge tunnel
```

## Deployment

```bash
cd static/hello-world && npm run build && cd ../..
forge deploy --non-interactive --e development
```
