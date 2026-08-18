#!/usr/bin/env python
# =====================================================
# 파일명: run_ccm.py
# 역할: 이 저장소의 단일 진입점. DSF 확정 → CCM 실행 → 결과표 기록을 한 번에 돌린다.
# 입력: data/ 의 입력 4종 (MODEL_OOF.tsv, cohort join 동결본, P9 원값 동결본, EnergyPlus LUT)
# 출력: outputs/results/ 아래 csv·tsv.gz·PROVENANCE.json (README §4 참조)
# 의존: numpy, pandas, matplotlib (model/ccm, model/EnergyPlus)
# =====================================================
"""CCM 재현 러너.

사용법
    python run_ccm.py --smoke   # 그룹크기 2·6 × annual 만 (약 20초) — 환경·입력 점검
    python run_ccm.py --full    # N=1~10 × 계절 5 = 50셀 (수 분) — 논문 산출물

무엇을 하는가
    1) DSF: 피험자 62명 각각의 전체 20개 P9_filled에서 최빈값을 desired setpoint로 확정한다
       (model/ccm/desired_at23.py).
    2) CCM: 각 (그룹크기 × 계절) 셀에서 그룹을 R회 무작위 구성하고, 분배 규칙별로 공유
       setpoint를 정한 뒤 4축(효율·공정·형평·에너지)을 잰다(model/ccm/interpreter.py).

셀별 seed와 동점 seed가 결정적으로 유도되므로 재실행해도 같은 결과가 나온다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description="DSF + CCM 재현 실행 (단일 진입점)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="2셀만 실행 (약 20초)")
    g.add_argument("--full", action="store_true", help="전체 50셀 실행")
    a = ap.parse_args()

    # model/ 을 import 경로에 넣는다 — ccm·EnergyPlus가 그 아래 형제 패키지다.
    sys.path.insert(0, str(ROOT / "model"))

    from ccm import interpreter, settings, visual_registry

    visual_registry.enabled_sources()  # 결정입력 소스 gate (oracle 전용인지 확인)

    if a.smoke:
        smoke = settings.SMOKE
        res = interpreter.run(
            group_sizes=smoke["group_sizes"],
            seasons=smoke["seasons"],
            demographics=settings.DEMOGRAPHICS,
            rule_filter=smoke["rules"],
            R=smoke["R"],
        )
        interpreter._write_outputs(res, tag="smoke_p9filled")
        print("[smoke] 통과 — 입력·환경 정상. 이제 --full 을 돌리면 된다.")
        return 0

    res = interpreter.run(
        group_sizes=settings.GROUP_SIZES,
        seasons=settings.SEASONS,
        demographics=settings.DEMOGRAPHICS,
        rule_filter=None,
        R=settings.PROVISIONAL["P2"]["값"]["R_full"],
    )
    interpreter._write_outputs(res, tag="full_p9filled")
    print("\n[완료] outputs/results/ 를 보면 된다 (스키마: outputs/RESULTS_SCHEMA.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
