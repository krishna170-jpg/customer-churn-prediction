"""End-to-end churn pipeline: EDA -> baseline -> model comparison -> tuning -> business impact."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import (train_test_split, StratifiedKFold, cross_validate,
                                     RandomizedSearchCV, cross_val_predict)
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score, precision_recall_curve,
                             roc_curve, confusion_matrix, classification_report)
from sklearn.inspection import permutation_importance
from sklearn.calibration import CalibratedClassifierCV

from data import load_data
from features import add_features, build_preprocessor

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SEED = 42

# ---- Business assumptions (edit these!) -------------------------------------
CUSTOMER_VALUE = 500     # revenue retained if a churner is saved
OFFER_COST = 50          # cost of one retention offer (discount/call)
SAVE_RATE = 0.30         # share of contacted churners the offer actually saves
# -----------------------------------------------------------------------------


def eda(df):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    df["Churn"].value_counts().rename({0: "Stayed", 1: "Churned"}).plot.bar(ax=ax[0], color=["#4c72b0", "#c44e52"])
    ax[0].set_title(f"Class balance (churn rate {df['Churn'].mean():.1%})")
    df.groupby("Contract")["Churn"].mean().plot.bar(ax=ax[1], color="#55a868")
    ax[1].set_title("Churn rate by contract"); ax[1].set_ylabel("rate")
    df.groupby(pd.cut(df["tenure"], [0, 6, 12, 24, 48, 72]), observed=True)["Churn"].mean().plot.bar(ax=ax[2], color="#8172b2")
    ax[2].set_title("Churn rate by tenure (months)")
    plt.tight_layout(); plt.savefig(REPORTS / "01_eda.png", dpi=130); plt.close()


def expected_profit(y_true, proba, threshold):
    contacted = proba >= threshold
    tp = ((y_true == 1) & contacted).sum()
    return tp * SAVE_RATE * CUSTOMER_VALUE - contacted.sum() * OFFER_COST


def main():
    REPORTS.mkdir(exist_ok=True)
    df, source = load_data()
    print(f"Data source: {source}\nRows: {len(df)}  Churn rate: {df.Churn.mean():.1%}")
    df = add_features(df)
    eda(df)

    X, y = df.drop(columns="Churn"), df["Churn"]
    # Hold out a test set FIRST; touch it only once at the end.
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)

    pre = build_preprocessor(X_tr)
    models = {
        "Logistic Regression (baseline)": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "Random Forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight="balanced_subsample",
                                                n_jobs=-1, random_state=SEED),
        "Gradient Boosting": HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, random_state=SEED),
    }
    try:
        from xgboost import XGBClassifier
        models["XGBoost"] = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=4,
                                          scale_pos_weight=(y_tr == 0).sum() / (y_tr == 1).sum(),
                                          eval_metric="logloss", random_state=SEED)
    except ImportError:
        pass

    # ---- Cross-validated comparison (train set only) ----
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    rows = []
    for name, m in models.items():
        res = cross_validate(Pipeline([("pre", pre), ("m", m)]), X_tr, y_tr, cv=cv,
                             scoring=["roc_auc", "average_precision"], n_jobs=-1)
        rows.append({"model": name, "ROC-AUC": res["test_roc_auc"].mean(), "ROC-AUC std": res["test_roc_auc"].std(),
                     "PR-AUC": res["test_average_precision"].mean()})
        print(f"{name:34s} ROC-AUC {rows[-1]['ROC-AUC']:.3f} ± {rows[-1]['ROC-AUC std']:.3f} | PR-AUC {rows[-1]['PR-AUC']:.3f}")
    cv_table = pd.DataFrame(rows).sort_values("PR-AUC", ascending=False)
    cv_table.to_csv(REPORTS / "cv_results.csv", index=False)

    # ---- Tune the best non-baseline model ----
    best_name = cv_table[~cv_table.model.str.contains("baseline")].iloc[0]["model"]
    print(f"\nTuning: {best_name}")
    best = Pipeline([("pre", pre), ("m", models[best_name])])
    param_grids = {
        "Random Forest": {"m__max_depth": [4, 6, 8, None], "m__min_samples_leaf": [3, 5, 10, 20], "m__max_features": ["sqrt", 0.3]},
        "Gradient Boosting": {"m__learning_rate": [0.02, 0.05, 0.1], "m__max_depth": [3, 4, 6, None],
                              "m__min_samples_leaf": [20, 50, 100], "m__l2_regularization": [0, 1, 5]},
        "XGBoost": {"m__max_depth": [3, 4, 6], "m__learning_rate": [0.02, 0.05, 0.1], "m__subsample": [0.7, 0.9, 1.0]},
    }
    search = RandomizedSearchCV(best, param_grids[best_name], n_iter=12, scoring="average_precision",
                                cv=cv, random_state=SEED, n_jobs=-1)
    search.fit(X_tr, y_tr)
    tuned = search.best_estimator_
    print("Best params:", search.best_params_)

    # Calibrate so predicted probabilities can be trusted for cost-based thresholding
    final = CalibratedClassifierCV(tuned, method="isotonic", cv=5).fit(X_tr, y_tr)

    # ---- Final evaluation on held-out test set ----
    base = Pipeline([("pre", pre), ("m", models["Logistic Regression (baseline)"])]).fit(X_tr, y_tr)
    p_base, p_final = base.predict_proba(X_te)[:, 1], final.predict_proba(X_te)[:, 1]
    summary = {
        "baseline_roc_auc": roc_auc_score(y_te, p_base), "baseline_pr_auc": average_precision_score(y_te, p_base),
        "final_model": best_name,
        "final_roc_auc": roc_auc_score(y_te, p_final), "final_pr_auc": average_precision_score(y_te, p_final),
    }

    # ---- Cost-optimal threshold (chosen on train out-of-fold predictions, NOT on test) ----
    oof = cross_val_predict(tuned, X_tr, y_tr, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
    grid = np.linspace(0.05, 0.9, 86)
    profits = [expected_profit(y_tr.values, oof, t) for t in grid]
    best_t = grid[int(np.argmax(profits))]
    pred = (p_final >= best_t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel()
    profit_model = expected_profit(y_te.values, p_final, best_t)
    profit_all = expected_profit(y_te.values, np.ones(len(y_te)), 0.5)   # contact everyone
    summary.update({"threshold": float(best_t), "precision": tp / (tp + fp), "recall": tp / (tp + fn),
                    "profit_model": float(profit_model), "profit_contact_everyone": float(profit_all),
                    "profit_do_nothing": 0.0, "test_customers": int(len(y_te))})
    print("\n", classification_report(y_te, pred, target_names=["Stayed", "Churned"]))

    # ---- Lift / gain: what do we capture by targeting the top X% ----
    order = np.argsort(-p_final)
    gain = np.cumsum(y_te.values[order]) / y_te.sum()
    pct = np.arange(1, len(y_te) + 1) / len(y_te)
    top20 = float(gain[int(0.2 * len(y_te)) - 1])
    summary["top20pct_captures_share_of_churners"] = top20

    # ---- Plots ----
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for p, lbl in [(p_base, "Baseline LR"), (p_final, f"Final ({best_name})")]:
        fpr, tpr, _ = roc_curve(y_te, p); ax[0].plot(fpr, tpr, label=lbl)
        pr, rc, _ = precision_recall_curve(y_te, p); ax[1].plot(rc, pr, label=lbl)
    ax[0].plot([0, 1], [0, 1], "k--", lw=.7); ax[0].set(title="ROC", xlabel="FPR", ylabel="TPR"); ax[0].legend()
    ax[1].set(title="Precision-Recall", xlabel="Recall", ylabel="Precision"); ax[1].legend()
    ax[2].plot(pct, gain, label="Model"); ax[2].plot([0, 1], [0, 1], "k--", label="Random")
    ax[2].axvline(.2, color="gray", ls=":")
    ax[2].set(title=f"Cumulative gain (top 20% -> {top20:.0%} of churners)",
              xlabel="% customers contacted", ylabel="% churners captured"); ax[2].legend()
    plt.tight_layout(); plt.savefig(REPORTS / "02_model_performance.png", dpi=130); plt.close()

    plt.figure(figsize=(6, 4))
    plt.plot(grid, profits)
    plt.axvline(best_t, color="r", ls="--", label=f"best threshold = {best_t:.2f}")
    plt.title("Expected retention profit vs. threshold (train OOF)"); plt.xlabel("threshold"); plt.ylabel("profit ($)"); plt.legend()
    plt.tight_layout(); plt.savefig(REPORTS / "03_threshold_profit.png", dpi=130); plt.close()

    # ---- Interpretability: permutation importance (+ SHAP if installed) ----
    pi = permutation_importance(tuned, X_te, y_te, scoring="average_precision", n_repeats=8, random_state=SEED, n_jobs=-1)
    imp = pd.Series(pi.importances_mean, index=X_te.columns).sort_values().tail(12)
    plt.figure(figsize=(7, 5)); imp.plot.barh(color="#4c72b0"); plt.title("Permutation importance (test PR-AUC drop)")
    plt.tight_layout(); plt.savefig(REPORTS / "04_feature_importance.png", dpi=130); plt.close()
    try:
        import shap
        Xt = tuned.named_steps["pre"].transform(X_te)
        names = tuned.named_steps["pre"].get_feature_names_out()
        expl = shap.Explainer(tuned.named_steps["m"], Xt, feature_names=names)
        shap.summary_plot(expl(Xt[:500]), show=False)
        plt.tight_layout(); plt.savefig(REPORTS / "05_shap_summary.png", dpi=130); plt.close()
    except Exception as e:
        print(f"(SHAP skipped: {type(e).__name__})")

    summary["top_drivers"] = imp.index[::-1][:5].tolist()
    json.dump(summary, open(REPORTS / "summary.json", "w"), indent=2, default=float)
    joblib.dump(final, ROOT / "churn_model.joblib")

    print("\n=== TEST SET RESULTS ===")
    print(f"Baseline LR : ROC-AUC {summary['baseline_roc_auc']:.3f}  PR-AUC {summary['baseline_pr_auc']:.3f}")
    print(f"Final model : ROC-AUC {summary['final_roc_auc']:.3f}  PR-AUC {summary['final_pr_auc']:.3f}")
    print(f"Threshold {best_t:.2f} -> precision {summary['precision']:.2f}, recall {summary['recall']:.2f}")
    print(f"Top 20% of customers captures {top20:.0%} of churners")
    print(f"Profit on test set: model ${profit_model:,.0f} | contact everyone ${profit_all:,.0f} | do nothing $0")
    print("Top drivers:", summary["top_drivers"])


if __name__ == "__main__":
    main()
