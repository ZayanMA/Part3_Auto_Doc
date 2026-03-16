# autodoc-test (Forge app)

Atlassian Forge app that receives AI-generated documentation from the AutoDoc CI pipeline, queues docs for human review inside a Jira issue panel, and publishes approved docs to Confluence.

## How it works

```
GitHub PR merged
  → GitHub Actions (autodoc.yml)
      → POST /generate to autodoc-backend API
      → Poll GET /jobs/{job_id} until done
      → POST to Forge webtrigger (HMAC-SHA256 signed)
  → Forge webhookHandler
      → Verifies X-AutoDoc-Signature header
      → Stores each documentation unit in Atlassian KVS (pending)
  → Developer opens Jira issue panel
      → Reviews pending docs one by one
      → Approves or rejects each
  → On approval:
      → Forge creates/updates Confluence page hierarchy
          [AutoDoc] <repo-name>
            ├── API
            ├── Models
            ├── Config
            ├── CLI
            ├── Tests
            └── Modules
      → Links the Confluence page to the Jira issue as a remote link
```

## First-time setup

### Prerequisites

- [Forge CLI](https://developer.atlassian.com/platform/forge/getting-started/) installed: `npm i -g @forge/cli`
- Logged-in Atlassian account: `forge login`

### Install dependencies

```bash
cd jira-confluence-app/autodoc-test
npm install
```

### Deploy and install

```bash
forge deploy
forge install   # select Jira and Confluence products when prompted
```

### Get the webhook URL

```bash
forge webtrigger
```

Copy the URL shown for the `autodoc-webhook` trigger. This is your `AUTODOC_WEBHOOK_URL`.

### Set the webhook secret

The app reads the HMAC secret from the `WEBHOOK_SECRET` environment variable. Set it using Forge's environment variable store:

```bash
forge variables set --environment production WEBHOOK_SECRET <your-secret>
```

Use a strong random value (e.g. `openssl rand -hex 32`). The same value must be set as the `AUTODOC_WEBHOOK_SECRET` GitHub secret in every target repository.

## GitHub secrets required

Set these in each target repository that uses the AutoDoc workflow:

| Secret | Description |
|--------|-------------|
| `AUTODOC_WEBHOOK_URL` | Webtrigger URL from `forge webtrigger` |
| `AUTODOC_WEBHOOK_SECRET` | Same value set with `forge variables set` |

The workflow also requires `AUTODOC_API_URL` and `AUTODOC_API_KEY` for the backend server — see the [root README](../../README.md) for the full secrets table.

## Webhook payload format

The CI pipeline sends a JSON body (compact, keys sorted) with an HMAC-SHA256 signature in the `X-AutoDoc-Signature` header:

```
X-AutoDoc-Signature: sha256=<hex-digest>
Content-Type: application/json
```

Body:

```json
{
  "confluenceSpaceKey": "DOCS",
  "jiraKey": "PROJ-123",
  "prNumber": "42",
  "prTitle": "Add login flow",
  "repoDoc": "# Repository Overview\n...",
  "repoFullName": "owner/my-repo",
  "repoName": "my-repo",
  "units": [
    {
      "kind": "api",
      "markdown": "# Auth Module\n...",
      "slug": "auth",
      "title": "Auth Module"
    }
  ]
}
```

The `webhookSecret` field is **not** sent in the body. Authentication is solely via the `X-AutoDoc-Signature` header (HMAC-SHA256 over the raw request body).

Required fields: `jiraKey`, `confluenceSpaceKey`, `units`.

## Local development

Run a tunnel to test against a locally running instance:

```bash
forge tunnel
```

## Redeployment

After any code change:

```bash
forge deploy
```
