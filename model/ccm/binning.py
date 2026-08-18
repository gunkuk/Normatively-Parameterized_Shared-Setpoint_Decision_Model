# =====================================================
# 파일명: binning.py
# 역할: S5 `HeterogeneityBinning` 교체축 — 그룹 내 desired 분산(이질성)을 이산구간으로 나누는 방식.
# 입력: 그룹별 desired-SD 배열
# 출력: (bin_of 배열[0/1/2], 경계 (q1,q2))
# 의존: numpy, registry
# =====================================================
"""이질성 binning — ARCHITECTURE.md §4.4(b)·§6.3 S5. 🟡 P1(잠정) — settings.PROVISIONAL["P1"].

원본: `_fig_ccm_heterogeneity.py`의 tertile 로직(45-49행) bit-identical 이식.

★ 이번 run에서의 실제 사용 범위: PLAN.md STEP6이 요구하는 필수 figure(PAR4_*, PAR2_collapse)는
legacy `_fig_pareto4d.py`/`_fig_pareto_collapse.py`의 y축(=demographic 구성 sex/age/sexage)을
"연결만" 하도록 지시돼 있고, 이 두 스크립트는 SD-tertile이 아니라 demographic 구성을 이질성 축으로
쓴다. 즉 이 binning.py는 STEP1 "이식" 목록에 있어 등록·구현은 완료하지만, 이번 run의 필수 산출물
파이프라인에서는 호출되지 않는다(향후 이질성 축을 demographic→SD-tertile로 교체할 때 쓸 슬롯).
REPORT.md §5(PROVISIONAL 경고)에 이 사실을 기록한다.
"""

from __future__ import annotations

import numpy as np

from . import registry


@registry.register("heterogeneity_binning", "tertile_sd", provisional="P1")
def tertile_sd(group_sd: np.ndarray) -> tuple[np.ndarray, tuple[float, float]]:
    """의도: 그룹별 desired-SD를 3분위(동질/중간/이질)로 이산화.
    입력: group_sd(그룹마다 desired 값의 표본표준편차, 길이=그룹 수).
    출력: (bin_of[0=동질,1=중간,2=이질] 배열, (q1,q2) 경계 — 표본 의존적).
    원본: `_fig_ccm_heterogeneity.py:48` bit-identical(quantile [1/3,2/3]).
    """
    group_sd = np.asarray(group_sd, float)
    q1, q2 = np.quantile(group_sd, [1 / 3, 2 / 3])
    bin_of = np.where(group_sd <= q1, 0, np.where(group_sd <= q2, 1, 2))
    return bin_of, (float(q1), float(q2))


# S6.3 슬롯 예약(§6.3 ARCHITECTURE): "continuous" | "fixed_interval" — 구현은 결정 후.
# 미확정(🔶)에 기본값을 정하지 않는다(governance §5-4) — 그래서 여기 등록하지 않고 이름만 문서화한다.
RESERVED_UNIMPLEMENTED = ("continuous", "fixed_interval")
