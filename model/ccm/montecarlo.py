# =====================================================
# 파일명: montecarlo.py
# 역할: PCM 예측오차의 전파를 재는 몬테카를로. 경험적 OOF 잔차를 재표본해 결정입력에
#       주입하고 CCM 결과(4축·setpoint·frontier 성립)의 분포·신뢰구간을 낸다.
# 입력: adapter.PersonMaterial(prediction·actual), settings, rules/social/energy
# 출력: results/MONTECARLO.tsv, results/MONTECARLO_FRONTIER.tsv, results/MONTECARLO_PROVENANCE.json
# 의존: numpy, pandas, adapter, rules, sampling, social, registry, settings, EnergyPlus.energy
# =====================================================
"""몬테카를로 오차전파 — oracle 대조를 대체하는 정답-불필요 검증.

★ 왜 필요한가
deploy run은 **단 한 번의 오차 실현**만 보여준다 — "nash의 frontier 성립률 40%"가 구조인지
그 한 번의 운인지 구분이 안 된다. 이 모듈은 같은 크기의 오차를 100번 다시 뽑아 그 40%에
신뢰구간을 붙인다.

★ 무엇을 흔드는가 (그리고 무엇을 고정하는가)
  흔든다  : 결정입력 desired* = base + r'   (r' = 재표본된 잔차, base는 §1.5 MODES)
  고정한다: 그룹 구성(생산 run과 같은 seed), 규칙, 격자, 효용, 평가기준(actual)
그룹을 고정하는 이유 — 흔들면 '표본 변동'과 '예측오차 전파'가 섞여 무엇이 결론을
흔들었는지 분리가 안 된다. 이 모듈의 질문은 후자 하나다.

★ 잔차 재표본 방식: 피험자 블록 치환 (subject-block permutation)
i.i.d. 재표본은 **개인별 계통 편향**을 깨뜨린다. 실측에서 피험자별 잔차 평균의 SD가
0.30°C로 무시할 수 없어(전체 잔차 SD 1.10°C의 27%), 한 사람의 20행 잔차 벡터를
통째로 다른 사람에게 배정하는 블록 치환을 쓴다 — 개인 내 오차 상관이 보존된다.

★ pmv는 재계산하지 않는다
pmv 규칙은 desired를 전혀 쓰지 않고 met만 쓰므로(rules.rule_pmv) 잔차를 흔들어도
setpoint가 불변이다. replicate마다 다시 풀면 비용의 절반을 버리는 것이라 1회만 계산해
전 replicate에 재사용한다. 이건 근사가 아니라 **정확히 같은 값**이다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from EnergyPlus import energy  # noqa: E402

from . import adapter, interpreter, registry, rules, settings, social  # noqa: E402

# 4축 정의 — figures.AXES4와 같은 순서·같은 최대화 방향(에너지만 최소화).
AXES4 = [
    ("efficiency", True),
    ("fairness", True),
    ("equity_cvar10", True),
    ("energy_MWh", False),
]
TOLS = (0.0, 0.02, 0.05)


# --- 1. 잔차 블록 치환 ---------------------------------------------------
def _residual_blocks(d_valid: pd.DataFrame) -> tuple[np.ndarray, list[np.ndarray]]:
    """의도: 피험자별 잔차 벡터를 블록으로 묶어 치환 재표본 재료를 만든다.
    입력: d_valid(no·actual·prediction 보유).
    출력: (잔차 배열 r[n], 피험자별 행 인덱스 리스트).

    r = prediction − actual. 즉 "예측이 진실에서 얼마나 벗어났나"이고,
    다른 사람의 r을 빌려 오면 "같은 모델이 이 사람에게 낼 법한 다른 오차"가 된다.
    """
    r = d_valid["prediction"].to_numpy(float) - d_valid["actual"].to_numpy(
        float
    )  # 잔차
    blocks = [
        np.flatnonzero(d_valid["no"].to_numpy() == s)
        for s in d_valid["no"].drop_duplicates()
    ]
    sizes = {len(b) for b in blocks}
    if len(sizes) != 1:
        # 블록 크기가 다르면 통째 배정이 성립하지 않는다 — 조용히 잘라 쓰지 않고 멈춘다.
        raise RuntimeError(f"피험자별 행수가 균일하지 않다: {sorted(sizes)}")
    return r, blocks


def _perturbed_desired(
    base: np.ndarray, r: np.ndarray, blocks: list[np.ndarray], rng
) -> np.ndarray:
    """의도: 한 replicate의 결정입력 desired*를 만든다 = base + (치환된 잔차).
    입력: base 배열(mode가 정한 기준점), 잔차 배열, 피험자 블록, rng.
    출력: desired* 배열.
    """
    order = rng.permutation(len(blocks))  # 피험자 → 다른 피험자의 잔차 블록 배정
    out = base.copy()
    for dst, src in enumerate(order):
        out[blocks[dst]] += r[blocks[src]]
    return out


# --- 1.5 주입 모드 -------------------------------------------------------
# ★ 2026-08-04 정정: 처음에는 base=prediction만 썼는데, prediction은 **이미 자기 오차를
#   품고 있어** 거기에 잔차를 또 더하면 총 오차 SD가 1.104 → 1.567 (=√2배)로 부풀었다.
#   그 상태의 결과는 배포 성능의 불편추정이 아니라 '2배 분산 stress test'였다(실측 비율 1.419).
#   두 모드를 명시적으로 갈라 라벨을 붙인다.
MODES = {
    # 정본. base=actual이므로 desired*의 오차 = 치환 잔차 그 자체 → 크기가 실제 배포와 일치.
    # "같은 크기의 오차를 다르게 냈다면 결론이 얼마나 달라지나"에 답한다.
    # actual은 **시뮬레이션 구성에만** 쓰이고 결정·평가 경로에 정답이 새지 않는다.
    "calibrated": "actual",
    # 정답 없이 돌릴 수 있는 판본. 오차가 √2배라 결과는 보수적 상한(stress)으로만 읽는다.
    "stress": "prediction",
}


# --- 2. 한 replicate 계산 -------------------------------------------------
def _axes_for(setpoints, groups, actual, utility_fn):
    """의도: 그룹별 setpoint 목록 → 방 단위로 계산한 3축 + 인원가중 평균 setpoint.
    입력: setpoint 리스트, 그룹 인덱스 리스트, actual 배열, 효용함수.
    출력: (setpoint평균, efficiency, fairness, equity).
    평가는 항상 actual로 한다 — 결정입력이 무엇이든 채점 기준은 불변(interpreter와 동일 원칙).
    """
    eff, fair, eq, ns = [], [], [], []
    for sp, g in zip(setpoints, groups):
        u = utility_fn(sp, actual[g])
        eff.append(float(u.mean()))
        fair.append(float(1 - social.gini(u)))
        eq.append(float(social.cvar(u)))
        ns.append(len(g))
    return (
        float(np.average(setpoints, weights=ns)),
        float(np.mean(eff)),
        float(np.mean(fair)),
        float(np.mean(eq)),
    )


def _nd_with_tol(M: np.ndarray, tol: float) -> np.ndarray:
    """의도: 축을 0~1로 정규화한 뒤 tol 여유를 준 4축 비지배 판정.
    입력: M(결정점 × 4축), tol.
    출력: bool 배열. figures.make_rule_pareto_table의 nd_with_tol과 동일 로직
          (같은 판정을 두 곳에서 다르게 구현하면 MC와 점추정이 비교 불가가 된다).
    """
    S = M.copy()
    for j, (_, maximize) in enumerate(AXES4):
        if not maximize:
            S[:, j] = -S[:, j]  # 최소화축(에너지)을 뒤집어 전부 '클수록 좋음'으로
    rng_ = S.max(axis=0) - S.min(axis=0)
    rng_[rng_ == 0] = 1.0  # 상수축은 나눗셈이 깨지므로 1로 둔다(기여 0)
    Sn = S / rng_
    return np.array(
        [
            not np.any(
                np.all(Sn >= Sn[i] - tol, axis=1) & np.any(Sn > Sn[i] + tol, axis=1)
            )
            for i in range(len(Sn))
        ]
    )


# --- 3. 전체 실행 ---------------------------------------------------------
def run(B: int, R: int, seed: int = 20260804, mode: str = "calibrated") -> dict:
    """의도: B회 replicate를 돌려 4축·setpoint·frontier 성립의 분포를 낸다.
    입력: B(replicate 수), R(셀당 그룹 수), seed(치환용 마스터 시드),
          mode("calibrated"=오차크기 일치 정본 | "stress"=√2배 보수적 상한).
    출력: {"axes": DataFrame, "frontier": DataFrame, "meta": dict}.
    """
    if settings.DECISION_SOURCE != "prediction":
        raise RuntimeError(
            "montecarlo는 CCM_DECISION_SOURCE=prediction 에서만 의미가 있다 "
            f"(현재 {settings.DECISION_SOURCE!r}) — oracle에는 흔들 예측오차가 없다"
        )
    pm = adapter.load()
    d = pm.d_valid
    actual = d["actual"].to_numpy(float)
    prediction = d["prediction"].to_numpy(float)
    utility_fn = registry.resolve("utility", settings.DEFAULT_SELECTION["utility"])
    sampling_fn = registry.resolve("sampling", settings.DEFAULT_SELECTION["sampling"])
    if mode not in MODES:
        raise ValueError(f"mode는 {sorted(MODES)} 중 하나 (받은 값: {mode!r})")
    base = {"actual": actual, "prediction": prediction}[MODES[mode]]
    r, blocks = _residual_blocks(d)

    # 그룹은 생산 run과 **같은 seed**로 한 번만 뽑아 전 replicate가 공유한다.
    groups_by_N = {
        N: sampling_fn(
            d,
            N,
            "pooled",
            np.random.default_rng(interpreter._cell_seed(N, "pooled", "annual")),
            R=R,
        )
        for N in settings.GROUP_SIZES
    }

    rule_eps = interpreter.RULE_EPS
    non_pmv = [(rule, eps) for rule, eps in rule_eps if rule != "pmv"]

    # pmv는 desired 비의존 → 1회만 계산해 재사용(정확히 같은 값).
    pmv_fn = registry.resolve("rule", "pmv")
    pmv_cache = {}
    for N, groups in groups_by_N.items():
        sps = [
            pmv_fn(actual[g], rules.REAL_GRID, utility_fn, met_grp=pm.met_all[g])
            for g in groups
        ]
        pmv_cache[N] = _axes_for(sps, groups, actual, utility_fn)

    master = np.random.default_rng(seed)
    records = []
    t0 = time.perf_counter()
    for b in range(B):
        rng = np.random.default_rng(master.integers(2**63))
        desired = _perturbed_desired(base, r, blocks, rng)
        for N, groups in groups_by_N.items():
            rows = [("pmv", None) + pmv_cache[N]]
            for rule, eps in non_pmv:
                fn = registry.resolve("rule", rule)
                e = 1.0 if eps is None else eps
                sps = [
                    fn(desired[g], rules.REAL_GRID, utility_fn, eps=e, met_grp=None)
                    for g in groups
                ]
                rows.append((rule, eps) + _axes_for(sps, groups, actual, utility_fn))
            for rule, eps, sp, ef, fa, eq in rows:
                for season in settings.SEASONS:
                    records.append(
                        {
                            "b": b,
                            "N": N,
                            "season": season,
                            "rule": rule,
                            "eps": (
                                "" if eps is None else ("inf" if np.isinf(eps) else eps)
                            ),
                            "setpoint": sp,
                            "efficiency": ef,
                            "fairness": fa,
                            "equity_cvar10": eq,
                            "energy_MWh": energy.apply(sp, season),
                        }
                    )
        if (b + 1) % 10 == 0:
            el = time.perf_counter() - t0
            print(
                f"  replicate {b + 1}/{B}  경과 {el / 60:.1f}분  "
                f"잔여 {(el / (b + 1) * (B - b - 1)) / 60:.1f}분",
                flush=True,
            )
    long = pd.DataFrame(records)

    # --- 4축 분포 요약 (replicate 간) ---
    axes = (
        long[long.season == "annual"]
        .groupby(["N", "rule", "eps"])[
            ["setpoint", "efficiency", "fairness", "equity_cvar10", "energy_MWh"]
        ]
        .agg(["mean", "std", lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)])
    )
    axes.columns = [
        f"{a}_{ {'mean': 'mean', 'std': 'sd', '<lambda_0>': 'p2.5', '<lambda_1>': 'p97.5'}[s] }"
        for a, s in axes.columns
    ]
    axes = axes.reset_index()

    # --- frontier 성립률 분포 ---
    fr = []
    for (b, N, season), g in long.groupby(["b", "N", "season"]):
        g = g.reset_index(drop=True)
        M = np.column_stack([g[c].to_numpy(float) for c, _ in AXES4])
        masks = {t: _nd_with_tol(M, t) for t in TOLS}
        for i in range(len(g)):
            fr.append(
                {
                    "b": b,
                    "N": N,
                    "season": season,
                    "rule": g["rule"][i],
                    "eps": g["eps"][i],
                    **{f"nd_tol{t:g}": bool(masks[t][i]) for t in TOLS},
                }
            )
    frl = pd.DataFrame(fr)
    per_b = (
        frl.groupby(["b", "rule", "eps"])[[f"nd_tol{t:g}" for t in TOLS]].mean() * 100.0
    )
    frontier = per_b.groupby(["rule", "eps"]).agg(
        ["mean", "std", lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)]
    )
    frontier.columns = [
        f"{a}_{ {'mean': 'mean', 'std': 'sd', '<lambda_0>': 'p2.5', '<lambda_1>': 'p97.5'}[s] }"
        for a, s in frontier.columns
    ]
    frontier = frontier.reset_index()

    return {
        "axes": axes,
        "frontier": frontier,
        "long": long,
        "meta": {
            "B": B,
            "R": R,
            "seed": seed,
            "mode": mode,
            "base": MODES[mode],
            "injected_error_sd_ratio": round(1.0 if mode == "calibrated" else 2**0.5, 3),
            "resample": "subject-block permutation (20행 블록 통째 배정)",
            "residual_sd_C": float(r.std(ddof=1)),
            "residual_mae_C": float(np.abs(r).mean()),
            "subject_bias_sd_C": float(
                pd.Series(r).groupby(d["no"].to_numpy()).mean().std(ddof=1)
            ),
            "fixed": ["groups", "rules", "grid", "utility", "evaluation=actual"],
            "pmv_note": "pmv는 desired 비의존이라 1회 계산 후 재사용(근사 아님)",
            "elapsed_min": round((time.perf_counter() - t0) / 60, 2),
        },
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=100, help="replicate 수")
    ap.add_argument("--R", type=int, default=300, help="셀당 그룹 수(생산 run과 동일)")
    ap.add_argument("--mode", default="calibrated", choices=sorted(MODES))
    a = ap.parse_args()
    res = run(B=a.B, R=a.R, mode=a.mode)
    out = interpreter.RESULTS_DIR
    # 모드별로 파일을 갈라 덮어쓰기를 막는다(정본 calibrated는 접미사 없음).
    sfx = "" if a.mode == "calibrated" else f"_{a.mode}"
    out.mkdir(parents=True, exist_ok=True)
    res["axes"].to_csv(out / f"MONTECARLO{sfx}.tsv", sep="\t", index=False)
    res["frontier"].to_csv(out / f"MONTECARLO_FRONTIER{sfx}.tsv", sep="\t", index=False)
    res["long"].to_csv(out / f"MONTECARLO_LONG{sfx}.tsv.gz", sep="\t", index=False)
    (out / f"MONTECARLO_PROVENANCE{sfx}.json").write_text(
        json.dumps(res["meta"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", **res["meta"]}, ensure_ascii=False))
