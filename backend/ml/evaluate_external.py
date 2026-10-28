"""
ml/evaluate_external.py

Evaluates retrained supervised models on the separate 3,000-row final test set.
Uses batch-computed vendor bank accounts, fixed anchor 2026-10-03,
per-issue recall breakdown, and optimal F1 threshold evaluation.
"""

import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from typing import Any, Dict, Optional, Tuple
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
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

from ml.features import extract_features

ML_DIR = BASE_DIR / "ml"
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = ML_DIR / "models"
REPORTS_DIR = ML_DIR / "reports"


def calculate_metrics_at_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Calculates all key evaluation metrics at given decision threshold."""
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
            correct = int((group["pred_binary"] == 0).sum())
            metric_name = "specificity / clean accuracy"
        else:
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


def plot_external_eval_charts(
    y_true: np.ndarray,
    y_prob_lr: np.ndarray,
    y_prob_rf: np.ndarray,
    best_th_lr: float,
    best_th_rf: float,
    cm_lr: np.ndarray,
    cm_rf: np.ndarray,
    output_dir: Path,
) -> None:
    """Plots and saves PR curves and confusion matrices for external evaluation."""
    # 1. PR Curves
    plt.figure(figsize=(8, 6))
    p_lr, r_lr, _ = precision_recall_curve(y_true, y_prob_lr)
    p_rf, r_rf, _ = precision_recall_curve(y_true, y_prob_rf)

    pr_auc_lr = average_precision_score(y_true, y_prob_lr)
    pr_auc_rf = average_precision_score(y_true, y_prob_rf)

    plt.plot(r_rf, p_rf, label=f"Random Forest (PR-AUC = {pr_auc_rf:.4f})", color="green", lw=2)
    plt.plot(r_lr, p_lr, label=f"Logistic Regression (PR-AUC = {pr_auc_lr:.4f})", color="blue", lw=2)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve - External 3k Test Set")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(output_dir / "external_test_pr_curve.png", dpi=300)
    plt.close()

    # 2. Confusion Matrices
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    labels = ["Clean (0)", "Exception (1)"]
    sns.heatmap(cm_lr, annot=True, fmt="d", cmap="Blues", ax=axes[0], xticklabels=labels, yticklabels=labels)
    axes[0].set_title(f"Logistic Regression on 3k (Thresh={best_th_lr:.2f})")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("True")

    sns.heatmap(cm_rf, annot=True, fmt="d", cmap="Greens", ax=axes[1], xticklabels=labels, yticklabels=labels)
    axes[1].set_title(f"Random Forest on 3k (Thresh={best_th_rf:.2f})")
    axes[1].set_xlabel("Predicted")
    axes[1].set_ylabel("True")

    plt.tight_layout()
    plt.savefig(output_dir / "external_test_confusion_matrices.png", dpi=300)
    plt.close()


def evaluate():
    print("=" * 75)
    print(" AP SENTINEL - EXTERNAL 3,000-ROW EVALUATION WITH ROBUST FEATURES (STEP 3)")
    print("=" * 75)

    rf_model_path = MODELS_DIR / "random_forest.joblib"
    lr_model_path = MODELS_DIR / "logistic_regression.joblib"

    if not rf_model_path.exists():
        raise FileNotFoundError(f"Model file not found at {rf_model_path}. Run train_baseline.py first.")

    rf_artifact = joblib.load(rf_model_path)
    rf_model = rf_artifact["model"]
    best_th_rf = rf_artifact.get("best_threshold", 0.5)

    lr_artifact = joblib.load(lr_model_path) if lr_model_path.exists() else None
    lr_model = lr_artifact["model"] if lr_artifact else None
    best_th_lr = lr_artifact.get("best_threshold", 0.5) if lr_artifact else 0.5

    # Load separate 3,000-row test dataset and ground truth
    ext_invoices_path = DATA_DIR / "invoices_dataset.csv"
    ext_gt_path = DATA_DIR / "ground_truth.csv"
    if not ext_gt_path.exists():
        ext_gt_path = DATA_DIR / "ground_truth_1.csv"

    print(f"Loading external test invoices from: {ext_invoices_path}")
    print(f"Loading external ground truth from:   {ext_gt_path}")

    df_ext = pd.read_csv(ext_invoices_path)
    df_gt = pd.read_csv(ext_gt_path)
    merged_ext = pd.merge(df_ext, df_gt, on="invoice_id")
    print(f"Loaded {len(merged_ext):,} external records.")

    # Extract robust features (anchor date 2026-10-03 for 3k file, batch-computed usual banks)
    print("\nExtracting robust features for 3k external test set...")
    X_ext, y_ext, y_ext_multi = extract_features(
        merged_ext,
        vendor_usual_banks=None,  # Computed from 3k batch!
        reference_date=date(2026, 10, 3),  # 3k generation anchor!
    )
    print(f"External test feature matrix: {X_ext.shape}")

    # Predict Probabilities
    y_prob_rf = rf_model.predict_proba(X_ext)[:, 1]
    y_prob_lr = lr_model.predict_proba(X_ext)[:, 1] if lr_model else np.zeros(len(X_ext))

    # Calculate metrics at default 0.5 and optimal threshold
    rf_metrics_def = calculate_metrics_at_threshold(y_ext.values, y_prob_rf, threshold=0.5)
    rf_metrics_opt = calculate_metrics_at_threshold(y_ext.values, y_prob_rf, threshold=best_th_rf)

    lr_metrics_def = calculate_metrics_at_threshold(y_ext.values, y_prob_lr, threshold=0.5) if lr_model else None
    lr_metrics_opt = calculate_metrics_at_threshold(y_ext.values, y_prob_lr, threshold=best_th_lr) if lr_model else None

    # Per-issue recall
    rf_per_issue = compute_per_issue_recall(
        y_ext_multi,
        (y_prob_rf >= best_th_rf).astype(int),
    )

    # Save Plots
    plot_external_eval_charts(
        y_ext.values,
        y_prob_lr,
        y_prob_rf,
        best_th_lr,
        best_th_rf,
        np.array(lr_metrics_opt["confusion_matrix"]) if lr_metrics_opt else np.zeros((2, 2)),
        np.array(rf_metrics_opt["confusion_matrix"]),
        REPORTS_DIR,
    )
    print(f"Saved external PR curve and confusion matrices to {REPORTS_DIR}")

    # Print and Save Detailed Report
    report_text = f"""========================================================================
AP SENTINEL: EXTERNAL 3,000-ROW TEST SET EVALUATION REPORT (STEP 3)
========================================================================
Test Invoices Dataset: {ext_invoices_path.name} (3,000 rows, Anchor: 2026-10-03)
Test Ground Truth:     {ext_gt_path.name}
Feature Strategy:      Batch-computed vendor usual banks & pair duplicate features
"""
    if lr_metrics_def and lr_metrics_opt:
        report_text += f"""
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

Optimal Threshold ({best_th_lr:.4f}):
  Accuracy:          {lr_metrics_opt['accuracy']:.4f}
  Precision:         {lr_metrics_opt['precision']:.4f}
  Recall:            {lr_metrics_opt['recall']:.4f}
  F1-Score:          {lr_metrics_opt['f1']:.4f}
  CLEAN Specificity: {lr_metrics_opt['clean_specificity']:.4f}

Confusion Matrix at Optimal Threshold ({best_th_lr:.2f}):
                Pred Clean (0)    Pred Exception (1)
True Clean (0)       {lr_metrics_opt['confusion_matrix'][0][0]:<15} {lr_metrics_opt['confusion_matrix'][0][1]:<15}
True Exception (1)   {lr_metrics_opt['confusion_matrix'][1][0]:<15} {lr_metrics_opt['confusion_matrix'][1][1]:<15}
"""

    report_text += f"""
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

Optimal Threshold ({best_th_rf:.4f}):
  Accuracy:          {rf_metrics_opt['accuracy']:.4f}
  Precision:         {rf_metrics_opt['precision']:.4f}
  Recall:            {rf_metrics_opt['recall']:.4f}
  F1-Score:          {rf_metrics_opt['f1']:.4f}
  CLEAN Specificity: {rf_metrics_opt['clean_specificity']:.4f}

Confusion Matrix at Optimal Threshold ({best_th_rf:.2f}):
                Pred Clean (0)    Pred Exception (1)
True Clean (0)       {rf_metrics_opt['confusion_matrix'][0][0]:<15} {rf_metrics_opt['confusion_matrix'][0][1]:<15}
True Exception (1)   {rf_metrics_opt['confusion_matrix'][1][0]:<15} {rf_metrics_opt['confusion_matrix'][1][1]:<15}

------------------------------------------------------------------------
PER-ISSUE-TYPE RECALL ON EXTERNAL 3K SET (Random Forest at Threshold {best_th_rf:.2f}):
------------------------------------------------------------------------
"""
    for lbl, stats in sorted(rf_per_issue.items()):
        report_text += f"  {lbl:<25} : Total={stats['total']:<4} | Caught={stats['detected']:<4} | Rate={stats['rate']*100:.1f}%\n"

    print(report_text)

    with open(REPORTS_DIR / "external_test_metrics.txt", "w", encoding="utf-8") as f:
        f.write(report_text)

    return rf_metrics_opt, lr_metrics_opt


if __name__ == "__main__":
    evaluate()
