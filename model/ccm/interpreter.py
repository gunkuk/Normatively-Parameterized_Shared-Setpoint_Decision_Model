# =====================================================
# 파일명: interpreter.py  (구 runner.py — "runner"가 통일 runner인 run_all.py와 헷갈려 개명, 2026-07-24)
# 역할: STEP3~5 결정 해석기(interpreter). (N × demographic × season) 셀 단위 checkpoint로
#       resume 가능하게 전 규칙(15개 rule×eps 결정점) × oracle만 계산해
#       full_p9filled.csv + PROVENANCE.json을 낸다 — 이 모듈이 CCM 규칙을 실제로 "해석 실행"한다.
# 입력: adapter.PersonMaterial, settings(GROUP_SIZES/SEASONS/DEMOGRAPHICS/SMOKE/PROVISIONAL)
# 출력: results/full_p9filled.csv, checkpoints/cfg_*.tsv, results/PROVENANCE.json
# 의존: numpy, pandas, hashlib, json, adapter, rules, sampling, social, utility, energy, registry, settings
# =====================================================
"""CCM 결정 해석기(interpreter) — PLAN.md STEP3~5.

★ 개명 이력: 이 파일은 원래 `runner.py`였다. 그런데 통일 실행기의 이름도 `run_all.py`
(experiment_runner, 파이썬 stage subprocess를 도는 그 "runner")라서, 대화·문서에서
"runner"라 부르면 항상 어느 쪽인지 되물어야 했다. 이 모듈이 하는 일은 등록된 규칙들을
"실행 해석"하는 것 — registry에서 규칙·표본추출·효용함수를 이름으로 찾아(resolve) 실제
셀 하나하나에 적용하는 해석기(interpreter) 역할이라 그 이름으로 바꿨다(사용자 지시 2026-07-24).

★ oracle 계산에 대한 중요 기록 (반드시 REPORT.md §7에도 재기록):
PLAN.md §2 절대규칙 2는 "`ground_truth`는... 실행 경로에서 절대 쓰지 않는다"고 못박았다.
그런데 STEP6이 요구하는 필수 figure(PAR4_*, PAR2_collapse)는 legacy `_fig_pareto4d.py`·
`_fig_pareto_collapse.py`를 "figure config 그대로" 재사용해야 하고, 그 스크립트들은 전부
oracle(실측으로 결정)과 deploy(예측으로 결정) **두 컬럼 세트**를 나란히 그린다
(ARCHITECTURE.md §7.5가 이 oracle의 존재의미 — "PCM 예측오차 vs CCM 규칙 효과 분리" —를
명시적으로 옹호한다). registry.py의 gate 자체도 무조건 차단이 아니라
`resolve(..., allow_legacy=True)`라는 **의도적 escape hatch**로 설계돼 있다(§6.1).

그래서 이 runner는 딱 한 곳에서, 라벨을 분명히 하고(컬럼명 `_oracle` 접미사, DEFAULT_SELECTION은
불변으로 유지), `resolve("decision_source", "ground_truth", allow_legacy=True)`를 명시 호출해
oracle 비교축을 계산한다. **이건 "gate가 뚫린 것"이 아니라 gate가 설계한 그 escape hatch를
의도적으로, 라벨을 붙여, 딱 한 줄만 쓴 것**이라고 판단했다 — 하지만 이 판단 자체가 절대규칙과
문면상 부딪히는 지점이라 사용자 재확인이 필요하다(REPORT.md §7 필독).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# energy.py는 EnergyPlus/ 폴더로 분리 이동(2026-08-03) — ccm 패키지 밖이라 model/을
# sys.path에 먼저 넣어야 패키지-경유 import(EnergyPlus.energy)가 된다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from EnergyPlus import energy  # noqa: E402

from . import adapter, registry, rules, settings, social, visual_registry

HERE = Path(__file__).resolve().parent


def _project_root() -> Path:
    """의도: 모듈 깊이에 의존하지 않고 프로젝트 루트를 찾는다.
    입력: 없음. 출력: data/ 와 CLAUDE.md 를 동시에 가진 최초의 조상 경로.

    ★ 2026-08-04: 이전 코드는 `HERE.parents[2]`로 루트를 셌는데, 폴더 재정렬로 모듈
    깊이가 한 단계 얕아지면서(model/src/ccm → model/ccm) parents[2]가 프로젝트 루트가
    아니라 그 **상위 폴더(Desktop)** 를 가리키게 됐다. 그 결과 산출물이 조용히
    Desktop/experiment/ 로 새어 나갔다 — 예외가 안 나서 발견이 늦었다.
    adapter.py가 이미 쓰는 것과 같은 방식으로 통일한다.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "data").is_dir() and (parent / "run_ccm.py").is_file():
            return parent
    raise RuntimeError("저장소 루트(run_ccm.py가 있는 폴더)를 찾을 수 없다")


# 산출물은 패키지 밖 experiment/<exp>/_internal 에 쓴다.
CCM_OUT = _project_root() / settings.CCM_OUT_RELPATH
CHECKPOINT_DIR = CCM_OUT / "checkpoints"
RESULTS_DIR = CCM_OUT / "results"
# ★ 2026-08-10 사용자 지시: "experiment/ccm 에는 svg, .md, 폴더만 있으면 돼".
#   그룹단위 전수(tsv.gz)·요약(tsv)·PROVENANCE(json)·desired_frequency_* 원자료는 사람이 직접
#   여는 배포본이 아니라 figure가 읽는 **입력 데이터**이므로 _internal/results로 옮긴다.
#   figure(svg)와 그 캡션 문서(RESULTS_SCHEMA.md·Results.md, 둘 다 .md)만 최상위에 남는다.
DATA_DIR = RESULTS_DIR
FIG_DIR = _project_root() / settings.CCM_FIG_RELPATH  # svg·md 전용 최상위 폴더
GLOBAL_SEED = 0  # legacy run_m9(seed=0)과 동일 기본값


# --- 0. 재현용 해시 유틸(pcm/hashing.py·model_selection storage.py와 동일 관행, 자체 보유) ---
def _stable_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha(value) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _code_fingerprint() -> str:
    """의도: 로직 모듈 소스가 바뀌면 checkpoint를 자동 무효화(핸드 관리 버전 번호보다 안전).
    입력: 없음. 출력: 8개 로직 파일 바이트를 이어붙인 sha256.

    ★ 2026-08-04 수정: energy.py는 2026-08-03에 model/EnergyPlus/로 분리 이동했는데
    이 목록이 갱신되지 않아 FileNotFoundError로 죽고 있었다(즉 재정렬 이후 sweep이
    한 번도 안 돌았다). 경로를 파일별로 명시해 다시 옮겨도 여기서 바로 잡히게 한다.
    """
    files = [
        HERE / "utility.py",
        HERE / "rules.py",
        HERE / "social.py",
        HERE / "sampling.py",
        HERE / "adapter.py",
        HERE / "desired_at23.py",  # legacy 파일명, 현재는 전체 20관측 DSF 정의의 owner
        HERE.parent / "EnergyPlus" / "energy.py",  # ccm 패키지 밖
        HERE / "sources.py",
        # ★ 2026-08-13 추가: interpreter.py **자신**. 이 파일이 셀 집계(방 단위 평균 vs
        #   pooled)와 출력 반올림 자릿수를 소유하는데 지문에 빠져 있어, 반올림을 4→9자리로
        #   고쳐도 checkpoint가 그대로 재사용돼 구 값이 살아남았다(resumed=50, computed=0).
        #   지문이 잡아야 할 전형적인 stale이 조용히 통과한 것이다.
        #   ⚠️ 대가: 이 파일을 주석 한 줄만 고쳐도 전 checkpoint가 무효화돼 full recompute가
        #   된다. 조용한 stale보다 재계산 비용이 낫다는 것이 이 지문의 원래 취지다.
        Path(__file__).resolve(),
    ]
    h = hashlib.sha256()
    for f in files:
        if (
            not f.exists()
        ):  # 조용히 건너뛰면 지문이 약해져 stale checkpoint를 통과시킨다
            raise FileNotFoundError(f"code fingerprint 대상 파일 없음: {f}")
        h.update(f.read_bytes())
    return h.hexdigest()


def _atomic_write_tsv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, sep="\t", index=False)
    tmp.replace(path)


def _atomic_write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    tmp.replace(path)


# --- 1. rule×eps 결정점 목록 (engine 그대로: atkinson만 EPS_GRID로 확장) -----
def _rule_eps_list() -> list[tuple[str, float | None]]:
    out: list[tuple[str, float | None]] = []
    for rule in rules.CCM_RULES:
        if rule == "atkinson":
            out += [(rule, eps) for eps in rules.EPS_GRID]
        else:
            out.append((rule, None))
    return out


RULE_EPS = _rule_eps_list()  # 8 + 6 = 14 (minimax_regret 제외, rules.py 주석 참조)


# --- 2. 셀(N×demographic×season) 단위 config_hash -----------------------
def _cell_config_hash(N: int, demographic: str, season: str, R: int) -> str:
    payload = {
        "N": N,
        "demographic": demographic,
        "season": season,
        "R": R,
        "grid": [
            settings.SETPOINT_MIN_C,
            settings.SETPOINT_MAX_C,
            settings.SETPOINT_STEP_C,
        ],
        "eps_grid": [None if e is None or np.isinf(e) else e for e in rules.EPS_GRID],
        "rules": rules.CCM_RULES,
        "selection": settings.DEFAULT_SELECTION,
        "provisional_ids": sorted(
            set(registry.provisional_ids(settings.DEFAULT_SELECTION)) | {"P3"}
        ),
        "analysis_sources": visual_registry.enabled_sources(),
        "decision_source": settings.DEFAULT_SELECTION["decision_source"],
        # grain이 바뀌면 desired의 정의 자체가 달라지므로 checkpoint를 반드시 무효화한다.
        "person_grain": settings.PERSON_GRAIN,
        "code_fingerprint": _code_fingerprint(),
    }
    return _sha(payload)


def _cell_seed(N: int, demographic: str, season: str) -> int:
    """의도: 실행 순서·resume 여부와 무관하게 셀마다 독립·결정적인 rng seed를 만든다.
    (legacy는 global 1개 rng를 순차 소비했으나, 그러면 일부 셀만 resume 시 이후 셀의 난수열이
    바뀐다 — checkpoint 정합을 위해 셀별 독립 seed로 바꿨다. 규칙·수식은 무변경, 채집 순서만 조정.)
    """
    key = f"{N}|{demographic}|{season}|{GLOBAL_SEED}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


# --- 3. 한 셀 계산 --------------------------------------------------------
def _read_checkpoint(
    path: Path, expected_hash: str, expected_rows: int
) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path, sep="\t")
    except Exception:
        return None
    if len(frame) != expected_rows:
        return None
    if "config_hash" not in frame.columns or frame["config_hash"].nunique() != 1:
        return None
    if str(frame["config_hash"].iloc[0]) != expected_hash:
        return None
    numeric_cols = [
        c
        for c in frame.columns
        if c.startswith(("setpoint_", "efficiency_", "fairness_", "equity_", "energy_"))
    ]
    if not np.isfinite(frame[numeric_cols].to_numpy(float)).all():
        return None
    return frame


def _compute_cell(
    d_valid: pd.DataFrame,
    met_all: np.ndarray,
    desired_decision: np.ndarray,
    N: int,
    demographic: str,
    season: str,
    R: int,
    utility_fn,
    sampling_fn,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """의도: 한 (N,demographic,season) 셀의 rule×eps 행을 계산한다.
    출력: (셀 요약 DataFrame, 그룹단위 전수 DataFrame) 또는 None(그룹 구성 불가 시 skip).

    ★ 2026-08-04 추가: 두 번째 반환값 = **300회 개별 결과 전수**. 이전에는 R회 결과를
    평균만 남기고 버렸는데, 그러면 "그 평균이 몇 개 위에서·얼마나 퍼진 값 위에서 나왔나"를
    사후에 확인할 방법이 없었다(사용자 지시: 각 실행의 모든 result 저장).
    """
    rng = np.random.default_rng(_cell_seed(N, demographic, season))
    groups = sampling_fn(d_valid, N, demographic, rng, R=R)
    if not groups:
        return None
    config_hash = _cell_config_hash(N, demographic, season, R)
    tag = settings.SOURCE_TAG  # "oracle" | "deploy" — 컬럼 접미사
    actual_all = d_valid["actual"].to_numpy()
    subject_no = d_valid["no"].to_numpy()
    rows, long_rows = [], []
    for rule, eps in RULE_EPS:
        rule_fn = registry.resolve("rule", rule)
        eff_eps = 1.0 if eps is None else eps
        dec_o, ns = [], []
        U_o_parts = []
        eps_out = "" if eps is None else ("inf" if np.isinf(eps) else eps)
        for rep, g in enumerate(groups):
            met_grp = met_all[g] if rule == "pmv" else None
            sp_o = rule_fn(
                desired_decision[g],
                rules.REAL_GRID,
                utility_fn,
                eps=eff_eps,
                met_grp=met_grp,
            )
            dec_o.append(sp_o)
            ns.append(len(g))
            # 평가는 항상 ground truth(actual)로 — 결정입력이 무엇이든 채점 기준은 동일(legacy util_true_c와 동일 원칙)
            actual_g = actual_all[g]
            u = utility_fn(sp_o, actual_g)
            U_o_parts.append(u)
            long_rows.append(
                {
                    "N": N,
                    "demographic": demographic,
                    "season": season,
                    "rule": rule,
                    "eps": eps_out,
                    "rep": rep,  # 0..R-1 — 이 셀의 몇 번째 무작위 그룹인가
                    "setpoint": round(float(sp_o), 3),
                    "efficiency": round(float(u.mean()), 6),
                    "fairness": round(float(1 - social.gini(u)), 6),
                    "equity_cvar10": round(float(social.cvar(u)), 6),
                    "energy_MWh": round(energy.apply(float(sp_o), season), 3),
                    # 그룹 구성원 — 재현·사후 층별분석용(피험자 번호를 ; 로 이어 붙임)
                    "members": ";".join(str(x) for x in subject_no[g]),
                    "desired_members": ";".join(f"{v:g}" for v in actual_g),
                }
            )
        mean_o = float(np.average(dec_o, weights=ns))
        # ★ 2026-07-28 수정: 비선형 지표(Gini·CVaR)는 **방 하나 안에서** 계산한 뒤 방들에
        # 걸쳐 평균낸다. 이전에는 300개 방의 효용을 한 벡터로 concat한 뒤 계산했는데(pooled),
        # 그러면 '한 방에서 가장 불만인 사람'이 아니라 '전체 1,800명 중 하위 10%'를 재게 되어
        # 방 **사이** 불평등이 섞여 들어왔다. 그 결과 ε이 커질수록 형평이 오히려 떨어지는
        # 역전이 18/18 셀에서 났다(그룹별로 바꾸면 0/18). 사용자 확정: "형평은 한 방에서 최악".
        # efficiency는 선형이라 집계 방식과 무관하지만 해석 단위를 맞추려 함께 방 단위로 낸다.
        per_eff = [float(u.mean()) for u in U_o_parts]
        per_fair = [float(1 - social.gini(u)) for u in U_o_parts]
        per_equity = [float(social.cvar(u)) for u in U_o_parts]
        rows.append(
            {
                "N": N,
                "demographic": demographic,
                "season": season,
                "rule": rule,
                "eps": eps_out,
                "n_groups": len(groups),
                f"setpoint_{tag}": round(mean_o, 3),
                # ★ 2026-08-13: 4자리 → 9자리. 4자리는 **표시용 반올림인데 지배 판정을
                #   좌우했다.** 파레토 지배는 knife-edge라 동률이면 뒤집히는데, 규칙 간
                #   efficiency 차이가 1e-6 수준인 셀이 있어(N=6: median 0.835317383 vs
                #   ε=0 0.835317940) 4자리로 자르면 없던 동률이 생겨 한쪽이 지배당한 것으로
                #   바뀐다. 실제로 이 csv를 읽는 Fig.D4와 groups 원자료를 읽는 Fig.6이
                #   N=4·6·10에서 서로 다른 지배 판정을 냈다. 개별 그룹값이 6자리이므로
                #   300개 평균은 그보다 정밀하며, 9자리면 그 정보를 버리지 않는다.
                #   ⚠️ 1e-6 차이가 과학적으로 유의하다는 뜻은 아니다 — 그 판단은 Fig.6의
                #   tolerance 패널이 한다. 여기서는 두 그림이 모순되지 않게만 만든다.
                f"efficiency_{tag}": round(float(np.mean(per_eff)), 9),
                f"fairness_{tag}": round(float(np.mean(per_fair)), 9),
                f"equity_cvar10_{tag}": round(float(np.mean(per_equity)), 9),
                f"energy_MWh_{tag}": round(energy.apply(mean_o, season), 1),
                # 300회의 산포 — 평균만으로는 "이 값이 얼마나 안정적인가"를 알 수 없다.
                f"setpoint_sd_{tag}": (
                    round(float(np.std(dec_o, ddof=1)), 4) if len(dec_o) > 1 else 0.0
                ),
                f"efficiency_sd_{tag}": (
                    round(float(np.std(per_eff, ddof=1)), 4)
                    if len(per_eff) > 1
                    else 0.0
                ),
                f"fairness_sd_{tag}": (
                    round(float(np.std(per_fair, ddof=1)), 4)
                    if len(per_fair) > 1
                    else 0.0
                ),
                f"equity_cvar10_sd_{tag}": (
                    round(float(np.std(per_equity, ddof=1)), 4)
                    if len(per_equity) > 1
                    else 0.0
                ),
                "config_hash": config_hash,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(long_rows)


# --- 4. 전체 sweep --------------------------------------------------------
def run(group_sizes, seasons, demographics, rule_filter, R: int) -> dict:
    """의도: 지정된 축 격자 전체를 순회하며 checkpoint를 읽거나 새로 계산한다.
    입력: group_sizes/seasons/demographics(축 값 리스트), rule_filter(None=전체), R(반복수).
    출력: {"rows": 합쳐진 DataFrame, "resumed": [cfg,...], "computed": [cfg,...], "skipped": [cfg,...]}.
    """
    pm = adapter.load()
    utility_fn = registry.resolve("utility", settings.DEFAULT_SELECTION["utility"])
    sampling_fn = registry.resolve("sampling", settings.DEFAULT_SELECTION["sampling"])
    # The visual register is also the source gate for this sweep: deployable
    # PCM-prediction values are not calculated or emitted while oracle-only is
    # active.  Changing this requires one explicit register review.
    visual_registry.enabled_sources()
    # 결정입력은 settings 스위치가 정한다(§DECISION_SOURCE). oracle 모드에서만
    # ground_truth escape hatch가 필요하므로 그때만 allow_legacy를 켠다 —
    # prediction 모드는 gate를 건드리지 않고 정상 경로로 resolve된다.
    _impl = settings.DEFAULT_SELECTION["decision_source"]
    desired_decision = registry.resolve(
        "decision_source", _impl, allow_legacy=(_impl == "ground_truth")
    )(pm.d_valid)

    resumed, computed, skipped = [], [], []
    all_rows, all_long = [], []
    for N in group_sizes:
        for demographic in demographics:
            for season in seasons:
                cfg_key = f"N{N}_{demographic}_{season}"
                ck_path = CHECKPOINT_DIR / f"cfg_{cfg_key}.tsv"
                long_path = CHECKPOINT_DIR / f"long_{cfg_key}.tsv.gz"
                expected_hash = _cell_config_hash(N, demographic, season, R)
                cached = _read_checkpoint(ck_path, expected_hash, len(RULE_EPS))
                # 요약 checkpoint가 유효해도 그룹단위 전수가 없으면 재계산한다 —
                # 반쪽 산출물을 조용히 통과시키면 long 파일에 구멍이 생긴다.
                if cached is not None and long_path.exists():
                    resumed.append(cfg_key)
                    all_rows.append(cached)
                    all_long.append(pd.read_csv(long_path, sep="\t"))
                    continue
                out = _compute_cell(
                    pm.d_valid,
                    pm.met_all,
                    desired_decision,
                    N,
                    demographic,
                    season,
                    R,
                    utility_fn,
                    sampling_fn,
                )
                if out is None:
                    skipped.append(cfg_key)
                    continue
                frame, long_frame = out
                _atomic_write_tsv(ck_path, frame)
                long_path.parent.mkdir(parents=True, exist_ok=True)
                long_frame.to_csv(long_path, sep="\t", index=False)
                computed.append(cfg_key)
                all_rows.append(frame)
                all_long.append(long_frame)
    merged = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    long_merged = pd.concat(all_long, ignore_index=True) if all_long else pd.DataFrame()
    if rule_filter is not None:
        merged = merged[merged["rule"].isin(rule_filter)].reset_index(drop=True)
        long_merged = long_merged[long_merged["rule"].isin(rule_filter)].reset_index(
            drop=True
        )
    return {
        "rows": merged,
        "long": long_merged,
        "resumed": resumed,
        "computed": computed,
        "skipped": skipped,
        "contract": pm.contract,
        "desired_tables": pm.desired_tables,
    }


def _write_outputs(result: dict, tag: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / f"{tag}.csv"
    result["rows"].to_csv(csv_path, index=False, encoding="utf-8-sig")
    provenance = {
        "tag": tag,
        "contract": result["contract"],
        "n_rows": int(len(result["rows"])),
        "cells_resumed": result["resumed"],
        "cells_computed": result["computed"],
        "cells_skipped": result["skipped"],
        "selection": settings.DEFAULT_SELECTION,
        "provisional_ids": sorted(
            set(registry.provisional_ids(settings.DEFAULT_SELECTION)) | {"P3"}
        ),
        "analysis_sources": visual_registry.enabled_sources(),
        "decision_source": settings.DEFAULT_SELECTION["decision_source"],
        "source_tag": settings.SOURCE_TAG,
        "decision_source_note": (
            "oracle 모드는 ground_truth를 allow_legacy=True로 명시 호출한다"
            "(모듈 docstring 참조). prediction 모드는 gate 없이 정상 경로."
        ),
        "code_fingerprint": _code_fingerprint(),
    }
    _atomic_write_json(RESULTS_DIR / "PROVENANCE.json", provenance)

    # --- 사람이 여는 산출물 폴더(Results.md·figure와 같은 곳)에 전수 데이터 배포 ---
    # 2026-08-04 사용자 지시: 각 실행의 모든 result를 Results.md·figure와 같은 폴더에,
    # README·Results.md가 참조 가능한 형태로 남긴다. 대용량 tabular은 TSV.gz(gzip 압축
    # 탭구분) — pandas가 확장자만 보고 바로 읽고, 스키마는 아래 RESULTS_SCHEMA.md가 소유.
    _publish_dataset(result, tag, provenance)

    print(f"[done] {tag}: {len(result['rows'])} rows -> {csv_path}")
    print(
        f"  resumed={len(result['resumed'])} computed={len(result['computed'])} skipped={len(result['skipped'])}"
    )
    print(f"  그룹단위 전수 {len(result['long'])} rows -> {DATA_DIR}")


def _publish_dataset(result: dict, tag: str, provenance: dict) -> None:
    """의도: 실행 결과 전수를 산출물 폴더에 TSV.gz로 내고 스키마 문서를 갱신한다.
    입력: run() 결과 dict, tag(full_p9filled|smoke_p9filled), provenance dict.
    출력: 없음(파일 기록).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    long_df, summary = result["long"], result["rows"]

    long_df.to_csv(DATA_DIR / f"{tag}_groups.tsv.gz", sep="\t", index=False)
    summary.to_csv(DATA_DIR / f"{tag}_summary.tsv", sep="\t", index=False)

    # desired 확정 근거(개인별 값·전수 관측·tie 해소 경로) — grain=session이면 비어 있다.
    for name, frame in result["desired_tables"].items():
        frame.to_csv(DATA_DIR / f"desired_frequency_{name}.tsv", sep="\t", index=False)

    _atomic_write_json(DATA_DIR / f"{tag}_PROVENANCE.json", provenance)
    _write_schema_doc(tag, long_df, summary, result)


def _fmt_bytes(path: Path) -> str:
    n = path.stat().st_size
    return f"{n / 1024:.0f} KB" if n < 1024**2 else f"{n / 1024**2:.1f} MB"


def _write_schema_doc(tag, long_df, summary, result) -> None:
    """의도: 방금 낸 데이터 파일들의 스키마·행수·읽는 법을 자기완결 문서로 남긴다.
    입력: tag, 그룹단위 전수 DF, 셀 요약 DF, run() 결과 dict.
    출력: 없음(RESULTS_SCHEMA.md 기록).

    ★ 왜 필요한가: TSV.gz는 열어보기 전에는 열이 무엇인지 알 수 없다. 이 문서가 없으면
    "efficiency가 0~1인지 %인지", "eps 빈칸이 무슨 뜻인지"를 매번 코드로 되짚어야 한다.
    """
    dsf = result["contract"].get("dsf", {})
    tables = result["desired_tables"]
    files = []
    for fname, desc in [
        (f"{tag}_groups.tsv.gz", "그룹단위 전수 — 무작위 그룹 1개 = 1행"),
        (f"{tag}_summary.tsv", "셀 요약 — R회 평균±SD, 1행 = (N × season × rule×eps)"),
        ("desired_frequency_per_subject.tsv", "피험자별 확정 desired setpoint"),
        ("desired_frequency_pool.tsv", "확정에 쓰인 전체 20관측 전수"),
        ("desired_frequency_resolution.tsv", "피험자별 확정 경로(최빈/동점해소 단계)"),
        (f"{tag}_PROVENANCE.json", "이 실행의 선택·해시·계약"),
    ]:
        p = DATA_DIR / fname
        if p.exists():
            # 원자료는 _internal/results에 있고 이 문서는 최상위(FIG_DIR)에 쓰인다 —
            # 링크는 그 상대경로로 적는다.
            files.append(
                f"| [`{fname}`](_internal/results/{fname}) | {desc} | {_fmt_bytes(p)} |"
            )

    seasons = sorted(long_df["season"].unique()) if len(long_df) else []
    ns = sorted(int(x) for x in long_df["N"].unique()) if len(long_df) else []
    rules_list = sorted(long_df["rule"].unique()) if len(long_df) else []
    reps = int(long_df["rep"].nunique()) if len(long_df) else 0

    doc = f"""# CCM 결과 데이터 — 스키마 명세

> **이 문서의 용어**
> - **desired setpoint** — 그 사람 혼자 온도조절기를 쥐었다면 골랐을 실내 공기온도(°C).
> - **AT** — ambient air temperature, 실측 공기온도(°C).
> - **oracle** — 예측오차 0인 DSF. desired를 실측값으로 직접 공급받는 구성.
> - **rule×eps** — 합의 규칙과 그 불평등회피 계수(ε). ε은 atkinson에만 있고 나머지는 빈칸.
> - **그룹(=방)** — 한 시점에 같은 zone을 공유하는 N명. 무작위로 R회 재구성한다.

데이터 파일은 `_internal/results/`에 있다(이 문서 자신은 `.md`라 최상위에 남는다 —
2026-08-10 사용자 지시 "experiment/ccm 에는 svg, .md, 폴더만"). `model/ccm/interpreter.py`
실행이 자동 생성한다. 손으로 고치지 말 것. 그림(`*.svg`)과 [`Results.md`](Results.md)가
참조하는 수치의 정본이다.

## 1. 파일 목록

| 파일 | 내용 | 크기 |
|---|---|---:|
{chr(10).join(files)}

`.tsv.gz` = gzip 압축된 탭 구분 텍스트. pandas가 확장자를 보고 알아서 푼다:

```python
import pandas as pd
g = pd.read_csv("_internal/results/{tag}_groups.tsv.gz", sep="\\t")
```

## 2. `{tag}_groups.tsv.gz` — 그룹단위 전수 ({len(long_df):,}행)

**1행 = 무작위로 구성한 그룹 1개에 규칙 1개를 적용한 결과.** 평균 내기 **전**의 원자료다.

| 열 | 뜻 | 값 |
|---|---|---|
| `N` | 그룹 크기(명) | {ns} |
| `demographic` | 표본 구성 기준 | `pooled`(층화 없음) |
| `season` | 에너지 환산 계절 | {seasons} |
| `rule` | 합의 규칙 | {rules_list} |
| `eps` | atkinson의 불평등회피 ε | 숫자 · `inf` · 빈칸(=해당 없음) |
| `rep` | 그 셀의 몇 번째 무작위 그룹인가 | 0 … {reps - 1} (총 {reps}회) |
| `setpoint` | 그 규칙이 고른 공유 설정온도 | °C |
| `efficiency` | 그룹 평균 효용 | 0~1 (1=전원 만족) |
| `fairness` | 1 − Gini(효용) | 0~1 (1=완전 균등) |
| `equity_cvar10` | 하위 10% 평균 효용(CVaR) | 0~1 |
| `energy_MWh` | 그 setpoint의 연간 에너지 | MWh |
| `members` | 그룹 구성원 피험자 번호 | `;` 구분 |
| `desired_members` | 그 구성원들의 desired setpoint | `;` 구분, °C |

★ `fairness`·`equity_cvar10`은 **방 하나 안에서** 계산한다(방 사이 불평등을 섞지 않는다).

## 3. `{tag}_summary.tsv` — 셀 요약 ({len(summary):,}행)

**1행 = (N × season × rule×eps) 한 셀.** §2의 {reps}행을 평균낸 값 + 그 산포(SD).
`*_{settings.SOURCE_TAG}` 접미사는 결정입력 종류(`oracle`=실측, `deploy`=PCM 예측)를 뜻한다.
`n_groups` = 그 평균이 실제로 몇 개 그룹 위에서 나왔는지 — **항상 {reps}이어야 한다.**

## 4. `desired_frequency_*.tsv` — desired setpoint 확정 근거

oracle이 반환하는 개인별 desired는 **각 피험자의 전체 20개 `P9_filled` 관측에서 얻은
최빈값**이다. 정의·근거는 호환 파일 `model/ccm/desired_at23.py`의 docstring이 소유한다.

- **pool** = 피험자 62명 × 전체 20관측 = 1,240행
- **tie 해소 3단계**: ① 유일 최빈값 → ② 복수 최빈값이면 전체 20관측 평균에 가장 가까운 값 →
  ③ 평균까지 정확히 동률이면 사전 지정 canonical 값(19번 24°C, 83번 22°C)
- **실측 결과**: {dsf.get("stage_counts", {})}
- **분포**: 평균 {dsf.get("desired_mean_C", "?")}°C, SD {dsf.get("desired_sd_C", "?")}°C,
  범위 {dsf.get("desired_min_C", "?")}~{dsf.get("desired_max_C", "?")}°C, n={dsf.get("n_subjects", "?")}

`desired_frequency_resolution.tsv`의 `stage` 열이 각 피험자가 ①②③ 중 어디서 정해졌는지
알려주고, `cands_mode`·`cands_nearest_mean`이 동점 후보를 그대로 남긴다.

### 알려진 데이터 이상
{dsf.get("known_anomaly", "(없음)")}

## 5. 재생성

```bash
cd model && python -m ccm.interpreter
```

`{tag}_PROVENANCE.json`의 `code_fingerprint`가 로직 파일 해시다 — 이 값이 같으면 같은 코드다.
"""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "RESULTS_SCHEMA.md").write_text(doc, encoding="utf-8")  # .md는 최상위


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        smoke = settings.SMOKE
        res = run(
            group_sizes=smoke["group_sizes"],
            seasons=smoke["seasons"],
            demographics=settings.DEMOGRAPHICS,
            rule_filter=smoke["rules"],
            R=smoke["R"],
        )
        _write_outputs(res, tag="smoke_p9filled")
    else:
        R_full = settings.PROVISIONAL["P2"]["값"]["R_full"]
        res = run(
            group_sizes=settings.GROUP_SIZES,
            seasons=settings.SEASONS,
            demographics=settings.DEMOGRAPHICS,
            rule_filter=None,
            R=R_full,
        )
        _write_outputs(res, tag="full_p9filled")
