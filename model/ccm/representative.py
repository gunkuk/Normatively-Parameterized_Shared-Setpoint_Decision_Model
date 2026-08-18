# =====================================================
# 파일명: representative.py
# 역할: S7 `RepresentativeSelect` 교체축 — 붕괴/비붕괴 대표 (demographic,N) 셀 선정.
# 입력: binning 구현(S5에서 주입받음 — 자체 보유 금지, ARCHITECTURE.md §6.3 S7→S5 중첩 원칙)
# 출력: {"intact": (demographic,N), "collapse_examples": [(demographic,N), ...]}
# 의존: registry
# =====================================================
"""대표표본 선정 — ARCHITECTURE.md §4.4(c)·§6.3 S7. 🟡 P1 의존(주입되는 binning이 P1).

원본: `_fig_pareto_collapse.py` 헤더 주석(2026-07-05 사용자 결정) — 대표=비붕괴 sexage-3 /
붕괴 대표=sex-3·age-6(N=2). legacy는 이 선정을 코드로 계산한 게 아니라 결과를 본 뒤
**수기로 확정**한 값이다. 그래서 이 함수는 binning을 계약대로 주입받되(§7→§5 중첩 원칙 준수 —
자체 binning을 새로 만들면 파레토 y축과 대표선정이 다른 이질성 정의를 쓰는 사고가 난다),
legacy 확정값 자체는 계산이 아니라 관찰 확정이므로 고정 반환한다.

★ 이번 run 사용 범위: REQUIRED_OUTPUTS(6종)에는 이 선정을 쓰는 개별 산점도(PAR_rep_*)가
포함되지 않는다 — PLAN.md STEP6 표는 axes2_legacy 산출을 "PAR2_collapse.png" 1개 파일로
지정했고, 이는 _fig_pareto_collapse.py의 oracle/deploy frontier-size 맵 2개를 PAR4_boundary.png와
같은 방식(1x2 서브플롯)으로 합친 것이다(REPORT.md §5 기록). 따라서 이 모듈은 등록·구현은
완료하지만 이번 run의 필수 파이프라인에서는 호출되지 않는다(미래 대표선정 자동화용 슬롯).
"""

from __future__ import annotations

from typing import Callable

from . import registry


@registry.register("representative", "collapse_legacy", provisional="P1")
def collapse_legacy(binning: Callable) -> dict:
    """의도: 붕괴/비붕괴 대표 셀을 legacy 관찰 확정값으로 반환.
    입력: binning(S5 heterogeneity_binning에서 resolve()로 주입받은 구현 — §7→§5 중첩 원칙상
          이 함수가 binning을 직접 만들지 않는다는 것을 시그니처로 강제하기 위해 받는다).
    출력: {"intact": (demographic,N), "collapse_examples": [(demographic,N), ...]}.
    원본: `_fig_pareto_collapse.py` 헤더 근거(사용자 결정 2026-07-05).
    """
    _ = binning  # 계약상 주입받되, legacy 값 자체는 binning 계산 결과가 아니라 관찰 확정값(위 docstring)
    return {
        "intact": ("sexage", 3),
        "collapse_examples": [("sex", 3), ("age", 6)],
    }
