PROMPT_VERSION = "v1"


def build_prompt(bundle) -> str:
    nearby_sections = []
    for path, content in zip(bundle.nearby_files, bundle.nearby_contents):
        nearby_sections.append(
            f"\n--- NEARBY FILE: {path} ---\n{content}\n"
        )

    nearby_text = "\n".join(nearby_sections)

    return f"""
You are generating technical documentation for a source code repository.

Task:
Generate concise but useful Markdown documentation for the changed file.

Rules:
- Do not invent APIs or behaviour not supported by the provided context.
- Focus on what this file does, its responsibilities, important functions/classes,
  inputs/outputs, dependencies, and any obvious risks or edge cases.
- If there is not enough information, say so rather than hallucinating.
- Return Markdown only.

Repository README:
{bundle.readme_content}

Changed file path:
{bundle.target_file}

Changed file diff:
{bundle.diff_text}

Changed file full content:
{bundle.target_content}

Supporting nearby files:
{nearby_text}
""".strip()


def build_repo_prompt(
    repo_name: str,
    readme_content: str,
    file_docs: list[tuple[str, str]],
) -> str:
    file_sections: list[str] = []
    for path, doc in file_docs:
        file_sections.append(f"\n--- DOCUMENTATION FOR FILE: {path} ---\n{doc}\n")

    files_text = "\n".join(file_sections)

    return f"""
You are generating high-level technical documentation for the source code repository "{repo_name}".

Task:
Produce a single, cohesive Markdown document that explains the repository at a repository-wide level.

Rules:
- Focus on the overall purpose of the repository and how its main parts fit together.
- Use the per-file documentation as input, but avoid repeating it verbatim; instead, synthesize and summarize.
- Highlight key modules, important responsibilities, and how a new contributor should navigate the codebase.
- If the information is incomplete, clearly state any limitations instead of hallucinating details.
- Return Markdown only.

Existing repository README (if any):
{readme_content}

Per-file documentation inputs:
{files_text}
""".strip()


def build_unit_prompt(bundle) -> str:
    files_list = "\n".join(f"- {p}" for p in bundle.files)

    diffs_text = ""
    if bundle.diffs:
        diffs_text = "\n".join(
            [f"\n--- DIFF: {p} ---\n{d}\n" for (p, d) in bundle.diffs]
        )

    contents_text = "\n".join(
        [f"\n--- FILE: {p} ---\n{c}\n" for (p, c) in bundle.file_contents]
    )

    return f"""
You are generating technical documentation for a source code repository.

Task:
Generate a single Markdown page documenting this *module/unit*.

Unit:
- Name: {bundle.unit_name}
- Root: {bundle.unit_root}
- Files in unit:
{files_list}

Rules:
- Write documentation for the unit as a whole (responsibilities, how it fits in, key flows).
- Do NOT create a section per file by default.
- Mention helper/tiny files only if they matter; avoid noise.
- Be explicit about inputs/outputs, side effects, and key dependencies.
- Do not invent APIs or behaviour not supported by the provided context.
- If information is missing, say so.

Repository README:
{bundle.readme_content}

Relevant diffs (optional):
{diffs_text}

Selected unit file contents:
{contents_text}
""".strip()