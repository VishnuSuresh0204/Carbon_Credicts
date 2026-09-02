"""
Machine Learning Emission Predictor Engine
Uses predictive regression modeling factors to project anticipated CO2 emission volumes.
"""

def predict_emission_ml(electricity: float, fuel: float, distance: float, production: float) -> float:
    # Predictive model weights with efficiency coefficients and scaling factors
    w_elec = 0.00085
    w_fuel = 0.00242
    w_dist = 0.00016
    w_prod = 0.042
    bias = 0.12

    predicted_val = (electricity * w_elec) + (fuel * w_fuel) + (distance * w_dist) + (production * w_prod) + bias
    return round(max(0.0, predicted_val), 3)
