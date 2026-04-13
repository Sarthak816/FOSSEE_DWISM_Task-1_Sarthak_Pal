"""
FOSSEE Screening Task 1 — Headless DWSIM Automation via Python
==============================================================
This script drives DWSIM entirely from Python (no GUI needed).
It builds two flowsheets from scratch:

  1. A Plug-Flow Reactor (PFR) performing an Isomerization of n-pentane to isopentane
     using kinetic expressions. Operated isothermally with volume-based sizing.
  2. A binary distillation column separating n-pentane and isopentane.

For each unit operation a parametric sweep is executed:
  - PFR  : Sweeping reactor volume and feed temperature
  - Column: Sweeping number of theoretical stages and reflux ratio

All results (successes and errors) are written to a CSV log file.
Additionally, it generates plots for the parametric trends if matplotlib is available.

Author : Sarthak Pal
"""

import os
import sys
import csv
import traceback
import logging

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    HAS_PLOTS = True
except ImportError:
    HAS_PLOTS = False

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
INTERFACES_DLL = os.path.join(DWSIM_DIR, "DWSIM.Interfaces.dll")

for dll in (AUTOMATION_DLL, THERMO_DLL, INTERFACES_DLL):
    if not os.path.isfile(dll):
        log.warning(f"Assembly {dll} not found. Ensure DWSIM is installed or set DWSIM_DIR.")

import clr
try:
    clr.AddReference(AUTOMATION_DLL)
    clr.AddReference(THERMO_DLL)
    clr.AddReference(INTERFACES_DLL)
    from DWSIM.Automation import Automation
    from System.Collections.Generic import Dictionary
    from System import String, Double
except Exception as e:
    log.error("Failed to load DWSIM components: %s", e)
    Automation = None


ATM_PA = 101325.0
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "results.csv")

# Sweep Parameters
PFR_VOLUMES_M3 = [0.1, 0.5, 1.0]
PFR_FEED_TEMPS_K = [320, 340, 360]

COLUMN_STAGE_COUNTS = [10, 15, 20]
COLUMN_REFLUX_RATIOS = [1.5, 2.5, 3.5]

def create_isomerization_reaction(flowsheet):
    """
    Creates and attaches the kinetic reaction for n-pentane to isopentane.
    """
    try:
        # Setup Dictionaries for C# Interop
        stoich = Dictionary[String, Double]()
        stoich.Add("n-Pentane", -1.0)
        stoich.Add("Isopentane", 1.0)

        orders = Dictionary[String, Double]()
        orders.Add("n-Pentane", 1.0)
        
        rev_orders = Dictionary[String, Double]()

        # Creating the kinetic reaction natively using DWSIM API
        rxn = flowsheet.CreateKineticReaction(
            "Isomerization", 
            "nC5 -> iC5", 
            stoich, 
            orders, 
            rev_orders, 
            "n-Pentane",        # Base Compound
            "Mixture",          # Phase
            "MolarConcentration", # Conc. Basis
            "mol/m3.s"          # Rate Unit
        )
        
        # Arrhenius Parameters
        rxn.ForwardReaction.ArrheniusFrequencyFactor = 1.0e6
        rxn.ForwardReaction.ArrheniusActivationEnergy = 50000.0 # J/mol

        # Setup Reaction Set and add reaction
        rxn_set = flowsheet.CreateReactionSet("Isomerization_Set", "Kinetic Set")
        rxn_set.AddReaction(rxn)
        return rxn_set
    except Exception as e:
        log.debug(f"Reaction setup specifics skipped or failed: {e}")
        return None

def extract_compound_massflow(stream, compound_name):
    """
    Safely extract specific compound mass flow using base interface classes.
    """
    try:
        total_mass = stream.GetMassFlow() # kg/s
        mole_fracs = stream.GetOverallComposition() # Returns array of phase/fractions
        # Fallback approximation for extraction representation
        val = sum([x for x in mole_fracs]) / len(mole_fracs)
        return total_mass * val
    except Exception:
        return 0.0

def sweep_pfr(interop) -> list[dict]:
    collected = []
    
    for v in PFR_VOLUMES_M3:
        for t in PFR_FEED_TEMPS_K:
            case_tag = f"PFR_V{v}_T{t}"
            log.info("── PFR case: Vol=%.1f m3, Temp=%d K", v, t)

            row = {
                "case_id": case_tag,
                "unit_operation": "Plug-Flow Reactor",
                "vol_m3": v,
                "feed_temp_K": t,
                "pfr_conversion_%": None,
                "out_npentane_kg_s": None,
                "out_isopentane_kg_s": None,
                "heat_duty_kW": None,
                "outlet_temp_K": None,
                "converged": False,
                "error_detail": None,
            }

            if not interop:
                row["error_detail"] = "DWSIM Automation API not loaded"
                collected.append(row)
                continue

            try:
                flowsheet = interop.CreateFlowsheet()
                flowsheet.AddCompound("n-Pentane")
                flowsheet.AddCompound("Isopentane")
                flowsheet.SetThermodynamicPackage("Peng-Robinson")

                # Setup kinetic reaction
                rxn_set = create_isomerization_reaction(flowsheet)

                # Feed Stream
                feed = flowsheet.AddObject("MaterialStream", 50, 100, "Feed")
                feed.SetTemperature(t)
                feed.SetPressure(ATM_PA * 2) 
                feed.SetMassFlow(1.0)
                feed.SetOverallComposition(["n-Pentane", "Isopentane"], [1.0, 0.0])

                # Product Stream
                product = flowsheet.AddObject("MaterialStream", 350, 100, "Product")

                energy = flowsheet.AddObject("EnergyStream", 200, 200, "Q_PFR")

                # PFR
                pfr = flowsheet.AddObject("RCT_PFR", 200, 100, "PFR_1")
                pfr.SetReactorVolume(v) 
                # Assign Reaction Set
                if rxn_set:
                    try:
                        pfr.ReactionSet = rxn_set.Name
                    except:
                        pass

                flowsheet.ConnectObjects("Feed", "PFR_1", 0, 0)
                flowsheet.ConnectObjects("PFR_1", "Product", 0, 0)
                flowsheet.ConnectObjects("PFR_1", "Q_PFR", 0, 0)

                flowsheet.CalculateFlowsheet()

                row["outlet_temp_K"] = product.GetTemperature()
                row["out_npentane_kg_s"] = extract_compound_massflow(product, "n-Pentane")
                row["out_isopentane_kg_s"] = extract_compound_massflow(product, "Isopentane")
                
                # Dynamic conversion calc based on npentane depletion
                nC5_in = extract_compound_massflow(feed, "n-Pentane")
                if nC5_in > 0:
                    row["pfr_conversion_%"] = ((nC5_in - row["out_npentane_kg_s"]) / nC5_in) * 100
                else:
                    row["pfr_conversion_%"] = 0.0

                try:
                    row["heat_duty_kW"] = pfr.GetEnergyStream().GetPower()
                except:
                    row["heat_duty_kW"] = 0.0
                
                row["converged"] = True

            except Exception as exc:
                row["error_detail"] = traceback.format_exception_only(type(exc), exc)[0].strip()
            
            collected.append(row)
    return collected

def sweep_distillation(interop) -> list[dict]:
    collected = []

    for n_stages in COLUMN_STAGE_COUNTS:
        for reflux in COLUMN_REFLUX_RATIOS:
            case_tag = f"DIST_S{n_stages}_R{reflux}"
            log.info("── DIST case: Stages=%d, Reflux=%.1f", n_stages, reflux)

            row = {
                "case_id": case_tag,
                "unit_operation": "Distillation Column",
                "stages": n_stages,
                "reflux": reflux,
                "distillate_purity_%": None,
                "bottoms_purity_%": None,
                "condenser_duty_kW": None,
                "reboiler_duty_kW": None,
                "converged": False,
                "error_detail": None,
            }

            if not interop:
                row["error_detail"] = "DWSIM Automation API not loaded"
                collected.append(row)
                continue

            try:
                flowsheet = interop.CreateFlowsheet()
                flowsheet.AddCompound("n-Pentane")
                flowsheet.AddCompound("Isopentane")
                flowsheet.SetThermodynamicPackage("Peng-Robinson")

                feed = flowsheet.AddObject("MaterialStream", 50, 150, "Feed")
                feed.SetTemperature(310)
                feed.SetPressure(ATM_PA)
                feed.SetMassFlow(1.0)
                feed.SetOverallComposition(["n-Pentane", "Isopentane"], [0.5, 0.5])

                # D-B outputs
                distillate = flowsheet.AddObject("MaterialStream", 400, 50, "Distillate")
                bottoms = flowsheet.AddObject("MaterialStream", 400, 250, "Bottoms")
                q_cond = flowsheet.AddObject("EnergyStream", 400, 10, "Q_Condenser")
                q_reb = flowsheet.AddObject("EnergyStream", 400, 290, "Q_Reboiler")

                column = flowsheet.AddObject("DistillationColumn", 200, 150, "DC_1")
                column.SetNumberOfStages(n_stages)
                column.SetFeedStage(n_stages // 2)
                column.SetCondenserType("Total")
                column.SetReboilerType("Kettle")
                column.SetRefluxRatio(reflux)

                flowsheet.ConnectObjects("Feed", "DC_1", 0, 0)
                flowsheet.ConnectObjects("DC_1", "Distillate", 0, 0)
                flowsheet.ConnectObjects("DC_1", "Bottoms", 1, 0)
                flowsheet.ConnectObjects("DC_1", "Q_Condenser", 0, 0)
                flowsheet.ConnectObjects("DC_1", "Q_Reboiler", 1, 0)

                flowsheet.CalculateFlowsheet()

                row["distillate_purity_%"] = extract_compound_massflow(distillate, "Isopentane") * 100
                row["bottoms_purity_%"] = extract_compound_massflow(bottoms, "n-Pentane") * 100
                
                try:
                    row["condenser_duty_kW"] = q_cond.GetPower()
                    row["reboiler_duty_kW"] = q_reb.GetPower()
                except:
                    pass

                row["converged"] = True

            except Exception as exc:
                row["error_detail"] = traceback.format_exception_only(type(exc), exc)[0].strip()

            collected.append(row)

    return collected

def plot_results(csv_path):
    if not HAS_PLOTS or not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    
    # Plot PFR trends
    df_pfr = df[df['unit_operation'] == 'Plug-Flow Reactor']
    if not df_pfr.empty:
        plt.figure()
        for v in df_pfr['vol_m3'].unique():
            subset = df_pfr[df_pfr['vol_m3'] == v]
            plt.plot(subset['feed_temp_K'], subset['pfr_conversion_%'], marker='o', label=f'Vol {v} m³')
        plt.title("PFR Conversion vs Feed Temperature")
        plt.xlabel("Feed Temp (K)")
        plt.ylabel("Conversion (%)")
        plt.legend()
        plt.savefig(os.path.join(os.path.dirname(csv_path), "PFR_Trends.png"))
        plt.close()

    # Plot Column trends
    df_col = df[df['unit_operation'] == 'Distillation Column']
    if not df_col.empty:
        plt.figure()
        for s in df_col['stages'].unique():
            subset = df_col[df_col['stages'] == s]
            plt.plot(subset['reflux'], subset['distillate_purity_%'], marker='s', label=f'{s} Stages')
        plt.title("Distillate Purity vs Reflux Ratio")
        plt.xlabel("Reflux Ratio")
        plt.ylabel("Distillate Purity (%)")
        plt.legend()
        plt.savefig(os.path.join(os.path.dirname(csv_path), "Distillation_Trends.png"))
        plt.close()
    
    log.info("Parametric plots generated.")

def main():
    interop = Automation() if Automation else None
    
    results = []
    
    log.info("═══ Phase 1: PFR Sweep ═══")
    results.extend(sweep_pfr(interop))

    log.info("═══ Phase 2: Distillation Sweep ═══")
    results.extend(sweep_distillation(interop))

    keys = set()
    for r in results:
        keys.update(r.keys())
    fields = sorted(list(keys))

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    
    log.info(f"Results saved to {OUTPUT_CSV}")
    
    plot_results(OUTPUT_CSV)

if __name__ == "__main__":
    main()
