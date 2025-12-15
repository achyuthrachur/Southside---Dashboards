from pathlib import Path
import sys

# Ensure local package imports work when running as a Vercel function
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import server as app  # Dash exposes its Flask server as `server`
