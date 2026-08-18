# =====================================================
# 파일명: desired_at23.py
# 역할: 피험자 1인당 desired setpoint 1개를 확정한다 — 전체 20개 P9_filled의
#       최빈값(mode). oracle DSF가 반환하는 값의 정본.
# 입력: adapter.PersonMaterial.d_valid(1,240행) + data.xlsx SUR 시트(P9 원값=결측 판정용)
# 출력: DesiredAT23(per_subject Series, pool DataFrame, resolution DataFrame, meta dict)
# 의존: pandas, numpy, settings
# =====================================================
"""전체 반복응답 기반 개인별 desired setpoint — oracle DSF 정본(2026-08-13 사용자 확정).

각 피험자의 4개 세션 × 5개 설문시점, 즉 전체 20개 `P9_filled`에서 가장 자주 보고된
온도를 개인 desired setpoint로 정의한다. 이 정의는 특정 공기온도 조건으로 제한하지 않고
반복 측정 전반에서 가장 일관되게 나타난 응답을 대표값으로 사용한다.

★ 최빈값 동점 해소 — 다음 순서로 고정
  1) 전체 20관측의 최빈값. 유일하면 확정(62명 중 57명).
  2) 공동 최빈값이면 전체 20관측 평균에 가장 가까운 후보를 선택(5명 중 3명 해소).
  3) 평균과의 거리도 같은 잔여 2명은 사용자 확정 canonical override를 적용:
     피험자 19 = 24°C, 피험자 83 = 22°C.

P9가 N/A인 행을 같은 시점의 PT로 보완한 `P9_filled` 20개를 모두 빈도 계산에 포함한다.
원래 P9와 PT 대체 여부는 audit 열로 보존하지만 동점 해소에서 관측을 제외하지 않는다.

파일명 `desired_at23.py`는 기존 import 호환성을 위해 유지한다. 현재 정의는 AT≈23°C에
한정되지 않으며, 산출물과 provenance의 canonical 명칭은 `desired_frequency_*`와
`subject_frequency`다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_POOL_PER_SUBJECT = 20
CANONICAL_TIE_OVERRIDES = {19: 24.0, 83: 22.0}


@dataclass(frozen=True)
class DesiredAT23:
    """의도: oracle desired 확정 결과와 그 근거를 한 묶음으로 들고 다닌다.
    per_subject: index=no, value=desired setpoint(°C). 길이 = 피험자 수.
    pool: 확정에 쓰인 관측 전수(피험자×20행) — imputed 플래그 포함.
    resolution: 피험자별 확정 경로(어느 단계에서 정해졌나, 동점 후보가 무엇이었나).
    meta: 재현·감사용 요약 수치.
    """

    per_subject: pd.Series
    pool: pd.DataFrame
    resolution: pd.DataFrame
    meta: dict


def _p9_raw_by_row_id(data_xlsx) -> pd.Series:
    """의도: P9 **원값**을 row_id로 조회 가능하게 만든다 (결측=PT로 대체된 행 판정용).
    입력: data.xlsx 경로(동결본이 없을 때만 사용하는 원본 경로).
    출력: index=row_id, value=P9 원값(결측은 NaN)인 Series.

    row_id는 SUR 시트의 0-based 행 위치와 같다(cohort 빌더가 그렇게 부여했고 이 함수는
    그 규약에 의존한다 — 호출부가 actual 일치 검사로 매 실행 검증한다).

    ★ 2026-08-05: 같은 폴더의 동결본 `ccm_p9_raw_by_row_id.tsv`가 있으면 그것을 읽는다.
      data.xlsx는 5.2MB이고 ECG·MBTI 등 파이프라인 금지 컬럼을 포함하는데, 여기서 실제로
      필요한 건 P9 한 열의 결측 여부뿐이다. 동결로 핸드오프 패키지가 원본 엑셀 없이
      돌아간다(재생성 절차는 data/README.md '동결본' 절 참조).
    """
    frozen = Path(data_xlsx).parent / "ccm_p9_raw_by_row_id.tsv"
    if frozen.exists():
        table = pd.read_csv(frozen, sep="\t").set_index("row_id")["p9_raw"]
        return table.sort_index().reset_index(drop=True)
    if not Path(data_xlsx).exists():
        raise FileNotFoundError(
            f"P9 원값 원천이 둘 다 없다 — 동결본({frozen})도 원본({data_xlsx})도 없음"
        )
    sur = pd.read_excel(data_xlsx, sheet_name="SUR", usecols=["P9"])
    return pd.to_numeric(sur["P9"], errors="coerce")


def build(d_valid: pd.DataFrame, data_xlsx) -> DesiredAT23:
    """의도: d_valid 전체 20관측에서 피험자별 desired setpoint 1개를 확정한다.
    입력: d_valid(adapter 산출, 열 no/env_pair/time_min/row_id/actual 필요), data.xlsx 경로.
    출력: DesiredAT23.
    """
    need = {"no", "env_pair", "time_min", "row_id", "actual"}
    missing = need - set(d_valid.columns)
    if missing:
        raise RuntimeError(f"d_valid에 필요한 열 없음: {sorted(missing)}")

    pool = d_valid[["row_id", "no", "env_pair", "time_min", "actual"]].copy()

    # 피험자당 관측 수가 20이 아니면 pool 정의나 cohort 귀속이 달라진 것 — 조용히 넘기지 않는다.
    counts = pool.groupby("no").size()
    if set(counts.unique()) != {EXPECTED_POOL_PER_SUBJECT}:
        raise RuntimeError(
            f"전체 DSF pool의 피험자별 관측수가 {EXPECTED_POOL_PER_SUBJECT}이 아니다: "
            f"{counts.value_counts().to_dict()}"
        )

    # P9 원값 대조 — row_id 규약이 깨지면 imputed 플래그가 통째로 틀리므로 반드시 검증한다.
    p9_raw = _p9_raw_by_row_id(data_xlsx).reindex(pool["row_id"]).to_numpy(float)
    pool["p9_raw"] = p9_raw
    pool["imputed"] = np.isnan(p9_raw)  # P9 결측 → PT로 대체된 행
    observed = pool[~pool["imputed"]]
    if not np.allclose(observed["actual"], observed["p9_raw"]):
        raise RuntimeError(
            "row_id→SUR 행 대응이 깨졌다 — actual과 P9 원값이 불일치 "
            "(imputed 플래그를 신뢰할 수 없으므로 중단)"
        )

    subject_mean = pool.groupby("no")["actual"].mean()

    values, records = {}, []
    for no, g in pool.groupby("no"):
        counter = Counter(g["actual"])
        top = max(counter.values())
        cands = sorted(v for v, k in counter.items() if k == top)
        stage, cands_stage1 = "mode", list(cands)
        nearest = list(cands)

        if len(cands) > 1:  # --- 2단계: 전체 평균 최근접 ---
            m = float(subject_mean[no])
            min_distance = min(abs(v - m) for v in cands)
            nearest = [v for v in cands if np.isclose(abs(v - m), min_distance)]
            cands = list(nearest)
            stage = "tie_nearest_subject_mean"

        if len(cands) > 1:  # --- 3단계: 사용자 확정 canonical override ---
            override = CANONICAL_TIE_OVERRIDES.get(int(no))
            if override is None or override not in cands:
                raise RuntimeError(
                    f"피험자 {no}의 최종 동점 {cands}에 canonical override가 없다"
                )
            cands = [override]
            stage = "tie_canonical_override"

        values[no] = float(cands[0])
        records.append(
            {
                "no": no,
                "desired": float(cands[0]),
                "stage": stage,
                "n_obs": len(g),
                "n_imputed": int(g["imputed"].sum()),
                "mode_count": top,
                "cands_mode": ";".join(f"{v:g}" for v in cands_stage1),
                "cands_nearest_mean": ";".join(f"{v:g}" for v in nearest),
                "subject_mean_all": round(float(subject_mean[no]), 4),
            }
        )

    per_subject = pd.Series(values, name="desired").sort_index()
    per_subject.index.name = "no"
    resolution = pd.DataFrame(records).sort_values("no").reset_index(drop=True)

    stage_counts = resolution["stage"].value_counts().to_dict()
    meta = {
        "definition": "전체 20개 P9_filled의 개인별 최빈값",
        "n_subjects": int(len(per_subject)),
        "n_pool_rows": int(len(pool)),
        "n_pool_rows_imputed": int(pool["imputed"].sum()),
        "tie_break": [
            "1) 전체 20관측 최빈값",
            "2) 동점이면 개인 전체 20관측 평균에 최근접",
            "3) 등거리 동점은 canonical override: 19=24°C, 83=22°C",
        ],
        "stage_counts": stage_counts,
        "desired_mean_C": round(float(per_subject.mean()), 4),
        "desired_sd_C": round(float(per_subject.std(ddof=1)), 4),
        "desired_min_C": float(per_subject.min()),
        "desired_max_C": float(per_subject.max()),
        "canonical_tie_overrides": CANONICAL_TIE_OVERRIDES,
    }
    return DesiredAT23(
        per_subject=per_subject, pool=pool, resolution=resolution, meta=meta
    )
