# Offline Occupancy Simulator

A GUI-based tool for simulating stochastic occupant behavior in office buildings using the Medium Office Prototype semantic building models (ASHRAE 223P) and customizable simulation parameters.

## Overview

This tool enables users to:
- Configure custom occupant types with arrival/departure patterns and short-term leaving behaviors
- Define office spaces (private, open, shared, mechanical) with occupant type distributions
- Configure meeting rooms with customizable schedules and attendance patterns (Conference, Food Prep, Classroom, Collaboration)
- Run configurable occupancy simulations (variable duration, timestep, and start conditions)
- Automatically visualize and export simulation results by space type and occupant category

---

## Quick Start

### 1. Prerequisites
- **Python 3.11 or 3.12** (Windows/Linux/macOS supported)

### 2. Configure Your Project
Edit `user_settings.py` with your project path and simulation parameters:

```
PROJECT_ROOT = "C:/Projects/Offline_Occupancy_Simulator"
START_DAY_OF_WEEK = "Monday"
IS_LEAP_YEAR = False
START_MONTH = 1
START_DAY = 1
END_MONTH = 12
END_DAY = 31
TIMESTEPS_PER_HOUR = 6
```

### 3. Run OOS_GUI_main.py file 
-The GUI will populate a new window

### 4. Follow the GUI workflow
1. Select number of occupant types to include in your simulation

2. Define occupant types (arrival/departure times,        behaviors). You can select pre-loaded occupant types from the drop down menu, or create your own using the "Create new, customized occupant type" button

3. Configure office space percentages

4. Configure meeting room settings (or leave as defaults)

5. Customize specific rooms (or leave as defaults)

6. Run simulation

7. View auto-generated visualizations

8. Click the "Finish and close!" button to close the application.

### 5. View plots, raw simulation data, and summarized simulation data in the "Simulation_Results" folder

Project structure:
```
Offline_Occupancy_Simulator/
├── OOS_GUI_main.py              # Main GUI application
├── helper_functions.py           # SPARQL/Occupancy helper classes
├── func_run.py                   # Simulation orchestrator
├── occSim_classes_SPARQL.py     # Core simulation classes
├── config.py                     # Configuration management
├── user_settings.py              # USER-EDITABLE settings
├── workdays.csv                  # Workday/holiday calendar
│
├── Supporting_Files/
│   ├── obCoSim.xml               # Simulator configuration (auto-updated by application)
│   ├── Config_Files/
│   │   └── OOS_input_template.xlsx
│   ├── FMUs/
│   │   ├── obFMU.exe             # Windows executable
│   │   ├── obFMU_linux           # Linux executable
│   │   └── obFMU_mac             # macOS executable
│   └── Semantic_Files/
│       ├── bldg2_AC_V1_PNNL.ttl  # Medium Office Prototype building model info provided by PNNL
│       └── Ontology.ttl          # Library of ASHRAE 223 elements used to make the bldg2_AC_V1_PNNL model file
│
└── simulation_trials/            # Auto-generated simulation outputs
    └── {timestamp}/
        ├── plots/                 # All visualization PNGs
        ├── simulation_summaries/  # Intermediate CSVs/Excel files
        └── raw_simulation_data/   # Raw occSim.csv, occSim_by_Occupant.csv simulation outputs
```
## Where to Find Your Results

Every time you run a simulation, a **new folder** is created in {PROJECT_ROOT}/simulation_trials/{timestamp}/

The `{timestamp}` shows when you started the simulation (e.g., `2025-01-15_14_30` means January 15, 2025 at 2:30 PM).

---

## What's Inside
```
{timestamp}/
├── plots/ ← Visualizations of simulation results by space type
├── simulation_summaries/ ← Configurations you used
└── raw_simulation_data/ ← Raw simulation numbers
```

---

## Indide the plots folder

This is probably what you're looking for. It contains **9 charts** showing occupancy patterns throughout the day:

| File | Shows |
|------|-------|
| `whole_bldg.png` | Overall building occupancy (% of max) |
| `open_office.png` | Who's in open offices, by job type |
| `private_office.png` | Who's in private offices, by job type |
| `shared_office.png` | Who's in shared offices, by job type |
| `mechanical.png` | Mechanical room occupancy |
| `conference.png` | Conference room occupancy |
| `dining.png` | Dining room occupancy |
| `bathroom.png` | Bathroom occupancy |
| `storage.png` | Storage room occupancy |

**All plots are generated automatically**

---

## Inside the simulation_summaries Folder

This contains the **settings you chose** during setup. Useful if you want to:
- Remember what configuration you used
- Re-create a similar simulation later
- Troubleshoot unexpected results

---

## Inside the raw_simulation_data Folder

This contains the **raw numbers** behind your plots:

- `occSim.csv` — Occupancy counts for every room, every timestep
- `occSim_by_Occupant.csv` — Where each individual person was, every timestep

**Use this if:** You want to use the occupancy validation Python tool created by PNNL, or do your own custom analysis in Excel, Python, or another tool.

---

## Quick Tips

**To view your plots:** Just open the `.png` files in the `plots/` folder with any image viewer

**To find your latest run:** Sort the `simulation_trials` folder by date — the newest timestamp is your most recent simulation

**To free up space:** Old simulation folders can be safely deleted once you've saved the results you need

**Don't manually edit** files in `simulation_summaries/` or `raw_simulation_data/` — these are generated automatically and edits won't affect future runs
