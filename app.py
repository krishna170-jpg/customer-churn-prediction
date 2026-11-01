"""Streamlit demo: streamlit run app.py"""
import joblib, pandas as pd, streamlit as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from features import add_features

st.title("Customer Churn Risk Calculator")
model = joblib.load(Path(__file__).parent / "churn_model.joblib")
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
