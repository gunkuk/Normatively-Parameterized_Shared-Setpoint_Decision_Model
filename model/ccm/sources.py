# =====================================================
# 파일명: sources.py
# 역할: 계약 A(PersonSet)의 `decision_source` 교체축 — desired 값을 어디서 채울지.
#       pcm_prediction(✅ 실행가능) / ground_truth(🔒 legacy·gate, 실행경로 금지).
# 입력: adapter.py가 만든 d_valid(행=세션, 열에 actual·prediction 포함)
# 출력: desired 배열 (d_valid과 같은 행 순서, 길이 n)
# 의존: registry
# =====================================================
"""decision_source registry — ARCHITECTURE.md 계약 A + §3 gate 그대로.

★ ground_truth는 재활용 참조용으로만 여기 남긴다. registry.resolve()가
allow_legacy=True 없이는 즉시 RuntimeError를 던지므로, 실행 경로에서 실수로
섞여 들어갈 수 없다(코드 레벨 강제).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import registry


@registry.register("decision_source", "pcm_prediction")
def pcm_prediction_source(d_valid: pd.DataFrame) -> np.ndarray:
    """의도: "실제 배포 시" 결정입력 — PCM(TabPFN) OOF 예측치.
    입력: d_valid (MODEL_OOF.tsv mean cell에서 온 'prediction' 열 포함).
    출력: desired 배열(°C), d_valid과 같은 행 순서.
    """
    return pd.to_numeric(d_valid["prediction"], errors="coerce").to_numpy(float)


@registry.register("decision_source", "ground_truth", legacy=True)
def ground_truth_source(d_valid: pd.DataFrame) -> np.ndarray:
    """🔒 LEGACY·GATED — 재활용 참조 전용. 실행 경로에서 resolve()가 즉시 예외를 던진다.
    의도: "PCM이 완벽했다면"(oracle) — 그 세션의 실측 P9_filled를 직접 desired로 씀.
    입력/출력: pcm_prediction_source와 동일 형태, 'actual' 열 사용.
    ⚠️ 이 함수를 실행 경로에서 부르는 것은 '설문 없이 예측'이라는 프로젝트 목적에 반한다
    (ARCHITECTURE.md §3 계약A 참조). 코드 참조·문서화 목적으로만 존재.
    """
    return pd.to_numeric(d_valid["actual"], errors="coerce").to_numpy(float)
