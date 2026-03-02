from __future__ import annotations


DEFAULT_MODEL_NAME = "stub-model"


def generate_documentation(prompt_text: str, source_file: str) -> str:
    """
    Placeholder generation function.
    Replace this with a real API call later.
    """
    return f"""# Documentation for `{source_file}`

> Auto-generated placeholder output.

## Overview
This documentation was generated from the current file contents and repository context.

## Notes
- This is currently using a stub generator.
- The orchestration pipeline is working if this file was created.
- Next step: replace the stub with a real LLM API call.

## Prompt Size
{len(prompt_text)} characters
"""


def generate_repo_documentation(prompt_text: str) -> str:
    """
    Placeholder generation function for repository-level documentation.
    Replace this with a real API call later.
    """
    return f"""# Repository Documentation

> Auto-generated repository-level placeholder output.

## Overview
This documentation was generated from per-file documentation and repository context.

## Notes
- This is currently using a stub generator.
- The orchestration pipeline is working if this file was created.
- Next step: replace the stub with a real LLM API call.

## Prompt Size
{len(prompt_text)} characters
"""