"""
Configuration loader for unified alignment pipeline.

Loads all configs from YAML/JSON files and computes deterministic fingerprint
for drift detection.
"""
import yaml
import json
import hashlib
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict
from pathlib import Path


@dataclass
class PipelineConfig:
    """Unified configuration with version tracking."""
    thresholds: Dict[str, Any]
    neg_vocab: Dict[str, Any]
    variants: Dict[str, Any]
    conversions: Dict[str, Any]
    feature_flags: Dict[str, Any]
    energy_bands: Dict[str, Any]
    proxy_rules: Dict[str, Any]
    category_allowlist: Dict[str, Any]  # Phase 7.1: Form-aware category gates
    config_version: str
    config_fingerprint: str


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML file."""
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}


def _load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


def load_pipeline_config(root: str = "configs") -> PipelineConfig:
    """
    Load all pipeline configs from directory and compute version fingerprint.

    Args:
        root: Path to configs directory (default: "configs/")

    Returns:
        PipelineConfig with loaded configs and version tracking

    Raises:
        FileNotFoundError: If required config files missing
    """
    root_path = Path(root)

    # Define config file paths (some optional)
    config_files = {
        "thresholds": root_path / "class_thresholds.yml",
        "neg_vocab": root_path / "negative_vocabulary.yml",
        "feature_flags": root_path / "feature_flags.yml",
        "conversions": root_path / "cook_conversions.v2.json",
        "energy_bands": root_path / "energy_bands.json",
        "proxy_rules": root_path / "proxy_alignment_rules.json",
        "variants": root_path / "variants.yml",
        "category_allowlist": root_path / "category_allowlist.yml",  # Phase 7.1
    }

    # Load configs (use empty dict if file doesn't exist)
    data = {}
    for key, path in config_files.items():
        if path.exists():
            if path.suffix in ('.yml', '.yaml'):
                data[key] = _load_yaml(path)
            elif path.suffix == '.json':
                data[key] = _load_json(path)
            else:
                raise ValueError(f"Unknown config file type: {path}")
        else:
            # Optional configs default to empty dict
            if key in ('energy_bands', 'proxy_rules', 'variants', 'category_allowlist'):
                data[key] = {}
            else:
                # Required configs must exist
                raise FileNotFoundError(
                    f"Required config file not found: {path}\n"
                    f"Run config externalization step first."
                )

    # Compute deterministic config fingerprint
    # Sort keys to ensure stability across reordered YAML
    blob = json.dumps(data, sort_keys=True).encode("utf-8")
    fingerprint = hashlib.sha256(blob).hexdigest()[:12]
    config_version = f"configs@{fingerprint}"

    return PipelineConfig(
        thresholds=data["thresholds"],
        neg_vocab=data["neg_vocab"],
        variants=data["variants"],
        conversions=data["conversions"],
        feature_flags=data["feature_flags"],
        energy_bands=data["energy_bands"],
        proxy_rules=data["proxy_rules"],
        category_allowlist=data["category_allowlist"],  # Phase 7.1
        config_version=config_version,
        config_fingerprint=fingerprint,
    )


def get_code_git_sha() -> str:
    """
    Get current Git SHA for code version tracking.

    Returns:
        12-character Git SHA or "unknown" if Git not available

    Falls back to CODE_GIT_SHA environment variable.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return sha[:12]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Git not available or not in repo - try env var
        return os.getenv("CODE_GIT_SHA", "unknown")
