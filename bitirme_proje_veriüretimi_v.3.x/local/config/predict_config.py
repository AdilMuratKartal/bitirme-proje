"""
config/predict_config.py — Predict-mode sabitleri
Train verisinden (userid 1–1000) ayrı öğrenci kümesi üretir.
"""

PREDICT_N_STUDENTS = 1000
PREDICT_ID_OFFSET  = 10_000   # userid = 10001 – 11000
PREDICT_SEED       = 999
PREDICT_CUTOFF     = 8        # 8. haftada erken uyarı kesiti
PREDICT_OUT_DIR    = "output/predict"
