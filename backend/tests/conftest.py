"""Tests run fully offline: no catalog database, no BU API, no private calendar feeds.

The variables are blanked before any app module is imported. python-dotenv never overrides a variable that
is already set, so even a developer's real backend/.env cannot leak into a test run.
"""
import os

for key in ("BU_BASE", "BU_API_KEY", "BU_TOKEN", "DB_HOST", "BLACKBOARD_ICS_URL", "GRADESCOPE_ICS_URL"):
    os.environ[key] = ""
