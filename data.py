"""Load the Telco Customer Churn dataset, or generate a realistic synthetic stand-in."""
from pathlib import Path
import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "telco_churn.csv"


def make_synthetic(n=7000, seed=42):
    """Synthetic data with the same schema as the Kaggle Telco dataset (churn ~26%)."""
    rng = np.random.default_rng(seed)
    tenure = np.clip(rng.exponential(30, n).astype(int) + 1, 1, 72)
    contract = rng.choice(["Month-to-month", "One year", "Two year"], n, p=[.55, .21, .24])
    internet = rng.choice(["DSL", "Fiber optic", "No"], n, p=[.34, .44, .22])
    payment = rng.choice(["Electronic check", "Mailed check", "Bank transfer", "Credit card"], n, p=[.34, .23, .22, .21])
    senior = rng.binomial(1, .16, n)
    partner = rng.choice(["Yes", "No"], n)
    dependents = rng.choice(["Yes", "No"], n, p=[.3, .7])
    tech = np.where(internet == "No", "No internet service", rng.choice(["Yes", "No"], n))
    security = np.where(internet == "No", "No internet service", rng.choice(["Yes", "No"], n))
    paperless = rng.choice(["Yes", "No"], n, p=[.6, .4])
    base = np.select([internet == "DSL", internet == "Fiber optic"], [45, 80], 20)
    monthly = np.round(base + rng.normal(0, 8, n) + 5 * (tech == "Yes"), 2).clip(18, 120)
    total = np.round(monthly * tenure * rng.uniform(.95, 1.05, n), 2)

    logit = (-2.6
             + 1.5 * (contract == "Month-to-month") - 1.2 * (contract == "Two year")
             + 0.9 * (internet == "Fiber optic")
             + 0.7 * (payment == "Electronic check")
             - 0.035 * tenure
             + 0.012 * (monthly - 65)
             + 0.4 * senior
             + 0.5 * (tech == "No") * (internet != "No")
             + 0.4 * (security == "No") * (internet != "No")
             + 0.25 * (paperless == "Yes")
             - 0.3 * (dependents == "Yes")
             + 1.1 * ((contract == "Month-to-month") & (internet == "Fiber optic") & (tenure < 12))
             - 0.9 * ((tenure > 36) & (contract != "Month-to-month"))
             + 0.8 * ((monthly > 90) & (payment == "Electronic check"))
             + rng.normal(0, 0.6, n))
    churn = rng.random(n) < 1 / (1 + np.exp(-logit))

    return pd.DataFrame({
        "customerID": [f"C{i:05d}" for i in range(n)],
        "gender": rng.choice(["Male", "Female"], n),
        "SeniorCitizen": senior, "Partner": partner, "Dependents": dependents,
        "tenure": tenure, "InternetService": internet, "TechSupport": tech,
        "OnlineSecurity": security, "Contract": contract,
        "PaperlessBilling": paperless, "PaymentMethod": payment,
        "MonthlyCharges": monthly, "TotalCharges": total,
        "Churn": np.where(churn, "Yes", "No"),
    })


def load_data():
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH)
        source = "Kaggle Telco CSV"
    else:
        df = make_synthetic()
        source = "synthetic data (drop the real CSV in data/telco_churn.csv to use it)"
    # Real file has blank TotalCharges for brand-new customers
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
    df["Churn"] = (df["Churn"] == "Yes").astype(int)
    return df.drop(columns=["customerID"]), source
