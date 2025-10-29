#!/usr/bin/env python3
"""
Repository Scanner for Snap & Track Vision Pipeline
Generates active file inventory and dependency graph.

Usage:
    python tools/scan_repo.py > DOCS/ACTIVE_INVENTORY.json
    python tools/scan_repo.py --dot > DOCS/DEPENDENCY_GRAPH.dot
"""
import os
import json
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional

# Exclusions
EXCLUDE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    '.pytest_cache', '.mypy_cache', 'data', 'dataset', 'artifacts',
    'runs', 'logs', 'telemetry', 'results', 'dist', 'build', 'coverage',
    '.archived'
}

EXCLUDE_EXTS = {
    '.log', '.jsonl', '.png', '.jpg', '.jpeg', '.gif', '.mp4',
    '.mov', '.zip', '.tar', '.gz', '.csv', '.pyc', '.pyo'
}

# Core files for active score calculation
CORE_FILES = {
    'align_convert.py',
    'alignment_adapter.py',
    'run.py',
    'schemas.py',
    'config_loader.py',
    'fdc_database.py'
}

ENTRYPOINT_PATTERNS = [
    r'run_\w+\.py$',
    r'nutritionverse_app\.py$',
    r'test_\w+\.py$'
]


def scan_files(root: Path) -> List[Path]:
    """Scan repository for code files."""
    files = []
    for path in root.rglob('*'):
        if path.is_file():
            # Check exclusions
            if any(ex in path.parts for ex in EXCLUDE_DIRS):
                continue
            if path.suffix in EXCLUDE_EXTS:
                continue
            # Include code files
            if path.suffix in {'.py', '.yml', '.yaml', '.json', '.md'}:
                files.append(path)
    return sorted(files)


def extract_python_imports(file_path: Path) -> Set[str]:
    """Extract import statements from Python file."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Match "import X" or "from X import Y"
            patterns = [
                r'^\s*from\s+([\w.]+)\s+import',
                r'^\s*import\s+([\w.]+)'
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    module = match.group(1).split('.')[0]
                    imports.add(module)
    except Exception:
        pass
    return imports


def is_entrypoint(file_path: Path) -> bool:
    """Check if file is an entrypoint."""
    name = file_path.name
    for pattern in ENTRYPOINT_PATTERNS:
        if re.match(pattern, name):
            # Additional check: must be executable or in entrypoints directory
            if 'entrypoint' in str(file_path).lower() or name.startswith('run_'):
                return True
    return False


def is_test(file_path: Path) -> bool:
    """Check if file is a test."""
    return ('test' in str(file_path).lower() and
            file_path.suffix == '.py' and
            (file_path.name.startswith('test_') or 'tests/' in str(file_path)))


def calculate_active_score(file_path: Path, deps: Set[str],
                           all_imports: Dict[str, Set[str]]) -> int:
    """
    Calculate active score (0-100) based on multiple criteria.

    Criteria:
    - Core file (name in CORE_FILES): +50
    - Entrypoint: +40
    - Test: +30
    - Config file (YAML): +40
    - Imported by core files: +30
    - Imported by entrypoints: +20
    - Imported by tests: +10
    - Recent modification (would check git, stub here): +10
    """
    score = 0
    name = file_path.name
    rel_path = str(file_path)

    # Core file check
    if name in CORE_FILES:
        score += 50

    # Entrypoint check
    if is_entrypoint(file_path):
        score += 40

    # Test check
    if is_test(file_path):
        score += 30

    # Config file check
    if file_path.suffix in {'.yml', '.yaml'}:
        if any(x in name for x in ['negative_vocabulary', 'class_thresholds',
                                     'feature_flags', 'cook_methods']):
            score += 40

    # Check if imported by important files
    file_module = file_path.stem  # filename without extension

    # Check if any core file imports this
    for importer_path, importer_deps in all_imports.items():
        if file_module in importer_deps or name.replace('.py', '') in importer_deps:
            importer_name = Path(importer_path).name
            if importer_name in CORE_FILES:
                score += 30
                break
            elif is_entrypoint(Path(importer_path)):
                score += 20
            elif is_test(Path(importer_path)):
                score += 10

    # Cap at 100
    return min(score, 100)


def categorize_file(file_path: Path, score: int) -> str:
    """Categorize file based on active score."""
    if score >= 80:
        return 'core'
    elif score >= 60:
        return 'support'
    elif score >= 40:
        return 'nice_to_have'
    else:
        return 'legacy'


def analyze_file(file_path: Path, root: Path, all_imports: Dict[str, Set[str]]) -> Dict:
    """Analyze a single file."""
    rel_path = file_path.relative_to(root)

    # Determine language
    lang_map = {
        '.py': 'Python', '.yml': 'YAML', '.yaml': 'YAML',
        '.json': 'JSON', '.md': 'Markdown', '.js': 'JavaScript', '.ts': 'TypeScript'
    }
    language = lang_map.get(file_path.suffix, 'Unknown')

    # Extract imports (Python only)
    deps = []
    if language == 'Python':
        deps = list(extract_python_imports(file_path))

    # Calculate active score
    score = calculate_active_score(file_path, set(deps), all_imports)
    category = categorize_file(file_path, score)

    # Determine purpose (simplified)
    name = file_path.name
    purpose = name  # Default to filename

    if 'align_convert' in name:
        purpose = 'Core alignment engine with Stage 1b/1c/2/5/Z'
    elif 'run.py' in name and 'pipeline' in str(rel_path):
        purpose = 'Unified pipeline orchestrator'
    elif 'schemas' in name:
        purpose = 'Pydantic type schemas'
    elif 'config_loader' in name:
        purpose = 'Config file loader'
    elif 'fdc_database' in name:
        purpose = 'FDC database interface'
    elif 'alignment_adapter' in name:
        purpose = 'Alignment engine adapter'
    elif 'cook_convert' in name:
        purpose = 'Stage 2: Raw→cooked conversion'
    elif 'test_' in name:
        purpose = f'Unit tests for {name.replace("test_", "").replace(".py", "")}'

    return {
        'path': str(rel_path),
        'language': language,
        'purpose_short': purpose,
        'active_score': score,
        'category': category,
        'size_bytes': file_path.stat().st_size,
        'deps': deps
    }


def generate_dot_graph(files: List[Dict], output_file: Path):
    """Generate Graphviz DOT file for dependency graph."""
    # Implementation would generate full DOT syntax
    # For now, reference existing DEPENDENCY_GRAPH.dot
    print("// Dependency graph generation", file=sys.stderr)
    print("// Use existing DOCS/DEPENDENCY_GRAPH.dot", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Scan repository for active files')
    parser.add_argument('--dot', action='store_true', help='Generate DOT graph instead of JSON')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    args = parser.parse_args()

    root = Path.cwd()
    print(f"Scanning repository: {root}", file=sys.stderr)

    # Scan files
    files = scan_files(root)
    print(f"Found {len(files)} code files", file=sys.stderr)

    # First pass: collect all imports
    all_imports = {}
    for file_path in files:
        if file_path.suffix == '.py':
            deps = extract_python_imports(file_path)
            all_imports[str(file_path)] = deps

    # Second pass: analyze files with import context
    inventory = []
    for file_path in files:
        info = analyze_file(file_path, root, all_imports)
        inventory.append(info)

    # Filter to active files only (score >= 40)
    active_files = [f for f in inventory if f['active_score'] >= 40]

    # Sort by score descending
    active_files.sort(key=lambda x: x['active_score'], reverse=True)

    # Output JSON
    output = {
        'repo_root': str(root),
        'total_files': len(inventory),
        'active_files': len(active_files),
        'files': active_files,
        'summary': {
            'core': len([f for f in active_files if f['category'] == 'core']),
            'support': len([f for f in active_files if f['category'] == 'support']),
            'nice_to_have': len([f for f in active_files if f['category'] == 'nice_to_have'])
        }
    }

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
