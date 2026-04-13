# FOSSEE Screening Task 1 — Python-Driven DWSIM Automation

> **Author:** Sarthak Pal  
> **Task:** Screening Task 1 — Python Automation of DWSIM  

---

## 1. Objective

The objective of this task is to evaluate the ability to use Python to control DWSIM via its Automation API, construct flowsheets programmatically, simulate a Plug Flow Reactor (PFR) and a Distillation Column, perform parametric sweep studies, and run simulations headlessly without opening the DWSIM GUI.

---

## 2. Deliverables

- `run_screening.py` – Main Python script driving the automation
- `requirements.txt` – List of Python dependencies
- `README.md` – Setup and execution instructions (this file)
- `results.csv` – Automatically generated output logging the parametric sweeps
- `*.png` - Optional plots showing parametric trends (generated on execution)

---

## 3. Implementation Details

### Part A – PFR Reactor Simulation
- **Reaction:** Isomerization of n-pentane to isopentane using kinetic expressions.
- **Mode:** Isothermal operation.
- **Sizing:** Volume-based sizing.
- **Reporting:** Conversion, outlet flow of n-pentane, isopentane, heat duty, and outlet temperature.

### Part B – Distillation Column Simulation
- **Separation:** Binary mixture of n-pentane and isopentane.
- **Specifications:** Number of stages, feed stage, reflux ratio, and distillate rate.
- **Reporting:** Distillate and bottoms purities, condenser duty, and reboiler duty.

### Part C – Parametric Sweeps
1. **PFR Sweep Variables:** Reactor Volume ($0.1\ m^3$ to $1.0\ m^3$) and Feed Temperature (320 K - 360 K).
2. **Column Sweep Variables:** Number of stages (10 - 20) and Reflux ratio (1.5 - 3.5).
All permutations are tested, and errors gracefully logged.

---

## 4. Setup and Execution

**Dependencies Required:**
- Local installation of DWSIM.
- Python 3.9+ with `pythonnet` installed.
- `pandas` and `matplotlib` (for optional plotting).

1. **Install python packages:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Execute Automation:**
   ```bash
   # If DWSIM lives in the default location (%LOCALAPPDATA%\DWSIM)
   python run_screening.py
   
   # If DWSIM is installed elsewhere, set it explicitly:
   set DWSIM_DIR=D:\Apps\DWSIM
   python run_screening.py
   ```

3. **Check Outputs:**
   - A `results.csv` file will be generated storing all KPI extracted from the simulated states.
   - Plots (`PFR_Trends.png` and `Distillation_Trends.png`) will be generated inside the execution folder.
