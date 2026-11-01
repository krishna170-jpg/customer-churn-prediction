"""Score customers with the saved model: python src/predict.py customers.csv"""
import sys
import joblib
import pandas as pd
from pathlib import Path
from features import add_features

model = joblib.load(Path(__file__).resolve().parents[1] / "churn_model.joblib")
df = pd.read_csv(sys.argv[1])
df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
ids = df.pop("customerID") if "customerID" in df else pd.RangeIndex(len(df))
df = df.drop(columns=["Churn"], errors="ignore")
out = pd.DataFrame({"customerID": ids, "churn_probability": model.predict_proba(add_features(df))[:, 1]})
print(out.sort_values("churn_probability", ascending=False).head(20).to_string(index=False))
