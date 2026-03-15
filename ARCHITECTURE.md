# AutoDoc Architecture

## 1. System Context (C4 Level 1)

```mermaid
graph TD
    Dev[Developer]
    Rev[Reviewer]

    subgraph AutoDoc System
        Backend[autodoc-backend\nPython CLI / REST API]
        Forge[jira-confluence-app\nAtlassian Forge]
        CI[GitHub Actions Workflow]
    end

    OR[OpenRouter API\nexternal LLM gateway]
    GH[GitHub\nsource + CI host]
    JC[Jira Cloud]
    CC[Confluence Cloud]

    Dev -->|pushes code / opens PR| GH
    GH -->|triggers workflow| CI
    CI -->|runs autodoc CLI| Backend
    Backend -->|LLM requests| OR
    CI -->|webhook POST| Forge
    Forge -->|creates/updates pages| CC
    Forge -->|adds remote links| JC
    Rev -->|reviews docs in| JC
    Rev -->|reads pages in| CC
```

---

## 2. Container Diagram (C4 Level 2)

```mermaid
graph TD
    CI[GitHub Actions Workflow\nCI runner - YAML]
    Backend[autodoc-backend\nPython CLI + REST API]
    Forge[jira-confluence-app\nAtlassian Forge - Node.js]
    OR[OpenRouter API]
    JiraAPI[Jira Cloud API]
    ConfAPI[Confluence Cloud API]

    CI -->|pip install + autodoc generate| Backend
    CI -->|webhook POST /webhook| Forge
    Backend -->|POST completions| OR
    Forge -->|REST API calls| ConfAPI
    Forge -->|REST API calls| JiraAPI
```

---

## 3. Backend Component Diagram (C4 Level 3)

```mermaid
graph TD
    CLI[cli.py\nCLI entry point]
    SRV[server.py\nFastAPI REST server]
    CTX[context.py\nContext assembly]
    IDX[repo_index.py\nImport graph builder]
    FLT[filters.py\nFile filters]
    GIT[git_utils.py\nGit diff helpers]
    PRM[prompts.py\nPrompt templates v4]
    LLM[llm.py\nOpenRouter client]
    RTR[router.py\nModel routing logic]
    CACHE[cache.py\nContent-hash cache]
    LANG[lang_extractors.py\nLanguage import parsers]

    CLI --> CTX
    SRV --> CTX
    CTX --> IDX
    CTX --> FLT
    CTX --> GIT
    CTX --> PRM
    PRM --> LLM
    RTR --> LLM
    CACHE --> LLM
    LANG --> IDX
```

---

## 4. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub
    participant CI as GitHub Actions
    participant Backend as autodoc-backend
    participant LLM as OpenRouter LLM
    participant Forge as Atlassian Forge
    participant KVS as Forge KV Store
    participant Jira as Jira Cloud
    participant Conf as Confluence Cloud

    Dev->>GH: Merge PR
    GH->>CI: Trigger workflow
    CI->>Backend: autodoc generate (CLI)
    Backend->>LLM: POST /chat/completions (per unit)
    LLM-->>Backend: Markdown documentation
    Backend-->>CI: Write .autodoc/units/*.md + repo.md
    CI->>Forge: POST /webhook {repo, docs}
    Forge->>KVS: Store pending docs
    Forge->>Jira: Create review issue
    Jira-->>Dev: Notification
    Dev->>Jira: Approve docs in review UI
    Jira->>Forge: Approval trigger
    Forge->>Conf: Create/update documentation page
    Forge->>Jira: Add remote link to Confluence page
```

---

## 5. Documentation Generation Flow (Single Unit)

```mermaid
flowchart TD
    A[Load .autodoc/config.yml] --> B[Filter tracked files]
    B --> C[Group files into units]
    C --> D[Build import graph]
    D --> E[Determine impacted units]

    E --> F{For each unit}

    F --> G[Check cache\ncontent hash]
    G -->|Hit| Z[Skip — reuse cached doc]
    G -->|Miss| H[Route model\nrouter.py]

    H --> I[Build context bundle\ncontext.py]
    I --> J[Build prompt\nprompts.py v4]
    J --> K[Call LLM\nllm.py via OpenRouter]
    K --> L[Save to cache]
    L --> M[Write .autodoc/units/slug.md]

    M --> N[All units done?]
    N -->|No| F
    N -->|Yes| O[Generate repo overview\nbuild_repo_prompt]
    O --> P[POST webhook to Forge]
```
