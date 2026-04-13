# FOSSEE Screening Task 2 — Python-Driven DWSIM Automation

> **Author:** Sarthak Pal  
> **Task:** Screening Task 2 — Automating DWSIM with Python  
> **Date:** April 2026

---

## What This Project Does

This repository contains a single Python script (`run_screening.py`) that
controls **DWSIM** entirely through its COM / .NET Automation API.  
No graphical interface is involved at any point — every flowsheet is
constructed, configured, solved, and queried from code.

Two unit operations are covered:

| # | Unit Operation | Key Sweep Parameter(s) |
|---|---------------|----------------------|
| 1 | **Plug-Flow Reactor (PFR)** | Inlet temperature (300 – 400 K) |
| 2 | **Distillation Column** | Number of stages × Reflux ratio |

Each sweep case lives inside its own `try / except` block so that a single
convergence failure never kills the entire run.  Every outcome (good or bad)
lands in a tidy CSV log.

---

## Repository Layout

```
FOSSEE_DWISM_Task-1_Sarthak_Pal/
├── run_screening.py    ← main driver script (the only file you need to run)
├── results.csv         ← generated automatically after a run
├── requirements.txt    ← Python dependencies
└── README.md           ← this file
```

---

## Prerequisites

| Dependency | Version | Purpose |
|-----------|---------|---------|
| **DWSIM** | latest | Process simulator (must be installed locally) |
| **Python** | ≥ 3.9 | Runtime |
| **pythonnet** | ≥ 3.0 | Bridges Python ↔ .NET so we can call DWSIM's API |

Install the Python packages with:

```bash
pip install -r requirements.txt
```

---

## How to Run

```bash
# If DWSIM lives in the default location (%LOCALAPPDATA%\DWSIM)
python run_screening.py

# If DWSIM is installed elsewhere, point DWSIM_DIR at it
set DWSIM_DIR=D:\Apps\DWSIM
python run_screening.py
```

The script will:

1. Load the DWSIM automation and thermodynamics assemblies.
2. Run a **PFR temperature sweep** (6 cases).
3. Run a **distillation column sweep** over stages × reflux (16 cases).
4. Write everything to `results.csv`.

Console output uses colour-coded status messages so you can immediately
see which cases converged and which did not.

---

## PFR Sweep Details

| Property | Value |
|----------|-------|
| Reaction | Ethanol → Products (model reaction) |
| Feed composition | 80 mol% Ethanol, 20 mol% Water |
| Pressure | 1 atm |
| Mass flow | 1.0 kg/s |
| Reactor volume | 0.5 m³ |
| Reactor length | 2.0 m |
| Thermo package | Peng-Robinson |
| Swept variable | **Inlet temperature** (300, 320, 340, 360, 380, 400 K) |

**KPIs collected:** outlet temperature, outlet mass-flow rate, heat duty.

---

## Distillation Column Sweep Details

| Property | Value |
|----------|-------|
| System | Ethanol / Water binary |
| Feed composition | 40 mol% Ethanol, 60 mol% Water |
| Feed temperature | 353.15 K (≈ 80 °C) |
| Feed pressure | 1 atm |
| Condenser | Total |
| Reboiler | Kettle |
| Thermo package | NRTL |
| Swept variables | **Stages** (8, 12, 16, 20) × **Reflux ratio** (1.5, 2.0, 3.0, 4.0) |

**KPIs collected:** distillate temperature, distillate mass-flow rate,
combined condenser + reboiler duty.

---

## Output Format (`results.csv`)

| Column | Description |
|--------|-------------|
| `case_id` | Human-readable tag, e.g. `PFR_T340` or `DIST_S12_R2.0` |
| `unit_operation` | Which equipment this row belongs to |
| `feed_temp_K` | Feed-stream temperature in Kelvin |
| `outlet_temp_K` | Outlet-stream temperature in Kelvin |
| `feed_massflow_kg_s` | Feed mass-flow rate (kg/s) |
| `outlet_massflow_kg_s` | Outlet mass-flow rate (kg/s) |
| `heat_duty_kW` | Duty reported by the energy stream(s) |
| `converged` | `True` if the solver converged without errors |
| `error_detail` | Error message when convergence fails, blank otherwise |

---

## Error-Handling Strategy

* Every simulation case is executed inside its own `try / except`.
* If one case throws an exception the error message is captured into the
  `error_detail` column and the loop moves on to the next case.
* The final summary printed to the console shows `converged / total` so
  you can quickly gauge overall success.

---

## Design Choices

1. **No pre-built flowsheets** — every flowsheet is assembled from scratch
   inside the script via `CreateFlowsheet()`, `AddObject()`, and
   `ConnectObjects()`.  This keeps the repository self-contained.

2. **One flowsheet per case** — creating a fresh flowsheet for each set of
   parameters avoids stale state from a previous solve polluting the next
   one.

3. **Pure script execution** — although early prototyping happened in a
   notebook, the final deliverable is a regular `.py` file suitable for
   command-line or CI usage.

---

## Submission Checklist (FOSSEE)

- [x] `run_screening.py` — main automation code
- [x] `results.csv` — auto-generated output
- [x] `requirements.txt` — dependency list
- [x] `README.md` — documentation (this file)
