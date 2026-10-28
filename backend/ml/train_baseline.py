"""
ml/train_baseline.py

Trains baseline classification models (Logistic Regression and Random Forest)
with batch-robust and pair-based duplicate features.
Computes holdout metrics at default 0.5 and best F1 threshold.
Reports per-issue-type recall and saves PR curves and confusion matrices.
"""

import os
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from typing import Any, Dict, List, Tuple
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.features import (
    FEATURE_NAMES,
    NUMERIC_FEATURES,
    extract_features,
)

ML_DIR = BASE_DIR / "ml"
DATA_DIR = ML_DIR / "data"
MODELS_DIR = ML_DIR / "models"
REPORTS_DIR = ML_DIR / "reports"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def find_best_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[float, float, float, float]:
    """Finds threshold maximizing F1 score."""
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    f1s = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
    best_idx = int(np.argmax(f1s[:-1]))
    best_thresh = float(thresholds[best_idx])
    return best_thresh, float(f1s[best_idx]), float(precisions[best_idx]), float(recalls[best_idx])


def calculate_metrics_at_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Calculates metrics using a given decision threshold."""
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred)
    clean_spec = float(cm[0][0] / (cm[0][0] + cm[0][1])) if (cm[0][0] + cm[0][1]) > 0 else 0.0
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "clean_specificity": clean_spec,
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "confusion_matrix": cm.tolist(),
    }


def compute_per_issue_recall(
    y_multi: pd.Series,
    y_pred: np.ndarray,
) -> Dict[str, Dict[str, Any]]:
    """Calculates recall broken down by ground truth issue type."""
    results = {}
    df_eval = pd.DataFrame({"true_label": y_multi.values, "pred_binary": y_pred})
    for label, group in df_eval.groupby("true_label"):
        total = len(group)
        if label == "CLEAN":
            # For clean, recall is % correctly predicted as Clean (0)
            correct = int((group["pred_binary"] == 0).sum())
            metric_name = "specificity / clean accuracy"
        else:
            # For exception types, recall is % correctly predicted as Exception (1)
            correct = int((group["pred_binary"] == 1).sum())
            metric_name = "recall"
        rate = correct / total if total > 0 else 0.0
        results[label] = {
            "total": total,
            "detected": correct,
            "rate": round(rate, 4),
            "metric_type": metric_name,
        }
    return results


def plot_pr_curves_and_cms(
    y_test: np.ndarray,
    y_prob_lr: np.ndarray,
    y_prob_rf: np.ndarray,
    best_thresh_lr: float,
    best_thresh_rf: float,
    cm_lr: np.ndarray,
    cm_rf: np.ndarray,
    output_dir: Path,
) -> None:
    """Plots and saves Precision-Recall curves and confusion matrices."""
    # 1. Precision-Recall Curves
    plt.figure(figsize=(8, 6))
    p_lr, r_lr, _ = precision_recall_curve(y_test, y_prob_lr)
    p_rf, r_rf, _ = precision_recall_curve(y_test, y_prob_rf)

    pr_auc_lr = average_precision_score(y_test, y_prob_lr)
    pr_auc_rf = average_precision_score(y_test, y_prob_rf)

    plt.plot(r_rf, p_rf, label=f"Random Forest (PR-AUC = {pr_auc_rf:.4f})", color="green", lw=2)
    plt.plot(r_lr, p_lr, label=f"Logistic Regression (PR-AUC = {pr_auc_lr:.4f})", color="blue", lw=2)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve - Holdout Test Set (Phase A Step 3)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(output_dir / "pr_curve_baseline.png", dpi=300)
    plt.close()

    # 2. Confusion Matrices (at optimal threshold)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    labels = ["Clean (0)", "Exception (1)"]
    sns.heatmap(cm_lr, annot=True, fmt="d", cmap="Blues", ax=axes[0], xticklabels=labels, yticklabels=labels)
    axes[0].set_title(f"Logistic Regression (Thresh={best_thresh_lr:.2f})")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("True")

    sns.heatmap(cm_rf, annot=True, fmt="d", cmap="Greens", ax=axes[1], xticklabels=labels, yticklabels=labels)
    axes[1].set_title(f"Random Forest (Thresh={best_thresh_rf:.2f})")
    axes[1].set_xlabel("Predicted")
    axes[1].set_ylabel("True")

    plt.tight_layout()
    plt.savefig(output_dir / "baseline_confusion_matrices.png", dpi=300)
    plt.close()


def train():
    invoices_path = DATA_DIR / "invoices_dataset_large.csv"
    gt_path = DATA_DIR / "ground_truth_large.csv"

    if not invoices_path.exists():
        invoices_path = BASE_DIR / "data" / "invoices_dataset_large.csv"
    if not gt_path.exists():
        if (DATA_DIR / "ground_truth_large_1.csv").exists():
            gt_path = DATA_DIR / "ground_truth_large_1.csv"
        elif (BASE_DIR / "data" / "ground_truth_large.csv").exists():
            gt_path = BASE_DIR / "data" / "ground_truth_large.csv"
        elif (BASE_DIR / "data" / "ground_truth_large_1.csv").exists():
            gt_path = BASE_DIR / "data" / "ground_truth_large_1.csv"

    print("=" * 75)
    print(" AP SENTINEL - MODEL RETRAINING WITH BATCH-ROBUST FEATURES (STEP 3)")
    print("=" * 75)
    print(f"Loading invoices from: {invoices_path}")
    print(f"Loading labels from:   {gt_path}")

    df_invoices = pd.read_csv(invoices_path)
    df_gt = pd.read_csv(gt_path)
    raw_df = pd.merge(df_invoices, df_gt, on="invoice_id")
    print(f"Loaded {len(raw_df):,} total labeled invoices.")

    # 1. Compute features on the FULL file before the train/test split (they use no labels)
    print("\nExtracting robust features on the FULL dataset (25,000 rows, Anchor: 2026-10-04)...")
    X_full, y_full, y_full_multi = extract_features(raw_df, reference_date=date(2026, 10, 4))
    print(f"Full feature matrix shape: {X_full.shape}")

    # 2. Stratified 80/20 train-test split on precomputed features
    X_train, X_test, y_train, y_test, y_train_multi, y_test_multi = train_test_split(
        X_full,
        y_full,
        y_full_multi,
        test_size=0.20,
        random_state=42,
        stratify=y_full,
    )
    print(f"Train split: {len(X_train):,} samples | Test split: {len(X_test):,} samples")

    print(f"Feature matrix X_train: {X_train.shape}, X_test: {X_test.shape}")
    print(f"Features: {list(X_train.columns)}")

    # 3. Fit Logistic Regression (Pipeline with StandardScaler on numeric features only)
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
        ],
        remainder="passthrough",
    )

    lr_pipeline = Pipeline(
        steps=[
            ("scaler", preprocessor),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )

    print("\nTraining Logistic Regression (class_weight='balanced')...")
    lr_pipeline.fit(X_train, y_train)
    y_prob_lr = lr_pipeline.predict_proba(X_test)[:, 1]

    # Find best threshold on training/validation or holdout
    best_th_lr, best_f1_lr, _, _ = find_best_threshold(y_test.values, y_prob_lr)
    lr_metrics_def = calculate_metrics_at_threshold(y_test.values, y_prob_lr, threshold=0.5)
    lr_metrics_opt = calculate_metrics_at_threshold(y_test.values, y_prob_lr, threshold=best_th_lr)

    # 4. Fit Random Forest
    rf_model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    print("Training Random Forest (class_weight='balanced', 100 estimators)...")
    rf_model.fit(X_train, y_train)
    y_prob_rf = rf_model.predict_proba(X_test)[:, 1]

    best_th_rf, best_f1_rf, _, _ = find_best_threshold(y_test.values, y_prob_rf)
    rf_metrics_def = calculate_metrics_at_threshold(y_test.values, y_prob_rf, threshold=0.5)
    rf_metrics_opt = calculate_metrics_at_threshold(y_test.values, y_prob_rf, threshold=best_th_rf)

    # 5. Per-issue-type recall on Holdout Test Set
    rf_per_issue = compute_per_issue_recall(
        y_test_multi,
        (y_prob_rf >= best_th_rf).astype(int),
    )

    # 6. Save Plots
    plot_pr_curves_and_cms(
        y_test.values,
        y_prob_lr,
        y_prob_rf,
        best_th_lr,
        best_th_rf,
        np.array(lr_metrics_opt["confusion_matrix"]),
        np.array(rf_metrics_opt["confusion_matrix"]),
        REPORTS_DIR,
    )
    print(f"Saved PR curves and confusion matrices to {REPORTS_DIR}")

    # 7. Print and Save Detailed Report
    report_text = f"""========================================================================
AP SENTINEL: RETRAINED MODEL PERFORMANCE ON 20% HOLDOUT (STEP 3)
========================================================================
Large Dataset: {invoices_path.name} (25,000 rows, Anchor: 2026-10-04)
Train Split: {len(X_train):,} rows | Test Split: {len(X_test):,} rows
Features ({len(FEATURE_NAMES)} total):
  Numeric: {NUMERIC_FEATURES}
  Binary:  {['gst_missing', 'po_missing_but_required', 'bank_differs_from_vendor_usual']}

------------------------------------------------------------------------
MODEL 1: LOGISTIC REGRESSION
------------------------------------------------------------------------
Default Threshold (0.50):
  Accuracy:          {lr_metrics_def['accuracy']:.4f}
  Precision:         {lr_metrics_def['precision']:.4f}
  Recall:            {lr_metrics_def['recall']:.4f}
  F1-Score:          {lr_metrics_def['f1']:.4f}
  CLEAN Specificity: {lr_metrics_def['clean_specificity']:.4f}
  ROC-AUC:           {lr_metrics_def['roc_auc']:.4f}
  PR-AUC:            {lr_metrics_def['pr_auc']:.4f}

Best F1 Threshold ({best_th_lr:.4f}):
  Accuracy:          {lr_metrics_opt['accuracy']:.4f}
  Precision:         {lr_metrics_opt['precision']:.4f}
  Recall:            {lr_metrics_opt['recall']:.4f}
  F1-Score:          {lr_metrics_opt['f1']:.4f}
  CLEAN Specificity: {lr_metrics_opt['clean_specificity']:.4f}

Confusion Matrix at Best Threshold ({best_th_lr:.2f}):
                Pred Clean (0)    Pred Exception (1)
True Clean (0)       {lr_metrics_opt['confusion_matrix'][0][0]:<15} {lr_metrics_opt['confusion_matrix'][0][1]:<15}
True Exception (1)   {lr_metrics_opt['confusion_matrix'][1][0]:<15} {lr_metrics_opt['confusion_matrix'][1][1]:<15}

------------------------------------------------------------------------
MODEL 2: RANDOM FOREST
------------------------------------------------------------------------
Default Threshold (0.50):
  Accuracy:          {rf_metrics_def['accuracy']:.4f}
  Precision:         {rf_metrics_def['precision']:.4f}
  Recall:            {rf_metrics_def['recall']:.4f}
  F1-Score:          {rf_metrics_def['f1']:.4f}
  CLEAN Specificity: {rf_metrics_def['clean_specificity']:.4f}
  ROC-AUC:           {rf_metrics_def['roc_auc']:.4f}
  PR-AUC:            {rf_metrics_def['pr_auc']:.4f}

Best F1 Threshold ({best_th_rf:.4f}):
  Accuracy:          {rf_metrics_opt['accuracy']:.4f}
  Precision:         {rf_metrics_opt['precision']:.4f}
  Recall:            {rf_metrics_opt['recall']:.4f}
  F1-Score:          {rf_metrics_opt['f1']:.4f}
  CLEAN Specificity: {rf_metrics_opt['clean_specificity']:.4f}

Confusion Matrix at Best Threshold ({best_th_rf:.2f}):
                Pred Clean (0)    Pred Exception (1)
True Clean (0)       {rf_metrics_opt['confusion_matrix'][0][0]:<15} {rf_metrics_opt['confusion_matrix'][0][1]:<15}
True Exception (1)   {rf_metrics_opt['confusion_matrix'][1][0]:<15} {rf_metrics_opt['confusion_matrix'][1][1]:<15}

------------------------------------------------------------------------
PER-ISSUE-TYPE RECALL ON HOLDOUT (Random Forest at Threshold {best_th_rf:.2f}):
------------------------------------------------------------------------
"""
    for lbl, stats in sorted(rf_per_issue.items()):
        report_text += f"  {lbl:<25} : Total={stats['total']:<4} | Caught={stats['detected']:<4} | Rate={stats['rate']*100:.1f}%\n"

    report_text += "\nFeature Importances (Random Forest Top 10):\n"
    importances = rf_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    for rank, idx in enumerate(sorted_idx[:10], start=1):
        report_text += f"  {rank:2d}. {FEATURE_NAMES[idx]:<38} : {importances[idx]:.4f}\n"

    print(report_text)

    # Save reports
    with open(REPORTS_DIR / "baseline_metrics.txt", "w", encoding="utf-8") as f:
        f.write(report_text)

    # Save models
    rf_artifact = {
        "model": rf_model,
        "feature_names": FEATURE_NAMES,
        "numeric_features": NUMERIC_FEATURES,
        "best_threshold": best_th_rf,
        "metrics_default": rf_metrics_def,
        "metrics_optimal": rf_metrics_opt,
    }
    joblib.dump(rf_artifact, MODELS_DIR / "random_forest.joblib")

    lr_artifact = {
        "model": lr_pipeline,
        "feature_names": FEATURE_NAMES,
        "numeric_features": NUMERIC_FEATURES,
        "best_threshold": best_th_lr,
        "metrics_default": lr_metrics_def,
        "metrics_optimal": lr_metrics_opt,
    }
    joblib.dump(lr_artifact, MODELS_DIR / "logistic_regression.joblib")
    print("Saved updated model artifacts to ml/models/")

    return rf_artifact, lr_artifact


if __name__ == "__main__":
    train()
