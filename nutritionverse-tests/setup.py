"""
Setup script for NutritionVerse API Test Harness.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="nutritionverse-tests",
    version="0.1.0",
    description="API test harness for evaluating vision-language models on nutrition estimation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/nutritionverse-tests",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "openai>=1.0.0",
        "anthropic>=0.18.0",
        "google-generativeai>=0.3.0",
        "aiohttp>=3.9.0",
        "pyarrow>=14.0.0",
        "streamlit>=1.30.0",
        "plotly>=5.18.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "nvtest=src.core.runner:main",
            "nvloader=src.core.loader:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
