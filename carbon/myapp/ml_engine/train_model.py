"""
Trains and compares two models on the emissions dataset, then saves the
better one to ml_engine/model/carbon_emission_model.pkl for use by
predict.py.

Run directly:
    python ml_engine/train_model.py
"""

import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = os.path.dirname(__file__)
DATASET_PATH = os.path.join(BASE_DIR, "data", "emissions_dataset.csv")
MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "carbon_emission_model.pkl")

FEATURES = [
    "electricity_consumption",
    "fuel_consumption",
    "transportation_distance",
    "production_level",
    "month",
]
TARGET = "total_emission"


def load_data():
    df = pd.read_csv(DATASET_PATH)
    # basic cleaning: drop missing rows, ignore anything negative/impossible
    df = df.dropna()
    df = df[(df[FEATURES] >= 0).all(axis=1)]
    return df


def evaluate(model, X_test, y_test, name):
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = mean_squared_error(y_test, preds) ** 0.5
    r2 = r2_score(y_test, preds)

    print(f"\n{name}")
    print(f"  MAE  : {mae:.4f}")
    print(f"  RMSE : {rmse:.4f}")
    print(f"  R2   : {r2:.4f}")

    return {"model": model, "name": name, "mae": mae, "rmse": rmse, "r2": r2}


def train():
    df = load_data()
    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    linear_model = LinearRegression()
    linear_model.fit(X_train, y_train)
    linear_result = evaluate(linear_model, X_test, y_test, "Linear Regression")

    forest_model = RandomForestRegressor(n_estimators=200, random_state=42)
    forest_model.fit(X_train, y_train)
    forest_result = evaluate(forest_model, X_test, y_test, "Random Forest Regressor")

    # lower RMSE wins
    best = min([linear_result, forest_result], key=lambda r: r["rmse"])
    print(f"\nBest model: {best['name']} (RMSE={best['rmse']:.4f})")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(
        {"model": best["model"], "features": FEATURES, "model_name": best["name"]},
        MODEL_PATH,
    )
    print(f"Saved best model to {MODEL_PATH}")

    return best


if __name__ == "__main__":
    train()