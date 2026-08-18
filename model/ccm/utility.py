# =====================================================
# 파일명: utility.py
# 역할: 계약 C(UtilityVector)의 효용함수 교체축. legacy 삼각형 clip 효용을 그대로 이식.
# 입력: setpoint(°C), desired 배열(°C), 관용폭 W
# 출력: 개인별 효용 배열 [0,1]
# 의존: numpy, registry
# =====================================================
"""효용함수 — ARCHITECTURE.md 계약 C. 🟡 P5(잠정) — settings.PROVISIONAL["P5"] 참조.

원본: `_exp_ccm_phase2_engine.py`의 `_u_pred_c`(결정용)·`util_true_c`(평가용) —
두 함수 모두 같은 삼각형 clip 공식을 쓴다(입력이 예측 desired냐 실측 desired냐만 다름).
그래서 이 모듈은 공식 하나만 이식하고, "무엇을 desired로 넣을지"는 호출자(runner)가 결정한다.
"""

from __future__ import annotations

import numpy as np

from . import registry

# --- 관용폭 W (2026-08-13 사용자 확정: 7.0 → 6.0) ------------------------
# ★ 현재 값의 근거 — 아래 ①~③ 환산은 그대로 두고 목표 PPD만 바꿨다.
#   W=6.0 → 6/3 = 2.00 scale unit → PPD = 76.8%.
#   "효용 0 = 약 3/4가 불만족"으로, W=7.0(PPD 89.3%)보다 관용폭을 좁게 잡은 것이다.
#   ⚠️ 이 값은 결과를 넓게 좌우한다. 좁힐수록 clip에 걸리는 사람이 늘어 maximin 계열이
#      불리해지고, 격자 동점(특히 threshold_cov)의 분포도 달라진다. 바꾸면 checkpoint가
#      자동 무효화되어 전 셀이 재계산된다(interpreter._code_fingerprint가 이 파일을 해싱).
# --- 이전 판정: 2026-08-05 사용자 확정 3.5 → 7.0 ------------------------
# ★ 근거 (이전 3.5는 legacy engine COMFORT_W_M9를 물려받은 값이라 근거가 없었다):
#   ① 열감각 척도의 온도 환산 — 문헌리뷰에 따르면 열감각투표(TSV, Thermal Sensation Vote)
#      1 scale unit은 중립온도 기준 **약 3°C**에 해당한다
#      (Individual difference in thermal comfort: A literature review, Building and
#       Environment 2018, 피인용 634).
#   ② 따라서 W=7°C는 7/3 = **2.33 scale unit** 어긋난 상태다.
#   ③ ASHRAE 55 / ISO 7730의 PMV-PPD 관계
#          PPD = 100 - 95*exp(-0.03353*PMV^4 - 0.2179*PMV^2)
#      에 PMV=2.33을 넣으면 **PPD = 89.3%** — 즉 약 90%가 심각한 불만족 상태다.
#   → "효용 0 = 열적으로 사실상 전원이 불만족(PPD≈90%)"이 되도록 W를 잡은 것이다.
#      W=3.5였을 때는 같은 환산으로 PMV=1.17 / PPD=33.6%에 불과해, 아직 2/3이 만족하는
#      지점을 '효용 0'으로 선언하는 셈이었다(과도하게 좁은 관용폭).
# ⚠️ 부수 효과(수치): 완전동점(임의 선택) 비율이 utilitarian 4.52%→0.60%,
#    equity의 Helly 붕괴(spread>2W)가 4.17%→0.00%로 줄어든다. 다만 이건 결과이지
#    W 선택의 근거가 아니다 — 근거는 위 ①~③이다.
W_DEFAULT_C = 6.0  # 🟡 P5: PPD≈77% 기준 (2026-08-13 확정. 구 7.0=PPD 89.3%, 구 3.5=legacy)

# --- 효용 정의역 바닥 (2026-08-04 사용자 지시로 rules/social → 여기로 이동) ----
# ★ 왜 효용 쪽에 있어야 하나 — Atkinson(1970) 각주 2는 정의역을 **0 < y ≤ ŷ** 로 못박는다.
#   즉 Atkinson 사회후생은 "효용이 0인 사람"을 애초에 상정하지 않는다. 그런데 우리 삼각형
#   clip은 |Δ|>W인 사람을 정확히 0으로 만들어 그 정의역을 깬다. 그래서 ε>=1 계열
#   (기하평균·조화평균)과 Nash의 log가 0으로 붕괴한다.
#   → 바닥은 "규칙마다 붙이는 수치 반창고"가 아니라 **효용의 정의역 자체**의 문제다.
#   이전에는 social.atkinson(클램프형)과 rules.rule_nash(가산형)가 서로 다른 바닥을
#   각자 적용해, utilitarian≠atkinson(ε=0)(0.425%)·nash≠atkinson(ε=1)(0.450%)이 됐다.
#   여기 한 곳에서 (0,1] 정의역을 보장하면 그 불일치가 원천 제거된다.
# ⚠️ 이 값은 결과를 좌우하는 자유 파라미터다(spread>2W 구간의 순위를 이것만이 정한다).
#   settings.PROVISIONAL에 P8로 등록하고 민감도를 봐야 한다 — 아래 TODO 참조.
UTILITY_FLOOR = 1e-3  # 🟡 P8(등록 대기): 구 social.FLOOR와 동일 값


@registry.register("utility", "triangular_clip", provisional="P5")
def triangular_clip(
    setpoint_c: float, desired: np.ndarray, W: float = W_DEFAULT_C
) -> np.ndarray:
    """의도: setpoint와 desired의 정렬도를 (0,1] 효용으로. |차이|=0이면 1, |차이|>=W면 바닥값.
    입력: setpoint_c(그룹 공유 설정온도), desired(개인별 원하는 온도 배열), W(관용폭 °C).
    출력: 효용 배열(desired과 같은 길이), 전부 [UTILITY_FLOOR, 1].
    원본: engine `_u_pred_c` / `util_true_c` — 삼각형 수식·상수(W=3.5) 불변.

    ★ 2026-08-04 변경: 하한을 0 → UTILITY_FLOOR로 올렸다. 수식은 그대로이고 바닥만
      Atkinson 정의역(0 < y)에 맞춘다. 이제 모든 규칙·평가축이 같은 정의역을 본다.
    """
    return np.clip(
        1 - np.abs(np.asarray(desired, float) - setpoint_c) / W, UTILITY_FLOOR, 1
    )


# ★ triangular_linear(clip-off 민감도 판본)는 2026-08-05 사용자 확정으로 폐기했다.
#   단순 experiment였고 정본 후보가 아니었으며, W를 7.0으로 올리며 겨냥하던 포화 문제가
#   해소됐다. 코드는 experiment/ccm/_internal/legacy/triangular_linear.py 에 보존한다
#   (registry 등록 없음 = 실행 경로에서 완전히 제외). 산출물은 variant_linear/ 에 그대로 남아 있다.
