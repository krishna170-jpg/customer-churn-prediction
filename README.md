# Customer Churn Prediction

Predict which telecom customers are likely to leave, then pick *who to contact* using a cost-benefit model rather than a default 0.5 cutoff.

## Quick start
```bash
pip install -r requirements.txt
# Optional: download the Kaggle "Telco Customer Churn" CSV into data/telco_churn.csv
cd src && python train.py          # trains, evaluates, writes reports/ and churn_model.joblib
python predict.py ../data/telco_churn.csv   # score customers
streamlit run ../app.py            # optional demo (pip install streamlit)
```
With no CSV present, the code generates a synthetic dataset with the same schema, so everything runs out of the box. **For your portfolio, use the real dataset and replace the numbers below with your own results.**

## Pipeline
1. **EDA** – class balance, churn by contract and tenure (`reports/01_eda.png`)
2. **Features** – average monthly spend, charge-vs-average, tenure buckets, new-customer flag
3. **Leakage control** – test set split off first; scaling/encoding live inside the sklearn `Pipeline`, so they are fit only on training folds
4. **Models** – Logistic Regression baseline, Random Forest, Gradient Boosting (XGBoost if installed), compared with 5-fold stratified CV on ROC-AUC and PR-AUC
5. **Imbalance** – class weights plus probability calibration and threshold tuning (instead of SMOTE, which tends to distort probabilities)
6. **Tuning** – randomized search on the best tree model, scored on PR-AUC
7. **Business threshold** – chosen on out-of-fold training predictions by maximizing expected profit: `saved churners × value − contacts × offer cost`
8. **Interpretation** – permutation importance (and SHAP if installed)

## Business assumptions (edit in `train.py`)
Customer value $500, offer cost $50, save rate 30%.

## Results on the bundled synthetic data (7,000 customers, ~22% churn)
| | ROC-AUC | PR-AUC |
|---|---|---|
| Logistic Regression baseline | 0.850 | 0.683 |
| Tuned Random Forest (calibrated) | 0.831 | 0.631 |

- Targeting the top 20% of customers captures about 53% of churners.
- At the profit-optimal threshold, the model nets about $9.4k on 1,400 test customers, versus about -$24k for contacting everyone and $0 for doing nothing.
- Top drivers: contract type, internet service, tenure, payment method, monthly charges.

**Honest takeaway:** the logistic baseline matched or beat the tree models here. That is a legitimate result: on mostly-linear, noisy tabular data, a simple model is hard to beat, and it is easier to explain. Report it that way rather than forcing a fancier model to "win." On the real Telco data, expect ROC-AUC around 0.84.

## Limitations and next steps
- Churn labels are a snapshot, not time-aware; a production version needs a prediction window and time-based validation.
- Save rate is an assumption; an A/B test of the retention offer would give the real number (and enable uplift modeling).
- Add monitoring for drift and recalibration.
