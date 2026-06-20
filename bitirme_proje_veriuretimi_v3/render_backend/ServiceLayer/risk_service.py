import os
import json
import datetime
import logging
import numpy as np
import pandas as pd
import onnxruntime as ort
from sqlalchemy import text
from Moodle_DAO.moodle_dao_schema import MoodleDAO

logger = logging.getLogger(__name__)

_SESSION = None
_FEATURES = None

def _get_onnx_session_and_features():
    global _SESSION, _FEATURES
    if _SESSION is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, "saved_models", "student_success_model.onnx")
        meta_path = os.path.join(base_dir, "saved_models", "student_success_meta.json")
        
        _SESSION = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        _FEATURES = meta["features"]
    return _SESSION, _FEATURES

def calculate_and_save_risk(userid: int, dao: MoodleDAO) -> dict | None:
    features_df = dao.get_dash_features(userid)
    if features_df.empty:
        return None
        
    sess, features_names = _get_onnx_session_and_features()
    input_name = sess.get_inputs()[0].name
    
    # Run batch prediction for all courses
    X = []
    for _, row in features_df.iterrows():
        row_dict = dict(row)
        feat_vector = []
        for feat in features_names:
            val = row_dict.get(feat, 0.0)
            if val is None or pd.isna(val):
                val = 0.0
            feat_vector.append(float(val))
        X.append(feat_vector)
        
    X_arr = np.array(X, dtype=np.float32)
    out = sess.run(None, {input_name: X_arr})
    # out[1] contains probabilities of shape (N, 2)
    pass_probabilities = out[1][:, 1]
    
    # Aggregation
    mean_pass_prob = float(np.mean(pass_probabilities))
    risk_score = round((1.0 - mean_pass_prob) * 100, 1)
    
    def _risk_level(score):
        if score < 40: return "Düşük"
        if score <= 70: return "Orta"
        return "Yüksek"
        
    risk_level = _risk_level(risk_score)
    will_pass = 1 if mean_pass_prob >= 0.5 else 0
    computed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    risk_data = {
        "user_id": userid,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "predicted_grade": None,
        "pass_probability": round(mean_pass_prob, 4),
        "will_pass": will_pass,
        "computed_at": computed_at
    }
    
    dao.upsert_dash_risk(risk_data)
    return risk_data

def get_or_calculate_user_risk(userid: int, dao: MoodleDAO) -> dict | None:
    """
    Kullanıcının risk verisini döner. 
    Veri yoksa veya 7 günden eski ise (stale) arka planda on-demand hesaplayıp kaydeder.
    """
    risk = dao.get_dash_risk(userid)
    
    is_stale = False
    if risk:
        computed_at_str = risk.get("computed_at")
        if computed_at_str:
            try:
                computed_at_dt = datetime.datetime.fromisoformat(computed_at_str)
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                age_days = (now_dt - computed_at_dt).days
                if age_days >= 7:
                    is_stale = True
            except Exception as e:
                is_stale = True
        else:
            is_stale = True
            
    if not risk or is_stale:
        try:
            logger.info(f"Risk calculation triggered for user {userid} (missing or stale).")
            new_risk = calculate_and_save_risk(userid, dao)
            if new_risk:
                risk = new_risk
        except Exception as e:
            logger.error(f"On-demand risk calculation failed for user {userid}: {e}")
            
    return risk

def recalculate_all_users_risk(dao: MoodleDAO) -> int:
    """
    Tüm kullanıcılar için risk skorlarını tek bir toplu işlemde (batch) hesaplar ve veritabanına yazar.
    1 SELECT + 1 DELETE + 1 INSERT ile son derece hızlı çalışır.
    """
    session = dao._session()
    try:
        df = pd.read_sql(text("SELECT * FROM dash_features"), session.bind)
    finally:
        session.close()
        
    if df.empty:
        return 0
        
    sess, features_names = _get_onnx_session_and_features()
    input_name = sess.get_inputs()[0].name
    
    # 2. Extract features matrix
    X = []
    for _, row in df.iterrows():
        row_dict = dict(row)
        feat_vector = []
        for feat in features_names:
            val = row_dict.get(feat, 0.0)
            if val is None or pd.isna(val):
                val = 0.0
            feat_vector.append(float(val))
        X.append(feat_vector)
        
    X_arr = np.array(X, dtype=np.float32)
    out = sess.run(None, {input_name: X_arr})
    df["pass_prob"] = out[1][:, 1].astype(float)
    
    # 3. Aggregate by userid
    agg = df.groupby("userid")["pass_prob"].mean().reset_index()
    agg["pass_probability"] = agg["pass_prob"].round(4)
    agg["risk_score"]       = ((1.0 - agg["pass_prob"]) * 100).round(1)
    
    def _risk_level(score):
        if score < 40:  return "Düşük"
        if score <= 70: return "Orta"
        return "Yüksek"
        
    agg["risk_level"] = agg["risk_score"].map(_risk_level)
    agg["will_pass"] = (agg["pass_prob"] >= 0.5).astype(int)
    agg["predicted_grade"] = None
    agg["computed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 4. Save to database in a single transaction
    records = agg.rename(columns={"userid": "user_id"}).to_dict(orient="records")
    
    with dao.transaction() as write_session:
        write_session.execute(text("DELETE FROM dash_risk"))
        write_session.execute(
            text("INSERT INTO dash_risk (user_id, risk_score, risk_level, predicted_grade, pass_probability, will_pass, computed_at) "
                 "VALUES (:user_id, :risk_score, :risk_level, :predicted_grade, :pass_probability, :will_pass, :computed_at)"),
            records
        )
        
    return len(records)
