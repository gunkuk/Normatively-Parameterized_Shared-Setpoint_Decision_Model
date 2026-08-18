# =====================================================
# 파일명: sampling.py
# 역할: 계약 E(SampleSet)의 대표표본 생성 교체축. legacy 혼합 demographic bootstrap(form_mixed) 이식.
# 입력: d(피험자×세션 DataFrame, no/sex/age/env_pair/time_min 열 필요), N(그룹크기), comp(혼합기준), rng, R(반복수)
# 출력: 그룹 리스트 [행idx 배열, ...] (그룹 원소 = d의 행 인덱스)
# 의존: numpy, pandas, registry
# =====================================================
"""표본 생성 — ARCHITECTURE.md 계약 E. 🟡 P2(잠정) — settings.PROVISIONAL["P2"] 참조.

원본: `_exp_ccm_phase2_engine.py`의 `form_mixed` bit-identical 이식(수식·분배 로직 불변).
★ 컬럼명 주의: legacy는 'time_min'(분 단위 시간축)을 썼다. 이번 이식의 입력 데이터(MODEL_OOF.tsv)는
시간축이 없고 대신 cohort 프레임의 'feature_window'(시간 슬롯 라벨, 예 "1-5")가 동급 역할을 한다.
adapter.py가 이 열을 'time_min'으로 alias해서 넘기므로, 이 함수 자체는 원본과 로직 변경이 0이다
(같은 "공통 env×time 셀" 개념을 그대로 쓴다 — governance actions의 2026-07-24-001 CCM port 기록 참조).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import registry


@registry.register("sampling", "subject_pool_random", provisional="P2")
def subject_pool_random(
    d: pd.DataFrame, N: int, comp: str, rng: np.random.Generator, R: int = 300
) -> list:
    """의도: 조건을 이미 만족하는 pool 안에서 N명 그룹을 **정확히 R개** 만든다.
    입력: d(행=피험자, 축약된 프레임), N(그룹크기), comp(무시), rng, R(반복수).
    출력: 길이 R의 그룹 리스트(각 원소 = 길이 N의 행 인덱스 배열).

    ★ 왜 새로 만들었나 (2026-08-04 사용자 지시)
    기존 pooled_random·form_mixed는 "먼저 N명을 뽑고 → 그 전원이 공유하는 env×time 셀이
    있는지 확인 → 없으면 그 회차를 버린다(continue)" 구조였다. 그래서 R=300을 요청해도
    실제 성립한 그룹은 300개보다 적었고, 평균이 몇 개의 표본 위에서 계산됐는지가 실행마다
    달랐다. 즉 요청한 반복수와 실현된 반복수가 달랐다.

    이 함수는 **개인별 DSF가 확정된 pool**(전체 20관측 빈도 축약, 행=피험자)을 전제하므로
    셀을 맞출 일이 없다 — 피험자만 뽑으면 되고, 따라서 탈락이 원리적으로 발생하지 않는다.
    R회 요청하면 정확히 R개가 나온다.
    """
    if N > len(d):
        # 조용히 빈 리스트를 돌려주면 셀이 통째로 사라진 것을 알아채기 어렵다.
        raise ValueError(f"N={N}이 pool 크기 {len(d)}보다 크다 — 그룹 구성 불가")
    idx = np.arange(len(d))
    # replace=False → 한 그룹 안에 같은 사람이 두 번 들어가지 않는다(그룹 간에는 중복 허용).
    return [rng.choice(idx, N, replace=False) for _ in range(R)]


@registry.register("sampling", "pooled_random", provisional="P2")
def pooled_random(
    d: pd.DataFrame, N: int, comp: str, rng: np.random.Generator, R: int = 20
) -> list:
    """의도: demographic 층화 없이 **완전 무작위**로 N명 그룹 R개를 만든다(대조군).
    입력: form_mixed와 동일 시그니처. comp는 무시된다(층화를 쓰지 않으므로).
    출력: 그룹 리스트(각 원소 = d의 행 인덱스 배열).

    왜 필요한가(2026-07-28 사용자 지시): 현재 이질성 축은 '성별/연령으로 어떻게 섞었나'인데,
    연령 분할이 코호트 중앙값 23.5세(전원 20대)라 층화가 실질적 이질성을 만들지 못한다.
    무작위 구성과 비교해야 층화가 무엇을 바꾸는지 알 수 있다.
    form_mixed와 동일하게 **공통 env×time 셀** 안에서 뽑아 조건 비교가능성을 유지한다.
    """
    sub = d.drop_duplicates("no")
    nos = sub["no"].to_numpy()
    out = []
    for _ in range(R):
        if len(nos) < N:
            continue
        picked = rng.choice(nos, N, replace=False)  # 피험자 단위 무작위 N명
        # form_mixed와 같은 규약: 뽑힌 전원이 공통으로 가진 env×time 셀 하나에서 1행씩
        cand = d[d["no"].isin(picked)]
        cells = (
            cand.groupby(["env_pair", "time_min"])["no"].nunique().loc[lambda s: s == N]
        )
        if cells.empty:
            continue
        env, tmin = cells.index[rng.integers(len(cells))]
        sel = cand[(cand.env_pair == env) & (cand.time_min == tmin)]
        idx = [sel.index[sel["no"] == p][0] for p in picked]  # 사람마다 그 셀의 1행
        out.append(np.array(idx))
    return out


@registry.register("sampling", "form_mixed", provisional="P2")
def form_mixed(
    d: pd.DataFrame, N: int, comp: str, rng: np.random.Generator, R: int = 20
) -> list:
    """의도: 혼합 구성 그룹 R개를 피험자단위로 추출 + 공통 env×time cell 1행씩 배정.
    입력: d(no/sex/age/env_pair/time_min 열 포함, 세션=행), N(그룹크기 1~10),
          comp('sex'|'age'|'sexage' 혼합기준), rng(numpy Generator), R(반복 그룹 수).
    출력: 그룹 리스트(각 원소 = d의 행 인덱스 배열, 길이 N 또는 그 미만이면 skip됨).
    원본: engine `form_mixed` bit-identical.
    """
    sub = d.drop_duplicates("no")  # 피험자별 1행(demographic은 피험자불변)
    sx_s = sub["sex"].to_numpy() if "sex" in d.columns else np.zeros(len(sub))
    am = d["age"].median() if "age" in d.columns else 0
    ag_s = (
        (sub["age"].to_numpy() > am).astype(int)
        if "age" in d.columns
        else np.zeros(len(sub), int)
    )
    nos = sub["no"].to_numpy()
    if comp == "sex":
        strata = {"M": nos[sx_s == 1], "F": nos[sx_s == 0]}
    elif comp == "age":
        strata = {"old": nos[ag_s == 1], "young": nos[ag_s == 0]}
    else:  # sexage 1:1:1:1
        strata = {
            "Mo": nos[(sx_s == 1) & (ag_s == 1)],
            "My": nos[(sx_s == 1) & (ag_s == 0)],
            "Fo": nos[(sx_s == 0) & (ag_s == 1)],
            "Fy": nos[(sx_s == 0) & (ag_s == 0)],
        }
    n_str = len(strata)
    if N < n_str:
        # engine 2026-07-02 T2 버그수정: strata별 최소1명 강제가 N<n_str서 그룹크기를 부풀림
        # → comp 분할이 원리적으로 불가할 때는 pooled(전 피험자 1개 stratum)로 정확히 N명.
        strata = {"pooled": nos}
        n_str = 1
    base = N // n_str
    rem = N % n_str
    per_list = [base + (1 if i < rem else 0) for i in range(n_str)]
    per_list = [max(1, p) for p in per_list]
    if any(len(v) < p for v, p in zip(strata.values(), per_list)):
        return []  # stratum 피험자 수가 요구보다 작으면 구성 불가
    has_cell = "env_pair" in d.columns and "time_min" in d.columns
    if has_cell:
        cells = d[["env_pair", "time_min"]].drop_duplicates().to_numpy()
    row_of = {}
    if has_cell:
        for i, (no, ep, tm) in enumerate(
            zip(d["no"].to_numpy(), d["env_pair"].to_numpy(), d["time_min"].to_numpy())
        ):
            row_of[(no, ep, tm)] = i
    groups = []
    for _ in range(R):
        chosen_subs = np.concatenate(
            [
                rng.choice(v, size=p, replace=False)
                for v, p in zip(strata.values(), per_list)
            ]
        )
        if has_cell:
            ep, tm = cells[rng.integers(len(cells))]
            g = [row_of[(no, ep, tm)] for no in chosen_subs if (no, ep, tm) in row_of]
            if len(g) < len(chosen_subs):  # 일부 피험자가 그 cell에 없으면 skip
                continue
            groups.append(np.array(g))
        else:  # env×time 없으면 피험자당 임의 1행(공점유 근사 불가 — manuscript 한계 명시)
            g = [
                rng.choice(np.where(d["no"].to_numpy() == no)[0]) for no in chosen_subs
            ]
            groups.append(np.array(g))
    return groups
