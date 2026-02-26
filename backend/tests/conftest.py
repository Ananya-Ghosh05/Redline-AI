"""Pytest configuration for backend tests.

Adds the app directory to sys.path so that test imports like
`from app.agents.xxx` resolve correctly.
"""
import sys
from pathlib import Path

# Add the backend directory to Python path so 'app' package is importable
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
