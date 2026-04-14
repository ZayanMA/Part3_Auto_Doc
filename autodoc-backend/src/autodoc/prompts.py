PROMPT_VERSION = "v4"

UNIT_NAMING_PROMPT = """\
You are naming software documentation units for a Confluence wiki.
For each unit, provide a concise descriptive name (3-7 words) that describes what the code DOES.
Good: "Authentication & JWT Token Handlers", "Database ORM Models & Schemas"
Bad: "Auth", "Models", "Src", "Utils"

Also set "coherent" to true if the files in the unit seem semantically related, false if they appear to be an unrelated mix.

Units to name — respond with ONLY valid JSON in this format:
{
  "slug1": {"name": "Descriptive Name Here", "coherent": true},
  "slug2": {"name": "Another Name", "coherent": false}
}

Units:
{unit_xml_list}\
"""


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

    repo_manifest_text = (getattr(bundle, "repo_manifest", "") or "").strip()
    manifest_section = f"\n## 0. Repository Context\n{repo_manifest_text}\n" if repo_manifest_text else ""

    return f"""Before writing, silently reason through:
1. What is the primary responsibility of this unit?
2. What are the 2–3 most important public interfaces?
3. What does this unit NOT do (boundaries)?
Then write the documentation. Do not include your reasoning in the output.
{manifest_section}
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
- Start with a single H1 title line only if needed; all required content sections must be H2 headings exactly as listed above.
- In `## Overview`, describe ONLY this unit's specific scope, role, and boundaries within the system. Do NOT write a repository or project-level summary — that belongs in REPOSITORY.md.
- Put a blank line after every heading and before every list or code block.
- Keep paragraphs short; prefer bullets over dense prose.
- In `## Key APIs & Interfaces`, list each important API/interface as its own bullet with a short explanation and file citation.
- In `## Responsibilities`, `## Dependencies`, and `## Configuration & Data`, prefer compact bullet lists.
- Use fenced code blocks only when they add real value; do not emit huge code dumps.
- Use Markdown tables only when summarising structured config or interfaces more clearly than bullets.
- Only mention functions, classes, parameters, or behaviours that appear verbatim in the code above.
- For each API or interface listed, cite the file it comes from (e.g. `cache.py`).
- If a section has nothing to say, write "N/A" rather than omitting the heading.
- Do not add sections beyond those listed above.
- Do not repeat the unit name or file list in the output body.
- DO NOT invent APIs or behaviour not supported by the code/diffs.
- Prefer updating the existing doc rather than rewriting from scratch.
""".strip()


def build_unit_patch_prompt(bundle) -> str:
    """Patch mode prompt — context-aware, scored against changed symbols (claw-code pattern)."""
    diffs = getattr(bundle, "diffs", []) or []
    diffs_text = "\n".join(f"\n--- DIFF: {p} ---\n{d}\n" for p, d in diffs) or "(none)"

    # Changed symbols: the "query tokens" extracted from the diff
    symbols = getattr(bundle, "changed_symbols", []) or []
    symbol_text = ", ".join(f"`{s}`" for s in symbols) if symbols else "(could not extract)"

    # Scored doc sections: only the most-relevant sections, not the full dump
    scored_sections = getattr(bundle, "scored_doc_sections", []) or []
    if scored_sections:
        existing_doc_text = "\n\n".join(f"## {h}\n{b}" for h, b in scored_sections)
    else:
        existing_doc_text = (getattr(bundle, "existing_unit_doc", "") or "").strip() or "(none yet)"

    # Changed files at HEAD: full content for the files that actually changed
    changed_paths = {p for p, _ in diffs}
    changed_file_contents = [
        (p, c) for p, c in (getattr(bundle, "file_contents", []) or [])
        if p in changed_paths
    ]
    files_text = "\n".join(f"\n--- FILE (HEAD): {p} ---\n{c}\n" for p, c in changed_file_contents) or "(none)"

    # Cross-unit impact: neighbour summaries
    neighbour_summaries = getattr(bundle, "neighbour_summaries", []) or []
    neighbours_text = "\n".join(
        f"**{name}**: {snippet}" for name, snippet in neighbour_summaries
    ) or "(none)"

    repo_manifest_text = (getattr(bundle, "repo_manifest", "") or "").strip()
    manifest_section = f"\n## Repository Context\n{repo_manifest_text}\n" if repo_manifest_text else ""

    return f"""You are updating technical documentation after a code change.
{manifest_section}
## Unit: {bundle.unit_name} ({bundle.unit_kind})

## Changed Symbols
{symbol_text}

## What Changed (diffs)
{diffs_text}

## Changed Files at HEAD (full content)
{files_text}

## Related Units (cross-unit impact)
{neighbours_text}

## Relevant Documentation Sections (scored against changed symbols)
{existing_doc_text}

## Instructions
- Return the COMPLETE updated Markdown document with ALL required sections:
  ## Overview / ## Responsibilities / ## Key APIs & Interfaces / ## Configuration & Data / ## Dependencies / ## Usage Notes
- Update ONLY sections directly affected by the diff above.
- Copy all unaffected sections verbatim from existing documentation.
- Preserve clean Markdown structure with blank lines between headings, paragraphs, lists, and code blocks.
- Keep sections concise and scannable; prefer bullets to long paragraphs.
- In `## Key APIs & Interfaces`, present each changed API or interface as a separate bullet with a short explanation and file citation.
- Do NOT invent APIs or behaviour not shown in the diff or file content.
- Output Markdown only.
""".strip()


def build_repo_prompt(
    repo_name: str,
    readme_content: str,
    file_docs: list[tuple[str, str]],
    unit_index: list[tuple[str, str]] | None = None,
) -> str:
    unit_sections: list[str] = []
    for name, doc in file_docs:
        unit_sections.append(f"\n--- UNIT DOC: {name} ---\n{doc}\n")

    units_text = "\n".join(unit_sections)

    # Build a reference list so the LLM knows exact link targets
    if unit_index:
        link_lines = "\n".join(
            f"- [{name}](units/{slug}.md)" for name, slug in unit_index
        )
        unit_links_section = f"\nAvailable unit documentation files (use these exact paths for markdown links):\n{link_lines}\n"
    else:
        unit_links_section = ""

    return f"""Write a repository overview for "{repo_name}" with these required sections:

## What This Does
(2–3 sentences: purpose and problem solved)

## Architecture Overview
(How the main components fit together — link each component using its markdown link from the list below)

## Key Entry Points
(How to start using or running this system — CLI commands, API endpoints, scripts)

## Component Map
(One line per component — use markdown links: [Component Name](units/slug.md))

## Getting Started
(Minimal steps for a new contributor to run locally)

Do not repeat unit documentation verbatim. Synthesise and connect.
Keep the Markdown visually clean:
- short paragraphs
- bullets for component maps and entry points
- blank lines between headings and lists
- no giant walls of text
- output Markdown only
{unit_links_section}
Existing repository README (if any):
{readme_content}

Per-unit documentation inputs:
{units_text}
""".strip()
