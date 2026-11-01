"""Streamlit demo: streamlit run app.py"""
import sys
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from features import add_features, build_preprocessor  # noqa: E402
from data import load_data  # noqa: E402

MODEL_PATH = ROOT / "churn_model.joblib"


def train_quick_model():
    """Fallback: fit a small calibrated model on startup (a few seconds)."""
    from sklearn.pipeline import Pipeline
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV

    df, _ = load_data()
    df = add_features(df)
    X, y = df.drop(columns="Churn"), df["Churn"]
    pipe = Pipeline([("pre", build_preprocessor(X)),
                     ("m", HistGradientBoostingClassifier(learning_rate=0.05, max_iter=150, random_state=42))])
    return CalibratedClassifierCV(pipe, method="isotonic", cv=3).fit(X, y)


@st.cache_resource(show_spinner="Loading model...")
def get_model():
    if MODEL_PATH.exists():
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            pass  # e.g. scikit-learn version mismatch -> retrain below
    return train_quick_model()


st.title("Customer Churn Risk Calculator")
model = get_model()

c1, c2 = st.columns(2)
tenure = c1.slider("Tenure (months)", 1, 72, 12)
monthly = c1.slider("Monthly charges ($)", 18, 120, 70)
contract = c1.selectbox("Contract", ["Month-to-month", "One year", "Two year"])
internet = c2.selectbox("Internet", ["DSL", "Fiber optic", "No"])
payment = c2.selectbox("Payment", ["Electronic check", "Mailed check", "Bank transfer", "Credit card"])
tech = c2.selectbox("Tech support", ["Yes", "No", "No internet service"])

row = pd.DataFrame([{"gender": "Male", "SeniorCitizen": 0, "Partner": "No", "Dependents": "No", "tenure": tenure,
                     "InternetService": internet, "TechSupport": tech, "OnlineSecurity": tech, "Contract": contract,
                     "PaperlessBilling": "Yes", "PaymentMethod": payment, "MonthlyCharges": monthly,
                     "TotalCharges": monthly * tenure}])
p = model.predict_proba(add_features(row))[0, 1]
st.metric("Churn probability", f"{p:.1%}")
st.progress(float(p))
st.caption("Demo model. Predictions are illustrative, not business advice.")
