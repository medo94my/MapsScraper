#!/usr/bin/env python3
"""Backward-compatible module exports for the original task.main interface."""

from task.base import BaseScraper
from task.checkpoint import Checkpoint
from task.error import MissingPromptFile, ScraperError, WrongPromptFile
from task.models import Listing, Prompt
from task.progress import ProgressReporter
from task.scraper import MapsScraper

__all__ = [
    "BaseScraper",
    "Checkpoint",
    "ProgressReporter",
    "ScraperError",
    "MissingPromptFile",
    "WrongPromptFile",
    "Prompt",
    "Listing",
    "MapsScraper",
]
