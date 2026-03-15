PROMPT_VERSION = "v4"


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

    return f"""Before writing, silently reason through:
1. What is the primary responsibility of this unit?
2. What are the 2–3 most important public interfaces?
3. What does this unit NOT do (boundaries)?
Then write the documentation. Do not include your reasoning in the output.

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
- Use ONLY the following required sections (H2 headings):
  ## Overview
  ## Responsibilities
  ## Key APIs & Interfaces
  ## Configuration & Data
  ## Dependencies
  ## Usage Notes
- Only mention functions, classes, parameters, or behaviours that appear verbatim in the code above.
- For each API or interface listed, cite the file it comes from (e.g. `cache.py`).
- If a section has nothing to say, write "N/A" rather than omitting the heading.
- Do not add sections beyond those listed above.
- Prefer bullet points within sections over dense paragraphs.
- Do not repeat the unit name or file list in the output body.
- DO NOT invent APIs or behaviour not supported by the code/diffs.
- Prefer updating the existing doc rather than rewriting from scratch.
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
- Return the COMPLETE updated Markdown document with ALL sections intact.
- Only change the content of sections that are DIRECTLY affected by the diff above.
- Copy all other sections from the existing documentation unchanged, word for word.
- Do NOT remove, rename, or reorder any existing H2 sections.
- Do NOT invent APIs or behaviour not shown in the diff.
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

    return f"""Write a repository overview for "{repo_name}" with these required sections:

## What This Does
(2–3 sentences: purpose and problem solved)

## Architecture Overview
(How the main components fit together — reference component names from the unit docs)

## Key Entry Points
(How to start using or running this system — CLI commands, API endpoints, scripts)

## Component Map
(Brief one-line description of each major component)

## Getting Started
(Minimal steps for a new contributor to run locally)

Do not repeat unit documentation verbatim. Synthesise and connect.

Existing repository README (if any):
{readme_content}

Per-unit documentation inputs:
{units_text}
""".strip()
