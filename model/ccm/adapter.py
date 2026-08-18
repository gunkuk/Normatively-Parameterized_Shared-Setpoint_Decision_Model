# =====================================================
# 파일명: adapter.py
# 역할: STEP2 입력 어댑터. MODEL_OOF.tsv(cell==mean, 62명·1,240행·248세션)에서
#       계약 A(PersonSet) 재료를 만들고, PCM 계약·금지feature 감사를 통과해야 통과시킨다.
# 입력: settings.PCM_OOF_RELPATH(MODEL_OOF.tsv), model_selection의 quality62 cohort 빌더(env_pair 등 join용)
# 출력: PersonMaterial(d_valid DataFrame, met_all 배열, contract dict)
# 의존: pandas, numpy, settings, rules(met_for)
# =====================================================
"""입력 어댑터 — ARCHITECTURE.md 계약 A(PersonSet). PLAN.md STEP2·verify 2.

★ 설계 결정 (PLAN.md에 없어 이번에 내린 것 — governance actions의 2026-07-24-001 CCM port 기록 참조):
legacy `form_mixed()`의 "공통 env×time cell" 샘플링에는 env_pair·time_min이 필요한데,
MODEL_OOF.tsv(유일 지정 입력)에는 `row_id, subject, actual, prediction, session("{no}_{env_pair}")`
뿐이라 이 두 열이 없다. 그래서 row_id로 PCM 62명 cohort 원본 프레임(quality62 빌더 —
MODEL_OOF.tsv 자체가 이 프레임에서 나온 것)에 역참조해 env_pair·feature_window(=legacy time_min과
동급인 시간슬롯 라벨)·sex/age/BMI/weight(demographic·PMV met용, legacy도 동일 열 사용)만 join한다.
이 5개는 신체계측·실험조건 라벨이지 설문응답(TP/TCV/PT/P1~9/M1~9)도 ECG도 MBTI도 아니다 — 그리고
CCM은 예측 모델이 아니라 결정론적 규칙 계산이라 애초에 '입력 feature'라는 개념이 desired 값
하나뿐이다(그 값은 오직 MODEL_OOF의 prediction/actual에서만 온다).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import rules, settings

# PLAN.md §2-3 절대규칙 그대로: 설문응답·ECG·MBTI는 feature로 쓰지 않는다.
BANNED_EXACT = {
    "TSV",
    "TCV",
    "TCV_3class",
    "TA",
    "TP",
    "TP_3class",
    "PT",
    "P1",
    "P2",
    "P3",
    "P4",
    "P5",
    "P6",
    "P7",
    "P8",
    "P9",
    "P6_want",
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "M7",
    "M8",
    "M9",
    "M6_want",
    "P9n",
    "PTn",
    "TPn",
    "desired_SP",
    "observed_numeric_p9",
    "P9_filled",
    "E",
    "N",
    "T",
    "J",
    "A",  # MBTI 5축
}
BANNED_PREFIX = ("ecg_",)

# 어댑터가 cohort 프레임에서 가져오는 열은 이 화이트리스트뿐이다(신체계측·실험조건 라벨만).
JOIN_COLS = [
    "row_id",
    "no",
    "env_pair",
    "feature_window",
    "sex",
    "age",
    "BMI",
    "weight",
]


def _project_root() -> Path:
    """의도: 이 파일 기준 프로젝트 루트(experiments/·이 있는 곳) 탐색."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "data").is_dir() and (parent / "run_ccm.py").is_file():
            return parent
    raise RuntimeError("저장소 루트(run_ccm.py가 있는 폴더)를 찾을 수 없다")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module load failed: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class PersonMaterial:
    """의도: 계약 A(PersonSet)의 재료 — 그룹 형성·PMV met 계산에 필요한 전부를 담는다.
    d_valid: 1,240행 DataFrame(no/sex/age/BMI/weight/env_pair/time_min/row_id/actual/prediction).
    met_all: d_valid과 같은 행 순서의 met 배열(그룹 인덱싱 시 met_all[g]로 슬라이스).
    contract: 계약검증에서 실측한 사실(행수·피험자수·세션수 등) — provenance에 그대로 박힌다.
    """

    d_valid: pd.DataFrame
    met_all: np.ndarray
    contract: dict
    # 개인단위 빈도 축약 시 desired 확정의 근거 표들. 축약을 안 하면 빈 dict.
    desired_tables: dict = field(default_factory=dict)


def load() -> PersonMaterial:
    """의도: MODEL_OOF.tsv(mean cell) + cohort join → PersonMaterial. 계약 위반 시 즉시 예외.
    출력: PersonMaterial. 이 함수가 성공적으로 반환하면 verify 2(§PLAN)가 전부 통과한 것이다.
    """
    root = _project_root()

    # --- 1. MODEL_OOF.tsv(mean cell) 로드 ------------------------------
    oof_path = root / settings.PCM_OOF_RELPATH
    if not oof_path.exists():
        raise FileNotFoundError(
            f"MODEL_OOF.tsv 없음({oof_path}) — 조용한 폴백 없음, 즉시 중단"
        )
    oof = pd.read_csv(oof_path, sep="\t")
    mean = oof[oof["cell"] == settings.PCM_OOF_CELL].copy()
    if mean.empty:
        raise ValueError(f"MODEL_OOF.tsv에 cell=={settings.PCM_OOF_CELL!r} 행이 없다")

    # --- 2. PCM 계약 검증 (verify 2 — 실패 시 §6 중단조건) --------------
    n_rows, n_subj, n_sess = (
        len(mean),
        mean["subject"].nunique(),
        mean["session"].nunique(),
    )
    if n_rows != settings.PCM_EXPECT_ROWS:
        raise RuntimeError(
            f"행 수 불일치: 기대 {settings.PCM_EXPECT_ROWS}, 실측 {n_rows}"
        )
    if n_subj != settings.PCM_EXPECT_SUBJECTS:
        raise RuntimeError(
            f"피험자 수 불일치: 기대 {settings.PCM_EXPECT_SUBJECTS}, 실측 {n_subj}"
        )
    if n_sess != settings.PCM_EXPECT_SESSIONS:
        raise RuntimeError(
            f"세션 수 불일치: 기대 {settings.PCM_EXPECT_SESSIONS}, 실측 {n_sess}"
        )
    if mean["prediction"].isna().any():
        raise RuntimeError("prediction 열에 결측 존재 — CCM 결정입력 불완전")
    if mean["actual"].isna().any():
        raise RuntimeError("actual 열에 결측 존재 — oracle/평가 불완전")
    if mean["row_id"].duplicated().any():
        raise RuntimeError("row_id 중복 — mean cell이 유일 행 집합이 아니다")

    # --- 3. cohort join 테이블 (동결본 읽기) ------------------------------
    # ★ 2026-08-05 사용자 지시로 **매 실행 재계산 → 동결본 읽기**로 바꿨다.
    #   이전에는 run_quality62_pt_imputed.py를 importlib으로 로드해 build_cohort()를 돌렸다.
    #   그 러너는 (a) 폴더 재정렬 v3에서 사라진 model/src 경로를 sys.path에 넣고,
    #   (b) model/_archive의 _exp_target_metric_matrix를 import하며,
    #   (c) TabPFN·huggingface_hub까지 끌어온다 — 그래서 CCM이 PYTHONPATH 수동 주입 없이는
    #   아예 실행되지 않았다. 정작 필요한 건 신체계측·실험조건 라벨 8열뿐이고 재계산할
    #   이유가 없으므로 data/에 동결하고 여기서는 읽기만 한다.
    #   동결본 재생성이 필요하면 그 러너를 직접 돌려 data/ccm_cohort62_join.tsv를 갱신하고
    #   PROVENANCE.json의 sha256을 함께 고친다(README §데이터 동결 참조).
    join_path = root / "data" / "ccm_cohort62_join.tsv"
    if not join_path.exists():
        raise FileNotFoundError(
            f"cohort join 동결본 없음({join_path}) — 조용한 폴백 없음. "
            "재생성 절차는 README의 '데이터 동결' 절 참조"
        )
    cohort_frame = pd.read_csv(join_path, sep="\t")

    missing_join_cols = [c for c in JOIN_COLS if c not in cohort_frame.columns]
    if missing_join_cols:
        raise RuntimeError(f"동결본에 join 대상 열 없음: {missing_join_cols}")
    join_src = cohort_frame[JOIN_COLS].drop_duplicates("row_id")

    # 동결본 무결성 — 파일이 바뀌면 PROVENANCE의 sha256과 어긋나 즉시 잡힌다.
    prov_path = root / "data" / "ccm_cohort62_join.PROVENANCE.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        actual_sha = hashlib.sha256(join_path.read_bytes()).hexdigest()
        if actual_sha != prov.get("sha256"):
            raise RuntimeError(
                f"cohort 동결본 sha256 불일치 — 기대 {prov.get('sha256')}, 실측 {actual_sha}"
            )

    # 금지 열 감사(화이트리스트 선택이지만 §2 절대규칙 3 준수를 코드로도 강제) ---
    banned_hit = (set(JOIN_COLS) & BANNED_EXACT) | {
        c for c in JOIN_COLS if c.startswith(BANNED_PREFIX)
    }
    if banned_hit:
        raise RuntimeError(f"금지 feature가 join 대상에 섞임: {banned_hit}")

    merged = mean.merge(
        join_src,
        on="row_id",
        how="left",
        validate="one_to_one",
    )
    if merged[JOIN_COLS[1:]].isna().any().any():  # row_id 제외 전부 결측 없어야 함
        raise RuntimeError("cohort join 후 결측 발생 — row_id 정합 확인 필요")
    if len(merged) != n_rows:
        raise RuntimeError(f"join 후 행수 변화: {n_rows} -> {len(merged)}")

    # legacy 'time_min'과 동급 시간슬롯 alias(위 모듈 docstring 참조) — sampling.py는 원본 그대로.
    merged = merged.rename(columns={"feature_window": "time_min"})

    d_valid = merged[
        [
            "row_id",
            "no",
            "sex",
            "age",
            "BMI",
            "weight",
            "env_pair",
            "time_min",
            "actual",
            "prediction",
        ]
    ].reset_index(drop=True)

    # --- 4. met 배열 (PMV rule 전용) ------------------------------------
    met_all = rules.met_for(
        d_valid["sex"].to_numpy(),
        d_valid["age"].to_numpy(),
        d_valid["BMI"].to_numpy(),
        d_valid["weight"].to_numpy(),
    )

    contract = {
        "n_rows": int(n_rows),
        "n_subjects": int(n_subj),
        "n_sessions": int(n_sess),
        "cell": settings.PCM_OOF_CELL,
        "source_oof": str(settings.PCM_OOF_RELPATH),
        "join_cols": JOIN_COLS,
        "banned_audit": "PASS(0 hits)",
    }

    # --- 5. 전체 20관측 빈도 기반 개인단위 축약 (2026-08-13 사용자 확정) ---
    tables: dict = {}
    if settings.PERSON_GRAIN == "subject_frequency":
        d_valid, met_all, dsf_contract, tables = _collapse_to_subject_frequency(
            d_valid, root
        )
        contract.update(dsf_contract)

    return PersonMaterial(
        d_valid=d_valid, met_all=met_all, contract=contract, desired_tables=tables
    )


def _collapse_to_subject_frequency(d_valid: pd.DataFrame, root: Path):
    """의도: 행=피험자×세션×시간창(1,240) 프레임을 행=피험자(62) 프레임으로 줄인다.
    입력: d_valid(세션 단위), 프로젝트 루트.
    출력: (d_subject, met_subject, contract 조각).

    출력의 4번째 원소 tables = desired 확정 근거 표 3종(per_subject/pool/resolution).

    ★ 왜 축약하는가 — desired_at23 모듈 docstring 참조(전체 반복응답의 대표값).
    `actual`을 전체 20관측 최빈값으로 **덮어쓴다**: oracle에서는 결정입력과 평가기준이 같은
    "그 사람이 원하는 온도" 하나여야 한다. 둘이 다르면 규칙이 최적화하는 대상과 채점
    대상이 어긋나 결과 해석이 불가능해진다.

    `prediction`은 전체 20행의 피험자 평균으로 옮긴다 — 🟡 잠정(P10). 이 축약이 배포(deploy)
    경로에 무엇이 맞는 집계인지는 별도 결정이 필요하다(oracle 모드에서는 쓰이지 않는다).
    """
    from . import desired_at23

    dsf = desired_at23.build(d_valid, root / "data" / "data.xlsx")
    pool_ids = set(dsf.pool["row_id"])

    # 신체계측·demographic은 피험자 불변이라 첫 행을 그대로 쓴다.
    d_subject = (
        d_valid.drop_duplicates("no")
        .set_index("no")
        .loc[dsf.per_subject.index, ["sex", "age", "BMI", "weight"]]
        .reset_index()
    )
    d_subject["actual"] = dsf.per_subject.to_numpy(float)
    d_subject["prediction"] = (
        d_valid[d_valid["row_id"].isin(pool_ids)]
        .groupby("no")["prediction"]
        .mean()
        .loc[dsf.per_subject.index]
        .to_numpy(float)
    )
    # 아래 두 열은 축약 후 의미가 없지만(노출조건을 이미 고정했다) 하류 코드가
    # 열 존재를 가정하므로 단일 상수로 채워 둔다 — 표본추출은 이 열을 쓰지 않는다.
    d_subject["env_pair"] = "all20"
    d_subject["time_min"] = "all20"
    d_subject["row_id"] = -1
    d_subject = d_subject[
        [
            "row_id",
            "no",
            "sex",
            "age",
            "BMI",
            "weight",
            "env_pair",
            "time_min",
            "actual",
            "prediction",
        ]
    ].reset_index(drop=True)

    met_subject = rules.met_for(
        d_subject["sex"].to_numpy(),
        d_subject["age"].to_numpy(),
        d_subject["BMI"].to_numpy(),
        d_subject["weight"].to_numpy(),
    )
    tables = {
        "per_subject": dsf.per_subject.reset_index(),
        "pool": dsf.pool,
        "resolution": dsf.resolution,
    }
    return (
        d_subject,
        met_subject,
        {"person_grain": "subject_frequency", "dsf": dsf.meta},
        tables,
    )
