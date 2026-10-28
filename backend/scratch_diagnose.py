import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

import joblib
import numpy as np
import pandas as pd
from datetime import date
from sklearn.model_selection import train_test_split
from ml.features import extract_features, FEATURE_NAMES, NUMERIC_FEATURES

# Load models and artifacts
rf_art = joblib.load('ml/models/random_forest.joblib')
rf = rf_art['model']
lr_art = joblib.load('ml/models/logistic_regression.joblib')
lr = lr_art['model']
best_th_rf = rf_art.get('best_threshold', 0.5)

print('--- DIAGNOSTIC a ---')
print(f'Random Forest threshold stored in artifact: {best_th_rf:.4f}')

# Load data
df_large = pd.read_csv('ml/data/invoices_dataset_large.csv')
gt_large = pd.read_csv('ml/data/ground_truth_large.csv')
merged_large = pd.merge(df_large, gt_large, on='invoice_id')

raw_train, raw_test = train_test_split(
    merged_large,
    test_size=0.20,
    random_state=42,
    stratify=(merged_large['true_label'] != 'CLEAN').astype(int)
)

X_train, y_train, y_train_multi = extract_features(raw_train, reference_date=date(2026, 10, 4))
X_test, y_test, y_test_multi = extract_features(raw_test, reference_date=date(2026, 10, 4))

df_ext = pd.read_csv('data/invoices_dataset.csv')
gt_ext = pd.read_csv('data/ground_truth.csv')
merged_ext = pd.merge(df_ext, gt_ext, on='invoice_id')
X_ext, y_ext, y_ext_multi = extract_features(merged_ext, reference_date=date(2026, 10, 3))

print('\n--- DIAGNOSTIC c ---')
print(f'X_train columns == X_ext columns: {list(X_train.columns) == list(X_ext.columns)}')
print(f'Column count: {len(X_train.columns)} vs {len(X_ext.columns)}')
print(f'X_ext nulls: {X_ext.isna().sum().sum()}, X_train nulls: {X_train.isna().sum().sum()}')

print('\n--- DIAGNOSTIC b (CLEAN ROWS ONLY) ---')
clean_train = X_train[y_train_multi == 'CLEAN']
clean_ext = X_ext[y_ext_multi == 'CLEAN']

stats = []
for col in X_train.columns:
    m_tr = clean_train[col].mean()
    med_tr = clean_train[col].median()
    m_ext = clean_ext[col].mean()
    med_ext = clean_ext[col].median()
    
    # Relative difference: |m_tr - m_ext| / max(|m_tr|, 1e-4)
    rel_diff = abs(m_tr - m_ext) / max(abs(m_tr), 1e-4)
    stats.append({
        'Feature': col,
        'Train Mean': m_tr,
        'Train Median': med_tr,
        'Ext Mean': m_ext,
        'Ext Median': med_ext,
        'Abs Diff': abs(m_tr - m_ext),
        'Rel Diff': rel_diff
    })

df_stats = pd.DataFrame(stats).sort_values('Rel Diff', ascending=False)
for _, r in df_stats.iterrows():
    print(f"{r['Feature']:<38} | Train: mean={r['Train Mean']:8.4f}, med={r['Train Median']:8.4f} | Ext: mean={r['Ext Mean']:8.4f}, med={r['Ext Median']:8.4f} | RelDiff={r['Rel Diff']:8.2f}")

print('\n--- DIAGNOSTIC d (PREDICTED PROBABILITIES ON CLEAN ROWS) ---')
probs_holdout_clean = rf.predict_proba(X_test[y_test_multi == 'CLEAN'])[:, 1]
probs_ext_clean = rf.predict_proba(X_ext[y_ext_multi == 'CLEAN'])[:, 1]

percentiles = [0, 10, 25, 50, 75, 90, 95, 99, 100]
print(f"{'Percentile':<12} | {'Holdout Clean Probs':<20} | {'External Clean Probs':<20}")
print('-'*60)
for p in percentiles:
    val_hold = np.percentile(probs_holdout_clean, p)
    val_ext = np.percentile(probs_ext_clean, p)
    print(f"{p:<12} | {val_hold:<20.4f} | {val_ext:<20.4f}")
