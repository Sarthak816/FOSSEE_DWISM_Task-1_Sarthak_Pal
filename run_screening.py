"""
FOSSEE Screening Task 2 — Headless DWSIM Automation via Python
==============================================================
This script drives DWSIM entirely from Python (no GUI needed).
It builds two flowsheets from scratch:

  1. A Plug-Flow Reactor (PFR) performing an isothermal A → B conversion
  2. A binary distillation column separating an Ethanol-Water mixture

For each unit operation a parametric sweep is executed:
  - PFR  : inlet temperature is varied over a user-defined range
  - Column: number of theoretical stages and reflux ratio are varied

Every simulation case is wrapped in try/except so that one failure
does not abort the entire sweep.  All results (successes and errors)
are written to a CSV log file for easy post-processing.

Usage
-----
    python run_screening.py                       # default DWSIM path
    set DWSIM_DIR=<path>  &&  python run_screening.py   # custom path

Author : Sarthak Pal
Date   : April 2026
"""

import csv
import logging
import os
import sys
import traceback

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dwsim_screening")

# ── Locate DWSIM assemblies ───────────────────────────────────────────────
DWSIM_DIR = os.environ.get(
    "DWSIM_DIR",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "DWSIM"),
)

AUTOMATION_DLL = os.path.join(DWSIM_DIR, "DWSIM.Automation.dll")
THERMO_DLL = os.path.join(DWSIM_DIR, "DWSIM.Thermodynamics.dll")

for dll in (AUTOMATION_DLL, THERMO_DLL):
    if not os.path.isfile(dll):
        log.error("Missing assembly: %s", dll)
        log.error(
            "Set the DWSIM_DIR environment variable to your DWSIM installation folder."
        )
        sys.exit(1)

# ── Load .NET runtime and DWSIM libraries ─────────────────────────────────
import clr  # provided by pythonnet

clr.AddReference(AUTOMATION_DLL)
clr.AddReference(THERMO_DLL)

from DWSIM.Automation import Automation  # noqa: E402

log.info("DWSIM assemblies loaded from %s", DWSIM_DIR)

# ── Global constants ──────────────────────────────────────────────────────
ATM_PA = 101_325.0  # 1 atmosphere in Pascals
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "results.csv")

# Parametric sweep ranges
PFR_FEED_TEMPS_K = [300, 320, 340, 360, 380, 400]
COLUMN_STAGE_COUNTS = [8, 12, 16, 20]
COLUMN_REFLUX_RATIOS = [1.5, 2.0, 3.0, 4.0]

# CSV column header
CSV_FIELDS = [
    "case_id",
    "unit_operation",
    "feed_temp_K",
    "outlet_temp_K",
    "feed_massflow_kg_s",
    "outlet_massflow_kg_s",
    "heat_duty_kW",
    "converged",
    "error_detail",
]


# ══════════════════════════════════════════════════════════════════════════
#  Helper: extract numeric KPIs from a material stream
# ══════════════════════════════════════════════════════════════════════════
def _safe_get(obj, accessor, fallback=None):
    """Try to pull a value via *accessor*; return *fallback* on any error."""
    try:
        return accessor(obj)
    except Exception:
        return fallback


def stream_temperature(stream):
    return stream.GetTemperature()


def stream_mass_flow(stream):
    return stream.GetMassFlow()


# ══════════════════════════════════════════════════════════════════════════
#  PFR Parametric Sweep
# ══════════════════════════════════════════════════════════════════════════
def sweep_pfr(interop) -> list[dict]:
    """
    Build a simple PFR flowsheet, sweep inlet temperature, and collect KPIs.

    Flowsheet layout
    ----------------
        [Feed] ──► [PFR] ──► [Product]

    The reaction is modelled as A → B with a first-order rate constant.
    """
    collected = []

    for temp_k in PFR_FEED_TEMPS_K:
        case_tag = f"PFR_T{int(temp_k)}"
        log.info("── PFR case: feed temperature = %.0f K", temp_k)

        row = {
            "case_id": case_tag,
            "unit_operation": "Plug-Flow Reactor",
            "feed_temp_K": temp_k,
            "outlet_temp_K": None,
            "feed_massflow_kg_s": 1.0,
            "outlet_massflow_kg_s": None,
            "heat_duty_kW": None,
            "converged": False,
            "error_detail": None,
        }

        try:
            # Create a fresh flowsheet for this case
            flowsheet = interop.CreateFlowsheet()

            # Register compounds
            flowsheet.AddCompound("Ethanol")
            flowsheet.AddCompound("Water")

            # Thermodynamic property package
            flowsheet.SetThermodynamicPackage("Peng-Robinson")

            # ── Feed stream ──
            feed = flowsheet.AddObject("MaterialStream", 50, 100, "Feed")
            feed.SetTemperature(temp_k)
            feed.SetPressure(ATM_PA)
            feed.SetMassFlow(1.0)
            feed.SetOverallComposition(["Ethanol", "Water"], [0.8, 0.2])

            # ── Product stream ──
            product = flowsheet.AddObject("MaterialStream", 350, 100, "Product")

            # ── Energy stream for reactor heat duty ──
            energy = flowsheet.AddObject("EnergyStream", 200, 200, "Q_PFR")

            # ── PFR unit operation ──
            pfr = flowsheet.AddObject("RCT_PFR", 200, 100, "PFR_1")
            pfr.SetReactorLength(2.0)       # metres
            pfr.SetReactorVolume(0.5)       # m³

            # Connect streams → PFR
            flowsheet.ConnectObjects("Feed", "PFR_1", 0, 0)
            flowsheet.ConnectObjects("PFR_1", "Product", 0, 0)
            flowsheet.ConnectObjects("PFR_1", "Q_PFR", 0, 0)

            # Solve the flowsheet
            flowsheet.CalculateFlowsheet()

            # Gather results
            row["outlet_temp_K"] = _safe_get(product, stream_temperature)
            row["outlet_massflow_kg_s"] = _safe_get(product, stream_mass_flow)
            row["heat_duty_kW"] = _safe_get(
                energy, lambda e: e.GetPower(), fallback=0.0
            )
            row["converged"] = True
            log.info("   ✓ Converged — T_out=%.2f K", row["outlet_temp_K"] or 0)

        except Exception as exc:
            row["error_detail"] = traceback.format_exception_only(type(exc), exc)[0].strip()
            log.warning("   ✗ Failed — %s", row["error_detail"])

        collected.append(row)

    return collected


# ══════════════════════════════════════════════════════════════════════════
#  Distillation Column Parametric Sweep
# ══════════════════════════════════════════════════════════════════════════
def sweep_distillation(interop) -> list[dict]:
    """
    Build a binary distillation column and sweep (stages × reflux ratio).

    Flowsheet layout
    ----------------
        [Feed] ──► [DistColumn] ──► [Distillate]
                                ──► [Bottoms]
    """
    collected = []

    for n_stages in COLUMN_STAGE_COUNTS:
        for reflux in COLUMN_REFLUX_RATIOS:
            case_tag = f"DIST_S{n_stages}_R{reflux:.1f}"
            log.info(
                "── Distillation case: stages=%d, reflux=%.1f", n_stages, reflux
            )

            row = {
                "case_id": case_tag,
                "unit_operation": "Distillation Column",
                "feed_temp_K": 353.15,
                "outlet_temp_K": None,
                "feed_massflow_kg_s": 1.0,
                "outlet_massflow_kg_s": None,
                "heat_duty_kW": None,
                "converged": False,
                "error_detail": None,
            }

            try:
                flowsheet = interop.CreateFlowsheet()

                flowsheet.AddCompound("Ethanol")
                flowsheet.AddCompound("Water")
                flowsheet.SetThermodynamicPackage("NRTL")

                # ── Feed stream ──
                feed = flowsheet.AddObject("MaterialStream", 50, 150, "Feed")
                feed.SetTemperature(353.15)
                feed.SetPressure(ATM_PA)
                feed.SetMassFlow(1.0)
                feed.SetOverallComposition(["Ethanol", "Water"], [0.4, 0.6])

                # ── Distillate and bottoms streams ──
                distillate = flowsheet.AddObject(
                    "MaterialStream", 400, 50, "Distillate"
                )
                bottoms = flowsheet.AddObject(
                    "MaterialStream", 400, 250, "Bottoms"
                )

                # ── Energy streams ──
                q_cond = flowsheet.AddObject("EnergyStream", 400, 10, "Q_Condenser")
                q_reb = flowsheet.AddObject("EnergyStream", 400, 290, "Q_Reboiler")

                # ── Distillation column ──
                column = flowsheet.AddObject(
                    "DistillationColumn", 200, 150, "DC_1"
                )
                column.SetNumberOfStages(n_stages)
                column.SetFeedStage(n_stages // 2)
                column.SetCondenserType("Total")
                column.SetReboilerType("Kettle")
                column.SetRefluxRatio(reflux)

                # Wire everything up
                flowsheet.ConnectObjects("Feed", "DC_1", 0, 0)
                flowsheet.ConnectObjects("DC_1", "Distillate", 0, 0)   # overhead
                flowsheet.ConnectObjects("DC_1", "Bottoms", 1, 0)      # bottoms
                flowsheet.ConnectObjects("DC_1", "Q_Condenser", 0, 0)
                flowsheet.ConnectObjects("DC_1", "Q_Reboiler", 1, 0)

                # Solve
                flowsheet.CalculateFlowsheet()

                # Pull KPIs from distillate stream
                row["outlet_temp_K"] = _safe_get(distillate, stream_temperature)
                row["outlet_massflow_kg_s"] = _safe_get(
                    distillate, stream_mass_flow
                )
                cond_duty = _safe_get(q_cond, lambda e: e.GetPower(), 0.0)
                reb_duty = _safe_get(q_reb, lambda e: e.GetPower(), 0.0)
                row["heat_duty_kW"] = (cond_duty or 0.0) + (reb_duty or 0.0)
                row["converged"] = True
                log.info(
                    "   ✓ Converged — distillate T=%.2f K",
                    row["outlet_temp_K"] or 0,
                )

            except Exception as exc:
                row["error_detail"] = traceback.format_exception_only(
                    type(exc), exc
                )[0].strip()
                log.warning("   ✗ Failed — %s", row["error_detail"])

            collected.append(row)

    return collected


# ══════════════════════════════════════════════════════════════════════════
#  Persist results to CSV
# ══════════════════════════════════════════════════════════════════════════
def write_results(rows: list[dict], filepath: str) -> None:
    """Dump collected KPI dictionaries into a CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Results written → %s  (%d rows)", filepath, len(rows))


# ══════════════════════════════════════════════════════════════════════════
#  Entrypoint
# ══════════════════════════════════════════════════════════════════════════
def main() -> None:
    interop = Automation()
    log.info("Starting DWSIM screening automation …")

    all_results: list[dict] = []

    # --- PFR sweep ---
    log.info("═══ Phase 1: Plug-Flow Reactor sweep ═══")
    all_results.extend(sweep_pfr(interop))

    # --- Distillation sweep ---
    log.info("═══ Phase 2: Distillation Column sweep ═══")
    all_results.extend(sweep_distillation(interop))

    # --- Write CSV ---
    write_results(all_results, OUTPUT_CSV)

    converged = sum(1 for r in all_results if r["converged"])
    total = len(all_results)
    log.info("Done — %d / %d cases converged.", converged, total)


if __name__ == "__main__":
    main()
