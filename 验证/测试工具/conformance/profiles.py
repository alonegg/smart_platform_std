"""附录 A.6、表 A.9；选择不代表符合性。"""
import json
from . import ROOT

PROFILES = json.loads((ROOT / "profiles.json").read_text())
CASE_IDS = sorted([f"T{i:02}" for i in range(1, 27)] + ["T08-" + s for s in "PCAR"] + ["T12-T", "T12-O", "T12-R", "T20-F", "T20-L", "T20-E"])


def select(profiles, stages=("P", "C", "A", "R"), triggers=()):
    if set(profiles) - PROFILES.keys() or set(stages) - set("PCAR") or set(triggers) - set(CASE_IDS):
        raise ValueError("unknown Profile, stage or trigger")
    selected = set().union(*(set(PROFILES[p]["basic"]) for p in profiles))
    selected.update(triggers)
    if "T08" in selected:
        selected.remove("T08")
        selected.update("T08-" + s for s in stages)
    if {"P-AI", "P-GRD"} <= set(profiles):
        selected.add("T08-P")
    for parent, children in {"T12": ("T", "O", "R"), "T20": ("F", "L", "E")}.items():
        if parent in selected:
            selected.remove(parent)
            selected.update(parent + "-" + s for s in children)
    return selected
