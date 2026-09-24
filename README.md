# RDF2OS

This folder contains the occupancy simulation and verification workflow used to generate, review, and validate occupancy assumptions for a building model.

The workflow is split into two related parts:

1. Occupancy Simulation GUI
2. Occupancy Verification

---

## 1) Occupancy Simulation GUI

Location:

`Occupancy Simulation GUI/`

This is the main simulation tool that generates the occupancy results used for analysis. It produces:

- raw simulation outputs in `simulation_results/{timestamp}/raw_simulation_data/`
- summary/configuration files in `simulation_results/{timestamp}/simulation_summaries/`
- plots in `simulation_results/{timestamp}/plots/`

The GUI creates a run-specific Excel workbook that is used as the configuration input for verification. For example:

`Occupancy Simulation GUI/simulation_results/2026-09-14_16_00/simulation_summaries/2026-09-14_16_00_temp_input.xlsx`

This generated workbook is the source of the config used in the verification step.

---

## 2) Occupancy Verification

Location:

`Occupancy Verification/`

This folder contains the workflow used to compare the configured occupancy targets against the simulated outputs and generate percent-difference and pass/fail summary analyses.

It expects the following input structure:

```text
Occupancy Verification/
├── config.py
├── input_data/
│   ├── OOS_config_files/
│   │   └── input_{CONFIG_NAME}.xlsx
│   └── simulation_results/
│       └── {CONFIG_NAME}/
│           ├── occSim.csv
│           ├── occSim_by_Occupant.csv
│           └── output_xml.xml
└── verification_results/
    └── {CONFIG_NAME}/
```

The key handoff is:

- The simulation GUI generates a workbook like `*_temp_input.xlsx`
- That workbook is copied or renamed into `Occupancy Verification/input_data/OOS_config_files/input_{CONFIG_NAME}.xlsx`
- The simulation outputs are copied into `Occupancy Verification/input_data/simulation_results/{CONFIG_NAME}/`
- `config.py` is then run to compare them

---

## Recommended workflow

1. Run the occupancy GUI from `Occupancy Simulation GUI/`
2. Save or copy the generated config workbook from the latest simulation results summary folder
3. Rename it to `input_{CONFIG_NAME}.xlsx`
4. Copy the raw result files into the matching verification folder under `input_data/simulation_results/{CONFIG_NAME}/`
5. Update `CONFIG_NAMES` in `Occupancy Verification/config.py`
6. Run:

```bash
python config.py
```

---

## Notes

- The configuration name must match exactly across all locations.
- The Excel workbook must contain the required sheets: `space_input`, `space_type_input`, and `behavior_input`.
- The result files under each simulation folder must come from the same run and configuration.
- Output reports are saved under `Occupancy Verification/verification_results/{CONFIG_NAME}/`.

---

## Related folders

- [Occupancy Simulation GUI](Occupancy%20Simulation%20GUI)
- [Occupancy Verification](Occupancy%20Verification)
