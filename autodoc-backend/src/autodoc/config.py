from __future__ import annotations
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            tomllib = None  # type: ignore

AUTODOC_DIR = ".autodoc"


@dataclass
class AutodocConfig:
    min_files_per_unit: int = 3
    max_files_fulltext: int = 8
    max_file_chars: int = 6000
    token_budget: int = 12000

    fast_model: str = "stepfun/step-3.5-flash"
    smart_model: str = "anthropic/claude-sonnet-4-5"

    patch_mode_enabled: bool = True
    patch_diff_threshold: int = 50

    cache_max_age_days: int = 30

    unit_overrides: dict[str, list[str]] = field(default_factory=dict)


def load_config(repo: Path, config_path: Path | None = None) -> AutodocConfig:
    if config_path is None:
        config_path = repo / AUTODOC_DIR / "config.toml"

    cfg = AutodocConfig()

    if tomllib is None or not config_path.exists():
        return cfg

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return cfg

    for key in ("min_files_per_unit", "max_files_fulltext", "max_file_chars", "token_budget",
                "fast_model", "smart_model", "patch_mode_enabled", "patch_diff_threshold",
                "cache_max_age_days"):
        if key in data:
            setattr(cfg, key, data[key])

    if "unit_overrides" in data and isinstance(data["unit_overrides"], dict):
        cfg.unit_overrides = data["unit_overrides"]

    return cfg
