# =====================================================
# 파일명: reduce.py
# 역할: S6 `AxisReduce` 교체축 — 계약 D(4축 SocialValue)를 몇 축으로 보여줄지.
#       axes4=4축 그대로, axes2_legacy=효율×형평(CVaR10%) 2축만.
# 입력: SocialValue 결과 DataFrame(efficiency/fairness/equity_cvar10/energy_MWh 열 포함)
# 출력: 같은 DataFrame(축소된 열 집합) — id열(N/demographic/season/rule/eps)은 항상 보존
# 의존: pandas, registry
# =====================================================
"""축 축소 — ARCHITECTURE.md §4.4(a)·§6.3 S6. settings.AXIS_REDUCE_OUTPUTS=("axes4","axes2_legacy")
둘 다 항상 출력(2026-07-23 사용자 지시) — 그래서 두 함수 모두 provisional 태그 없이 등록한다
(P1~P6 어디에도 "축 개수" 항목은 없다 — settings.py PROVISIONAL 대장에 새 ID를 만들지 않았다.
새 ID 추가는 §6.5 관리규약상 ARCHITECTURE.md §6.2부터 고쳐야 하는 문서측 결정이라 이번 스코프 밖).
"""

from __future__ import annotations

import pandas as pd

from . import registry

ID_COLS = ["N", "demographic", "season", "rule", "eps"]


@registry.register("axis_reduce", "axes4")
def axes4(sv: pd.DataFrame) -> pd.DataFrame:
    """의도: 4축(효율·형평·공평·에너지) 전부 유지 — PAR4_* 3부작 입력.
    입력/출력: SocialValue 테이블(변경 없음, 그대로 반환) — 축소가 아니라 '유지'가 이 구현의 정의."""
    return sv


@registry.register("axis_reduce", "axes2_legacy")
def axes2_legacy(sv: pd.DataFrame) -> pd.DataFrame:
    """의도: 효율×형평(CVaR10%) 2축만 — PAR2_collapse 입력(_fig_pareto_collapse.py와 동일 축 선택).
    입력: SocialValue 테이블. 출력: id열 + {efficiency,equity_cvar10}_{oracle,deploy} 열만."""
    keep = [
        c
        for c in sv.columns
        if c in ID_COLS or c.startswith(("efficiency_", "equity_cvar10_"))
    ]
    return sv[keep]
