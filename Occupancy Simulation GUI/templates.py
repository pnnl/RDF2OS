"""
templates.py

Stores all simulation input template data that was previously
read from OOS_input_template.xlsx. Eliminates the need for the
Config_Files folder and Excel template file entirely.
"""

import pandas as pd
import numpy as np


# ============================================================
# BEHAVIOR TEMPLATE
# Used in RoomSetting.run_simulation() to structure
# occupant behavior input for the simulation engine
# ============================================================

BEHAVIOR_TEMPLATE_DATA = {
    'OccType': [
        'Season',
        'Days',
        'typical arrival time [hh:mm]',
        'arrival time variation [min]',
        'typical departure time [hh:mm]',
        'departure time variation [min]',
        'percent of time in space - Own office [%]',
        'average stay time - Own office [min]',
        'percent of time in space - Other offices [%]',
        'average stay time - Other offices [min]',
        'percent of time in space -  Meeting rooms [%]',
        'average stay time -  Meeting rooms [min]',
        'percent of time in space -  Auxiliary rooms [%]',
        'average stay time -  Auxiliary rooms [min]',
        'percent of time in space -  Outdoor [%]',
        'average stay time -  Outdoor [min]',
        'typical short-term leaving [hh:mm]',
        'short-term leaving variation [min]',
        'typical short-term leaving duration [min]',
        'short-term leaving duration variation [min]'
    ],
    'Values': [
        'All',
        'Monday, Tuesday, Wednesday, Thursday, Friday',
        '12:00',
        240,
        '15:00',
        240,
        45,
        60,
        15,
        10,
        35,
        60,
        4,
        5,
        1,
        5,
        '13:00',
        30,
        45,
        15
    ]
}

behavior_template = pd.DataFrame(BEHAVIOR_TEMPLATE_DATA)


# ============================================================
# OCC SPACE OPTIONS
# Defines default time distribution across space types
# for each predefined occupant type.
# Used in RoomSetting.run_simulation() and ViewOccDefaults.
# ============================================================

OCC_SPACE_OPTIONS_DATA = {
    'Space':      ['Own Office', np.nan, 'Other Offices', np.nan,
                   'Meeting Rooms', np.nan, 'Auxiliary', np.nan,
                   'Outdoor', np.nan],
    'Parameters': ['[%]', '[mins]', '[%]', '[mins]',
                   '[%]', '[mins]', '[%]', '[mins]',
                   '[%]', '[mins]'],
    'Recluse':       [70, 120,  5,  10, 10, 60, 10, 10,  5, 10],
    'Social':        [10,   5, 55,  15, 20, 10, 10, 10,  5,  0],
    'Meeting Heavy': [25,  90,  5,  10, 55, 60, 10,  5,  5,  5],
    'Cleaning':      [ 3,   5, 60,  15,  5, 10, 32, 10,  0,  0],
    'Maintenance':   [ 5,   5, 20,   5, 40, 10, 30, 15,  5,  5],
    'Manager':       [15,  90, 10,  10, 70, 60,  4,  5,  1,  5],
    'Regular Staff': [70,  30, 15,  30, 10, 60,  4,  5,  1,  5],
}

occ_space_options = pd.DataFrame(OCC_SPACE_OPTIONS_DATA)


# ============================================================
# SPACE INPUT TEMPLATE
# Defines default office and conference room settings
# used as the baseline simulation input structure.
# Used in RoomSetting.run_simulation().
# ============================================================

SPACE_INPUT_TEMPLATE_DATA = {
    'Office': [
        'Office: Occupancy Density [m2/person]',
        'Office: occupant percentage - occtype_0 [%]',
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan
    ],
    'Office_Values': [
        10,
        100,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
        np.nan
    ],
    'Conference Room': [
        'Seasons',
        'Days of week',
        'Conference Room: minimum number of meeting per day',
        'Conference Room: maximum number of meeting per day',
        'Conference Room: minimum number of people per meeting',
        'Conference Room: maximum number of people per meeting',
        'Conference Room: probability of 30-min meetings [%]',
        'Conference Room: probability of 60-min meetings [%]',
        'Conference Room: probability of 90-min meetings [%]',
        'Conference Room: probability of 120-min meetings [%]',
        np.nan,
        np.nan
    ],
    'Default Value': [
        'Summer, Winter, Spring, Fall',
        'Weekdays',
        0,
        3,
        1,
        6,
        70,
        30,
        0,
        0,
        np.nan,
        np.nan
    ]
}

space_input_template_df = pd.DataFrame(SPACE_INPUT_TEMPLATE_DATA)


# ============================================================
# SPACE INPUT SHEET TEMPLATE
# The blank per-room template used to build the
# space_input sheet in the simulation Excel file.
# Previously read from sheet 'space_input_template'.
# ============================================================

SPACE_INPUT_SHEET_COLUMNS = [
    'Room/Enclosure',
    'Number of occupants',
    'Occupant density (m^2/person)',
    'Area (m^2)',
    'Qty',
    'Space Type'
]

def get_space_input_template(num_rows=200):
    """
    Generate a blank space input template DataFrame.

    Args:
        num_rows (int): Number of rows to pre-allocate (default 200)

    Returns:
        pd.DataFrame: Blank space input template
    """
    return pd.DataFrame(
        index=range(num_rows),
        columns=SPACE_INPUT_SHEET_COLUMNS
    )