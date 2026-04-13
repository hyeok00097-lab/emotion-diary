from emotions import KOELECTRA_LABEL_MAP

print("KoELECTRA 감정 분류 모델 로딩 중...")
try:
    from transformers import pipeline as hf_pipeline
    _emotion_pipeline = hf_pipeline(
        "text-classification",
        model="LimYeri/HowRU-KoELECTRA-Emotion-Classifier",
        tokenizer="LimYeri/HowRU-KoELECTRA-Emotion-Classifier",
        top_k=None,
    )
    print("✓ KoELECTRA 모델 로드 완료")
except Exception as e:
    _emotion_pipeline = None
    print(f"✗ KoELECTRA 모델 로드 실패 → LLM 전용 모드: {e}")


def koelectra_classify(text: str) -> tuple[str, float, dict]:
    """KoELECTRA로 감정 분류. 모델 없으면 neutral/0.0/{} 반환."""
    if _emotion_pipeline is None:
        return "neutral", 0.0, {}
    try:
        raw        = _emotion_pipeline(text[:512])[0]
        sorted_raw = sorted(raw, key=lambda x: x["score"], reverse=True)
        top1_label = sorted_raw[0]["label"]
        top1_score = sorted_raw[0]["score"]
        dominant   = KOELECTRA_LABEL_MAP.get(top1_label, "neutral")
        total      = sum(r["score"] for r in sorted_raw)
        all_scores = {
            KOELECTRA_LABEL_MAP[r["label"]]: round(r["score"] / total * 100, 1)
            for r in sorted_raw if r["label"] in KOELECTRA_LABEL_MAP
        }
        print(f"[KoELECTRA] top1={top1_label}({top1_score:.2f}) → {dominant}")
        return dominant, top1_score, all_scores
    except Exception as e:
        print(f"[KoELECTRA] 추론 오류: {e}")
        return "neutral", 0.0, {}
