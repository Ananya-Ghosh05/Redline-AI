"""Pytest configuration for unit tests.

Adds the backend directory to sys.path so that imports like
`from app.agents.xxx` resolve correctly.
"""
import sys
from pathlib import Path

# Add the backend directory to Python path so 'app' package is importable
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
