"""Feature engineering + preprocessing. All fitting happens inside the sklearn Pipeline,
so there is no leakage from test folds into scalers/encoders."""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer


def add_features(df):
    df = df.copy()
    df["avg_monthly_spend"] = df["TotalCharges"] / df["tenure"].clip(lower=1)
    df["charge_vs_avg"] = df["MonthlyCharges"] - df["avg_monthly_spend"]
    df["tenure_bucket"] = pd.cut(df["tenure"], [0, 6, 12, 24, 48, 100],
                                 labels=["0-6", "7-12", "13-24", "25-48", "49+"]).astype(str)
    df["is_new_customer"] = (df["tenure"] <= 6).astype(int)
    return df


def build_preprocessor(X):
    num = X.select_dtypes(include=np.number).columns.tolist()
    cat = X.select_dtypes(exclude=np.number).columns.tolist()
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat),
    ])
