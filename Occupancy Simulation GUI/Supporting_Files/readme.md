# Supporting_Files Folder Guide

## You Don't Need to Modify Anything Here

This folder contains files the application needs to run — but you shouldn't need to edit any of them directly. All simulation customization happens through `user_settings.py` and the GUI itself.

---

## What's Inside
```
Supporting_Files/
├── obCoSim.xml ← Auto-updated by the app (don't edit manually)
├── FMUs/
│ ├── obFMU.exe
│ ├── obFMU_linux
│ └── obFMU_mac
└── Semantic_Files/
├── bldg2_AC_V1_PNNL.ttl
└── Ontology.ttl
```

---

## `obCoSim.xml`

This file controls simulation settings like start date, timestep, and duration.

**You don't need to edit this manually** — the app automatically updates it based on what you enter in `user_settings.py` every time you run the program.

---

## Semantic_Files/Building Model

Contains the semantic building model files (TTL format) that semi-auto populate the building's rooms, layout, and properties.
This workflow is desiged to work with the default Medium Office Prototype works out of the box.

**Future modifications to the workflow will support the use of different building models.**

---

## FMUs/Simulation Engine

Contains the actual simulation executable that runs your occupant behavior simulation.

- `obFMU.exe` — Windows
- `obFMU_linux` — Linux
- `obFMU_mac` — macOS

**Never modify these files.** The app automatically detects your operating system and uses the correct executable. These are pre-built simulation engines — editing or replacing them will break the simulation.

---
## Temporary Files (Safe to Ignore)

You may occasionally see `occupant_space_dict.xlsx` appear in this folder after running a simulation.

**This is normal and expected** — it's a temporary file automatically created by the simulation engine, then copied into your simulation's results folder (`simulation_summaries/`) for permanent storage.

**You can safely delete it from `Supporting_Files`** if you want to keep this folder clean — it will be recreated automatically the next time you run a simulation.

## Summary

 For standard use, you can ignore this entire folder. All the settings you need to change are in `user_settings.py`.