"""
Loads the trained model (once, at import time) and exposes a simple
predict_emission_ml() function for views.py to call.
"""

import os
from datetime import date
import joblib
import pandas as pd

BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "model", "carbon_emission_model.pkl")

_bundle = None  # lazy-loaded so importing this module doesn't fail if the
                 # model hasn't been trained yet


def _load_bundle():
    global _bundle
    if _bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                "No trained model found. Run `python ml_engine/train_model.py` first."
            )
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def predict_emission_ml(electricity, fuel, distance, production, month=None):
    """
    Predict total carbon emission for given activity data.

    Args:
        electricity: electricity consumption (kWh)
        fuel: fuel consumption (litres)
        distance: transportation distance (km)
        production: production level (units)
        month: 1-12, defaults to the current month if not given

    Returns:
        float: predicted total emission (tonnes CO2e)
    """
    bundle = _load_bundle()
    model = bundle["model"]
    features = bundle["features"]

    if month is None:
        month = date.today().month

    row = {
        "electricity_consumption": electricity,
        "fuel_consumption": fuel,
        "transportation_distance": distance,
        "production_level": production,
        "month": month,
    }

    X = pd.DataFrame([row])[features]
    prediction = model.predict(X)[0]

    return round(float(prediction), 4)


if __name__ == "__main__":
    # quick manual check: python ml_engine/predict.py
    result = predict_emission_ml(9500, 480, 1900, 4700)
    print(f"Predicted emission: {result} tonnes CO2e")