"""
Emission Calculator Service
Calculates total carbon emissions in metric tonnes (tCO2e) based on standard emission factors:
- Electricity: ~0.82 kg CO2 / kWh -> 0.00082 tCO2/kWh
- Fuel: ~2.31 kg CO2 / Liter -> 0.00231 tCO2/L
- Transportation: ~0.15 kg CO2 / km -> 0.00015 tCO2/km
- Production Level: ~0.04 tCO2 / production unit
"""

def calculate_emission(electricity: float, fuel: float, distance: float, production: float) -> float:
    e_factor = 0.00082
    f_factor = 0.00231
    d_factor = 0.00015
    p_factor = 0.04

    total = (electricity * e_factor) + (fuel * f_factor) + (distance * d_factor) + (production * p_factor)
    return round(total, 3)
