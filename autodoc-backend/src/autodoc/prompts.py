PROMPT_VERSION = "v3"


def build_unit_prompt(bundle) -> str:
    files_list = "\n".join(f"- {p}" for p in bundle.files)

    # Separate primary/changed from supporting files
    diffs = getattr(bundle, "diffs", []) or []
    changed_paths = {p for p, _ in diffs}

    main_files = [(p, c) for p, c in bundle.file_contents if p in changed_paths]
    supporting_files = [(p, c) for p, c in bundle.file_contents if p not in changed_paths]

    main_text = "\n".join(f"\n--- FILE: {p} ---\n{c}\n" for p, c in main_files) or "(none)"
    supporting_text = "\n".join(f"\n--- FILE: {p} ---\n{c}\n" for p, c in supporting_files) or "(none)"

    diffs_lines = []
    for p, d in diffs:
        label = "modified" if p in changed_paths else "added"
        diffs_lines.append(f"\n--- DIFF [{label}]: {p} ---\n{d}\n")
    diffs_text = "\n".join(diffs_lines) or "(no diffs — full generation run)"

    neighbour_summaries = getattr(bundle, "neighbour_summaries", []) or []
    neighbours_text = "\n".join(
        f"**{name}**: {snippet}" for name, snippet in neighbour_summaries
    ) or "(none)"

    existing_doc_text = (getattr(bundle, "existing_unit_doc", "") or "").strip() or "(none yet)"

    return f"""You are maintaining technical documentation for a codebase.

## 1. Unit Identity
- **Name**: {bundle.unit_name}
- **Root**: {bundle.unit_root}
- **Kind**: {bundle.unit_kind}
- **Files in unit**:
{files_list}

## 2. Main Files (primary + changed — full content)
{main_text}

## 3. Supporting Files (remaining selected — may be truncated)
{supporting_text}

## 4. What Changed (diffs)
{diffs_text}

## 5. Related Units (neighbour summaries)
{neighbours_text}

## 6. Existing Documentation (previous version)
{existing_doc_text}

## 7. Instructions
- Output Markdown only.
- DO NOT invent APIs or behaviour not supported by the code/diffs.
- Prefer updating the existing doc rather than rewriting from scratch.
- Structure: Overview, Responsibilities, Key APIs/Interfaces, Data/Config, Dependency notes, How it fits in.
- Do NOT add a section per file unless it truly helps. Summarize at unit level.
""".strip()


def build_unit_patch_prompt(bundle) -> str:
    """Shorter prompt for patch mode — focused on diff + existing doc."""
    diffs = getattr(bundle, "diffs", []) or []
    diffs_text = "\n".join(f"\n--- DIFF: {p} ---\n{d}\n" for p, d in diffs) or "(none)"
    existing_doc_text = (getattr(bundle, "existing_unit_doc", "") or "").strip() or "(none yet)"

    return f"""You are updating technical documentation after a small code change.

## Unit: {bundle.unit_name} ({bundle.unit_kind})

## What Changed (diffs)
{diffs_text}

## Existing Documentation
{existing_doc_text}

## Instructions
- Return the COMPLETE updated Markdown document.
- Make minimal changes — only update sections affected by the diffs.
- DO NOT invent APIs or behaviour not shown in the diffs.
- Output Markdown only.
""".strip()


def build_repo_prompt(
    repo_name: str,
    readme_content: str,
    file_docs: list[tuple[str, str]],
) -> str:
    unit_sections: list[str] = []
    for name, doc in file_docs:
        unit_sections.append(f"\n--- UNIT DOC: {name} ---\n{doc}\n")

    units_text = "\n".join(unit_sections)

    return f"""
You are generating high-level technical documentation for the source code repository "{repo_name}".

Task:
Produce a single, cohesive Markdown document that explains the repository at a repository-wide level.

Rules:
- Focus on the overall purpose of the repository and how its main parts fit together.
- Use the unit documentation as input, but avoid repeating it verbatim; instead, synthesize and summarize.
- Highlight key modules, important responsibilities, and how a new contributor should navigate the codebase.
- If the information is incomplete, clearly state any limitations instead of hallucinating details.
- Return Markdown only.

Existing repository README (if any):
{readme_content}

Per-unit documentation inputs:
{units_text}
""".strip()
