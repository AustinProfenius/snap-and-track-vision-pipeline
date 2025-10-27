"""
Pytest configuration for pipeline convergence tests.
"""
import sys
from pathlib import Path

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

# Add nutritionverse-tests to path
nutritionverse_path = repo_root / "nutritionverse-tests"
if str(nutritionverse_path) not in sys.path:
    sys.path.insert(0, str(nutritionverse_path))
