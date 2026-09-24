"""
========================================================================
USER SETTINGS - Edit the values below to configure your simulation
After editing, save this file and run the simulation script (OOS_GUI_main.py)
========================================================================
"""

import os

# ------------------------------------------------------------------------
# REQUIRED: Project Location
# ------------------------------------------------------------------------
# Full path to your project folder (where this file is located)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------------
# SIMULATION SETTINGS
# ------------------------------------------------------------------------

# What day of the week does your simulation start on?
# Options: "Monday", "Tuesday", "Wednesday", "Thursday", 
#          "Friday", "Saturday", "Sunday"
START_DAY_OF_WEEK = "Monday"

# Is this a leap year? (True/False) - affects whether Feb has 29 days
IS_LEAP_YEAR = False

# Simulation start date (month and day, no year needed)
START_MONTH = 1      # 1-12
START_DAY = 1        # 1-31

# Simulation end date (month and day, no year needed)
END_MONTH = 12        # 1-12
END_DAY = 31          # 1-31

# Timesteps per hour (must evenly divide 60)
# Common values:
#   4  = 15-minute timesteps
#   6  = 10-minute timesteps
#   12 = 5-minute timesteps
TIMESTEPS_PER_HOUR = 6


# ------------------------------------------------------------------------
# NOTES
# ------------------------------------------------------------------------
# - Maximum simulation length is 1 year (365 or 366 days)
# - End date must be after start date (cannot cross year boundaries)