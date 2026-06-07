"""
Manual script to run daily data update.
This fetches data from 2025-01-01 to yesterday (or last Friday).
"""

from data_collection import run_collection
import logging

if __name__ == "__main__":
    logging.info("Starting manual data update...")
    run_collection(use_dynamic_dates=True)
    logging.info("Manual update complete!")
