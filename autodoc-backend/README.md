# autodoc-backend

Python CLI and FastAPI server that analyzes a git repository, groups source files into logical documentation units, calls an LLM via OpenRouter, and returns structured Markdown documentation.

## Requirements

- Python 3.13+
- `pip` or `uv`
- An [OpenRouter](https://openrouter.ai) API key

## Installation

```bash
cd autodoc-backend
pip install -e .
```

This installs two entry points:

| Command | Description |
|---------|-------------|
| `autodoc` | CLI for local generation |
| `autodoc-server` | FastAPI server for CI-driven generation |

## Configuration

### Environment variables (`.env`)

Create a `.env` file in the working directory (or export the variables directly):

```dotenv
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-sonnet-4-5   # optional override
```

### Per-repo config (`.autodoc/config.toml`)

Place this file in the root of the *target* repository to tune generation behaviour:

```toml
fast_model          = "stepfun/step-3.5-flash"       # model for small/simple units
smart_model         = "anthropic/claude-sonnet-4-5"  # model for large/complex units
token_budget        = 12000                          # context window budget (tokens)
patch_mode_enabled  = true                           # incremental patch on small diffs
patch_diff_threshold = 50                            # lines-changed threshold for patch
min_files_per_unit  = 3                              # merge groups smaller than this
max_files_fulltext  = 8                              # max files sent as full text
max_file_chars      = 6000                           # max characters per file
cache_max_age_days  = 30                             # prune cache entries older than this

[unit_overrides]
# Force specific files into a named unit:
# "auth" = ["src/auth/login.py", "src/auth/tokens.py"]
```

## CLI usage

Generate docs for files changed between two git refs:

```bash
autodoc generate --repo . --base HEAD~1 --head HEAD
```

Regenerate documentation for all relevant files:

```bash
autodoc generate --repo . --all
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--repo PATH` | `.` | Path to the target repository |
| `--base REF` | `HEAD~1` | Base git ref (older) |
| `--head REF` | `HEAD` | Head git ref (newer) |
| `--all` | off | Regenerate all units, not just changed ones |
| `--model MODEL` | config | Override model for all units |
| `--fast-model MODEL` | config | Override fast model only |
| `--smart-model MODEL` | config | Override smart model only |
| `--config PATH` | `.autodoc/config.toml` | Path to config TOML |
| `--debug` | off | Print prompt diagnostics (SHA, char count) |
| `--dump-prompts` | off | Write full prompts to `.autodoc/prompts/` |
| `--patch / --no-patch` | on | Enable/disable incremental patch mode |
| `--limit N` | none | Process at most N units |
| `--costs / --no-costs` | on | Show token/cost column in summary table |
| `--prune-cache / --no-prune-cache` | on | Prune stale cache entries before run |

## API server

### Starting the server

```bash
AUTODOC_API_KEY=<your-key> OPENROUTER_API_KEY=<your-key> autodoc-server
```

The server listens on `http://0.0.0.0:8080`.

### Authentication

Set `AUTODOC_API_KEY` in the server's environment. All API calls must include:

```
Authorization: Bearer <AUTODOC_API_KEY>
```

If `AUTODOC_API_KEY` is unset, authentication is disabled (development mode).

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `POST` | `/generate` | Submit a generation job (async) |
| `GET` | `/jobs/{job_id}` | Poll job status and retrieve results |

#### `POST /generate` — request body

```json
{
  "repo_full_name": "owner/repo",
  "github_token":   "ghp_...",
  "base":           "abc1234",
  "head":           "def5678",
  "all_files":      false,
  "model":          null,
  "config_path":    null
}
```

The server clones the repository using the provided `github_token` and runs generation in the background. Returns immediately with a job ID:

```json
{
  "job_id":   "550e8400-e29b-41d4-a716-446655440000",
  "status":   "pending",
  "poll_url": "/jobs/550e8400-e29b-41d4-a716-446655440000"
}
```

#### `GET /jobs/{job_id}` — response

```json
{
  "job_id":      "550e8400-...",
  "status":      "done",
  "created_at":  "2026-03-16T10:00:00+00:00",
  "finished_at": "2026-03-16T10:02:30+00:00",
  "units": [
    {
      "slug":     "auth",
      "name":     "Auth",
      "kind":     "api",
      "markdown": "# Auth\n...",
      "status":   "generated"
    }
  ],
  "repo_doc": "# Repository Overview\n...",
  "error":    null
}
```

Possible `status` values: `pending`, `running`, `done`, `failed`.

## Output artifacts

Generated files are written into the target repository under `.autodoc/`:

| Path | Description |
|------|-------------|
| `.autodoc/units/{slug}.md` | Per-unit Markdown documentation |
| `.autodoc/REPOSITORY.md` | High-level repository overview |
| `.autodoc/index.json` | Repo structure index used for incremental runs |
| `.autodoc/cache/` | Content-addressed cache of LLM responses |

## Running tests

```bash
pytest tests/
```
