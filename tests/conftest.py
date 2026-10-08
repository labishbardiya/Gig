"""Tests must never inherit live credentials or operator demo settings."""
import os

os.environ['GIG_SKIP_PROJECT_ENV'] = '1'
