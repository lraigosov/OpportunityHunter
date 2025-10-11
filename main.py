#!/usr/bin/env python3
"""
Entry point for the OpportunityHunter platform.
"""
from pathlib import Path
import sys

# Add src to path
sys.path.append(str((Path(__file__).parent / "src").resolve()))

from src.licitaciones.cli import main

if __name__ == "__main__":
    main()