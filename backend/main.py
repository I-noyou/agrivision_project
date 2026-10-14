from __future__ import annotations
import csv, itertools, json, math
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
FRONTEND = BASE.parent / "frontend" / "index.html"
with (DATA / "crops.json").open(encoding="utf-8") as f:
    CROPS = json.load(f)
with (DATA / "demo_parcels.json").open(encoding="utf-8") as f:
    PARCELS = json.load(f)

app = FastAPI(title="AgriVision Chhattisgarh API", version="1.0.0", description="Demo crop suitability and land-allocation API. Outputs are planning estimates, not guaranteed farm outcomes.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

DISTRICTS = ["Balod", "Baloda Bazar-Bhatapara", "Balrampur-Ramanujganj", "Bastar", "Bemetara", "Bijapur", "Bilaspur", "Dantewada", "Dhamtari", "Durg", "Gariaband", "Gaurela-Pendra-Marwahi", "Janjgir-Champa", "Jashpur", "Kabirdham", "Kanker", "Khairagarh-Chhuikhadan-Gandai", "Kondagaon", "Korba", "Korea", "Mahasamund", "Manendragarh-Chirmiri-Bharatpur", "Mohla-Manpur-Ambagarh Chowki", "Mungeli", "Narayanpur", "Raigarh", "Raipur", "Rajnandgaon", "Sakti", "Sarangarh-Bilaigarh", "Sukma", "Surajpur", "Surguja"]

class FarmInput(BaseModel):
    state: Literal["Chhattisgarh"] = "Chhattisgarh"
    district: str = "Durg"
    tehsil: str = "Bori"
    village: str = "Temri"
    khasra: str = "122/1"
    soil: Literal["clay", "loam", "sandy", "black", "red", "unknown"] = "loam"
    land_acres: float = Field(default=0.593, gt=0, le=500)
    budget_inr: float = Field(default=20000, ge=0, le=100000000)
    water: Literal["low", "medium", "high"] = "medium"
    season: Literal["kharif", "rabi", "zaid"] = "kharif"
    weather: Literal["normal", "dry", "wet", "heat"] = "normal"
    market: Literal["steady", "volatile", "high"] = "steady"
    preferred_crops: list[str] = Field(default_factory=list)
    @field_validator("khasra")
    @classmethod
    def clean_khasra(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 50: raise ValueError("Enter a valid Khasra number.")
        return v


def crop_cost(c: dict) -> float:
    return (c["cultivation_cost_min"] + c["cultivation_cost_max"]) / 2

def seed_cost(c: dict) -> float:
    vals = [c.get("seed_price_min"), c.get("seed_price_max"), c.get("seed_rate_kg_acre_min"), c.get("seed_rate_kg_acre_max")]
    if any(v is None for v in vals): return 0.0
    return ((vals[0] + vals[1]) / 2) * ((vals[2] + vals[3]) / 2)

def evaluate_crop(c: dict, x: FarmInput) -> dict:
    reasons, penalties = [], 0.0
    if x.soil != "unknown" and x.soil not in c["soils"]:
        penalties += 0.30; reasons.append("soil match is uncertain")
    else: reasons.append("soil screening passed or soil data is unknown")
    if x.water == "low" and c["water_need"] > 1:
        penalties += 0.35; reasons.append("water demand may exceed available supply")
    elif x.water == "medium" and c["water_need"] >= 3:
        penalties += 0.12; reasons.append("reliable irrigation would improve suitability")
    else: reasons.append("water-demand screening passed")
    if x.weather == "dry": penalties += 0.20 if c["water_need"] > 1 else 0.05
    elif x.weather == "wet": penalties += 0.15 if c["id"] != "paddy" else 0.02
    elif x.weather == "heat": penalties += 0.12
    if x.market == "volatile": penalties += 0.08
    if x.market == "high" and c["id"] in ("paddy", "maize"): penalties = max(0, penalties - 0.04)
    gross = c["yield_qtl_acre"] * c["selling_price_inr_qtl"]
    total_cost = crop_cost(c) + seed_cost(c)
    base_profit = gross - total_cost
    risk = min(0.9, c["risk_base"] + penalties)
    risk_adjusted_profit = base_profit * (1 - risk * 0.65)
    if x.preferred_crops and c["id"] in x.preferred_crops:
        risk_adjusted_profit += 500
        reasons.append("farmer preference applied")
    return {"id": c["id"], "name": c["name"], "seasons": c["seasons"], "soil_suitable": x.soil == "unknown" or x.soil in c["soils"], "water_need": c["water_need"], "seed_price_min": c["seed_price_min"], "seed_price_max": c["seed_price_max"], "seed_rate_kg_acre_min": c["seed_rate_kg_acre_min"], "seed_rate_kg_acre_max": c["seed_rate_kg_acre_max"], "cultivation_cost_per_acre": round(crop_cost(c)), "seed_cost_per_acre": round(seed_cost(c)), "estimated_gross_revenue_per_acre": round(gross), "estimated_total_cost_per_acre": round(total_cost), "estimated_net_profit_per_acre": round(base_profit), "risk_score": round(risk, 3), "risk_adjusted_profit_per_acre": round(risk_adjusted_profit), "selling_price_inr_qtl": c["selling_price_inr_qtl"], "selling_price_source": c["selling_price_source"], "data_status": c["data_status"], "reasons": reasons}

def candidate_crops(x: FarmInput) -> list[dict]:
    results = []
    for c in CROPS:
        if x.season not in c["seasons"]: continue
        e = evaluate_crop(c, x)
        # Exclude clearly poor matches for a low-water farm; retain borderline options with a risk penalty otherwise.
        if x.water == "low" and c["water_need"] >= 3: continue
        if x.soil != "unknown" and not e["soil_suitable"] and len([r for r in results]) > 0:
            # Keep mismatch as a lower-ranked alternative instead of silently claiming exact suitability.
            pass
        results.append(e)
    return sorted(results, key=lambda c: c["risk_adjusted_profit_per_acre"], reverse=True)

def compositions(total: int, parts: int):
    if parts == 1:
        yield (total,); return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1): yield (first,) + rest

def optimize_plan(x: FarmInput) -> dict:
    candidates = candidate_crops(x)
    if not candidates:
        raise HTTPException(status_code=422, detail="No crop candidates match this season and water constraint. Change the season or verify local agronomic advice.")
    unit = x.land_acres / max(1, min(200, int(math.ceil(x.land_acres / 0.05))))
    max_units = min(200, max(1, int(math.ceil(x.land_acres / unit - 1e-8))))
    # A crop may be split into 0.05-acre units. Enumerate crop sets up to 3 and allocations, selecting the best feasible risk-adjusted net return.
    best = {"score": -float("inf"), "alloc": [], "cost": 0.0, "land": 0.0}
    crop_pool = candidates[:min(5, len(candidates))]
    for count in range(1, min(3, len(crop_pool)) + 1):
        for subset in itertools.combinations(crop_pool, count):
            for total_units in range(1, max_units + 1):
                for alloc_units in compositions(total_units, count):
                    if count > 1 and any(u == 0 for u in alloc_units): continue
                    areas = [u * unit for u in alloc_units]
                    total_cost = sum(a * (c["estimated_total_cost_per_acre"]) for a, c in zip(areas, subset))
                    if total_cost > x.budget_inr + 0.01: continue
                    score = sum(a * c["risk_adjusted_profit_per_acre"] for a, c in zip(areas, subset))
                    # Small diversification bonus, not a substitute for agronomic constraints.
                    if count > 1: score += min(350, 100 * (count - 1))
                    if score > best["score"]:
                        best = {"score": score, "alloc": list(zip(subset, areas)), "cost": total_cost, "land": sum(areas)}
    if not best["alloc"]:
        # Explicit no-feasible-plan response rather than violating the budget.
        cheapest = min(candidates, key=lambda c: c["estimated_total_cost_per_acre"])
        return {"status": "infeasible", "message": "The entered budget is too low for the minimum modeled crop area. Increase the budget or enter verified local costs.", "land_acres": x.land_acres, "budget_inr": x.budget_inr, "total_cost_inr": 0, "estimated_gross_revenue_inr": 0, "estimated_net_profit_inr": 0, "allocated_area_acres": 0, "unused_area_acres": x.land_acres, "zones": [], "recommendations": candidates, "assumptions": assumptions()}
    zones, gross, net, cost = [], 0.0, 0.0, 0.0
    for i, (c, area) in enumerate(best["alloc"]):
        gross_i = area * c["estimated_gross_revenue_per_acre"]
        cost_i = area * c["estimated_total_cost_per_acre"]
        net_i = gross_i - cost_i
        zones.append({"zone": chr(65 + i), "crop_id": c["id"], "crop_name": c["name"], "area_acres": round(area, 3), "area_hectares": round(area / 2.47105, 4), "share_percent": round(area / x.land_acres * 100, 1), "seed_cost_inr": round(area * c["seed_cost_per_acre"]), "cultivation_cost_inr": round(area * c["cultivation_cost_per_acre"]), "total_cost_inr": round(cost_i), "gross_revenue_inr": round(gross_i), "estimated_net_profit_inr": round(net_i), "risk_adjusted_profit_inr": round(area * c["risk_adjusted_profit_per_acre"], 2), "risk_score": c["risk_score"], "data_status": c["data_status"]})
        gross += gross_i; net += net_i; cost += cost_i
    return {"status": "ok", "message": "Plan generated from local demo datasets and documented assumptions.", "land_acres": x.land_acres, "budget_inr": x.budget_inr, "total_cost_inr": round(cost), "estimated_gross_revenue_inr": round(gross), "estimated_net_profit_inr": round(net), "risk_adjusted_net_profit_inr": round(best["score"]), "allocated_area_acres": round(best["land"], 3), "unused_area_acres": round(max(0, x.land_acres - best["land"]), 3), "budget_remaining_inr": round(max(0, x.budget_inr - cost)), "zones": zones, "recommendations": candidates, "confidence": "low to moderate; depends on input and demo assumptions", "assumptions": assumptions()}

def assumptions():
    return ["This is a working MVP, not a validated agronomic decision system.", "Yield and cultivation-cost assumptions are illustrative and must be replaced with district-, season-, and variety-specific data.", "MSP is a benchmark, not a guaranteed sale price or guaranteed procurement.", "Khasra 122/1 is a manually entered demo record; no live government parcel lookup is performed.", "Crop zones are conceptual allocations and are not surveyed boundaries or georeferenced polygons.", "Risk adjustment is a transparent heuristic, not a calibrated stochastic yield model."]

@app.get("/api/health")
def health(): return {"status": "ok", "service": "AgriVision Chhattisgarh API", "version": "1.0.0"}
@app.get("/api/districts")
def districts(): return {"state": "Chhattisgarh", "districts": DISTRICTS}
@app.get("/api/crops")
def crops(): return {"items": [{k: v for k, v in c.items()} for c in CROPS]}
@app.get("/api/seed-prices")
def seed_prices():
    with (DATA / "seed_prices.csv").open(encoding="utf-8-sig", newline="") as f: return {"items": list(csv.DictReader(f))}
@app.get("/api/cultivation-costs")
def cultivation_costs():
    with (DATA / "cultivation_costs.csv").open(encoding="utf-8-sig", newline="") as f: return {"items": list(csv.DictReader(f))}
@app.post("/api/parcels/lookup")
def parcel_lookup(x: FarmInput):
    for p in PARCELS:
        if (p["district"].casefold(), p["tehsil"].casefold(), p["village"].casefold(), p["khasra"].casefold()) == (x.district.casefold(), x.tehsil.casefold(), x.village.casefold(), x.khasra.casefold()):
            return {"found": True, "parcel": p, "source_type": "demo record", "georeferenced": False}
    return {"found": False, "parcel": None, "source_type": "no connected government lookup", "message": "This Khasra number is not present in the local demo dataset. No live land-record lookup was performed."}
@app.post("/api/land/analyze")
def land_analyze(x: FarmInput):
    return {"inputs": x.model_dump(), "candidate_count": len(candidate_crops(x)), "candidates": candidate_crops(x), "assumptions": assumptions()}
@app.post("/api/crops/recommend")
def recommend(x: FarmInput): return {"items": candidate_crops(x), "assumptions": assumptions()}
@app.post("/api/optimize")
def optimize(x: FarmInput): return optimize_plan(x)
@app.get("/api/weather")
def weather(district: str = "Durg", scenario: str = "normal"):
    if district not in DISTRICTS: raise HTTPException(status_code=422, detail="Select a district in Chhattisgarh.")
    descriptions = {"normal": "Normal seasonal conditions (demo scenario)", "dry": "Below-normal rainfall / drought-risk scenario (demo)", "wet": "Excess rainfall / waterlogging-risk scenario (demo)", "heat": "High-temperature-risk scenario (demo)"}
    if scenario not in descriptions: raise HTTPException(status_code=422, detail="Unsupported weather scenario.")
    return {"district": district, "scenario": scenario, "description": descriptions[scenario], "is_live": False, "source": "User-selected simulation; no live weather provider connected"}

@app.get("/", include_in_schema=False)
def index(): return FileResponse(FRONTEND)
@app.get("/favicon.ico", include_in_schema=False)
def favicon(): raise HTTPException(status_code=404, detail="No favicon")
