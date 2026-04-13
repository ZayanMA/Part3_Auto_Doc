from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, List


def _dedup(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


def _extract_python(content: str) -> List[str]:
    """Regex fallback for Python (AST path kept in repo_index.py)."""
    imports: List[str] = []
    for m in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
        imports.append(m.group(1))
    for m in re.finditer(r"^from\s+(\.+[\w.]*|[\w.]+)\s+import", content, re.MULTILINE):
        imports.append(m.group(1))
    return _dedup(imports)


def _extract_js(content: str) -> List[str]:
    """JS/TS: import … from '…' and require('…')."""
    imports: List[str] = []
    # ESM: import ... from 'pkg'
    for m in re.finditer(r"""import\s+.*?from\s+['"]([^'"]+)['"]""", content, re.DOTALL):
        imports.append(m.group(1))
    # dynamic import / require
    for m in re.finditer(r"""(?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)""", content):
        imports.append(m.group(1))
    return _dedup(imports)


def _extract_go(content: str) -> List[str]:
    """Go: single-line and block imports."""
    imports: List[str] = []
    # single-line: import "pkg"
    for m in re.finditer(r'^import\s+"([^"]+)"', content, re.MULTILINE):
        imports.append(m.group(1))
    # block: import ( "pkg1" "pkg2" )
    for block in re.finditer(r"import\s*\(([^)]+)\)", content, re.DOTALL):
        for m in re.finditer(r'"([^"]+)"', block.group(1)):
            imports.append(m.group(1))
    return _dedup(imports)


def _extract_java(content: str) -> List[str]:
    """Java: import [static] pkg.Class;"""
    imports: List[str] = []
    for m in re.finditer(r"^import\s+(?:static\s+)?([\w.]+)\s*;", content, re.MULTILINE):
        imports.append(m.group(1))
    return _dedup(imports)


def _extract_rust(content: str) -> List[str]:
    """Rust: use crate::…; — captures the top-level path."""
    imports: List[str] = []
    for m in re.finditer(r"^use\s+([\w:]+)", content, re.MULTILINE):
        imports.append(m.group(1))
    return _dedup(imports)


def _extract_ruby(content: str) -> List[str]:
    """Ruby: require / require_relative '…'"""
    imports: List[str] = []
    for m in re.finditer(r"""(?:require|require_relative)\s+['"]([^'"]+)['"]""", content):
        imports.append(m.group(1))
    return _dedup(imports)


def _extract_zig(content: str) -> List[str]:
    """Zig: @import("...") — captures both std lib and relative file imports."""
    imports: List[str] = []
    for m in re.finditer(r'@import\s*\(\s*"([^"]+)"\s*\)', content):
        imports.append(m.group(1))
    return _dedup(imports)


def _extract_generic(content: str) -> List[str]:
    return []


_EXTRACTORS: dict[str, Callable[[str], List[str]]] = {
    ".py": _extract_python,
    ".js": _extract_js,
    ".jsx": _extract_js,
    ".ts": _extract_js,
    ".tsx": _extract_js,
    ".mjs": _extract_js,
    ".cjs": _extract_js,
    ".go": _extract_go,
    ".java": _extract_java,
    ".rs": _extract_rust,
    ".rb": _extract_ruby,
    ".zig": _extract_zig,
}


def extract_imports_for_file(path: str, content: str) -> List[str]:
    """Dispatch to per-language extractor. Returns raw import strings."""
    ext = Path(path).suffix.lower()
    return _EXTRACTORS.get(ext, _extract_generic)(content)
