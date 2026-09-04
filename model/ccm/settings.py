# =====================================================
# 파일명: settings.py
# 역할: CCM의 모든 설정값을 단독 소유하는 SSOT(단일 진실 공급원). 값만 갖고 로직은 0.
# 입력: 없음 (아무것도 import하지 않는다 — 순환 의존 원천 차단)
# 출력: 다른 모듈이 `from ccm import settings`로 읽어간다
# 의존: 없음
# =====================================================
"""CCM 설정 SSOT — pcm/settings.py와 동일한 규율.

★ 이 파일의 규칙 세 가지:
  1. **값만 둔다.** 함수·클래스·계산 로직을 넣지 않는다.
  2. **아무것도 import 안 한다.** 그래야 어느 모듈에서도 안전하게 읽을 수 있다.
  3. **미확정(🟡)에 임의 기본값을 정하지 않는다.** 잠정값은 반드시 PROVISIONAL 대장에
     ID를 달아 등록한다 — 그래야 "확정된 것처럼" 굳지 않는다(ARCHITECTURE.md §5-4).
"""

# --- 1. 상류 PCM 계약 (여기가 바뀌면 CCM 전체가 무효) ------------------
# 2026-07-23 사용자 확정: CCM은 PCM 마감본 기준을 따른다(ARCHITECTURE.md §7.3).
PCM_TARGET = "P9_filled"  # T*(=AT+(P9-PT)) 아님. legacy T* 경로는 comparator로만 보존
PCM_EXPECT_SUBJECTS = 62
PCM_EXPECT_ROWS = 1240
PCM_EXPECT_SESSIONS = 248

# PCM OOF 산출물 — CCM의 유일한 결정입력 원천.
# `actual` 열 = 실측 P9_filled(=🔒 ground_truth), `prediction` 열 = TabPFN OOF(=✅ pcm_prediction)
# ★ 이 배포 저장소에서는 원본 C-PCM의 experiment/model_selection/.../model_matrix/ 대신
#   data/ 한 곳에 모아 둔다(README '원본과의 차이' 참조). 파일 내용은 동일하다.
PCM_OOF_RELPATH = "data/MODEL_OOF.tsv"
PCM_OOF_CELL = "mean"  # 20열 mean 집계 = 채택된 최종 행렬(TabPFN 챔피언)

# CCM 산출물 root(프로젝트 상대 경로 문자열) — src 패키지 밖.
# "model/=코드+설명만" 폴더 재정렬 v3 (2026-07-27). 각 모듈이 자기 ROOT에 join해 쓴다.
# --- 효용 구현 (2026-08-05: clip on/off 스위치 폐기, 단일 구현) ----------
# 구 CCM_UTILITY_MODE=clip|linear 스위치를 제거했다. linear(clip-off) 판본은 단순
# experiment였고 정본 후보가 아니었으며, W를 3.5→7.0으로 올리며(P5) 그 판본이 겨냥하던
# 포화 문제가 해소됐다. 코드는 experiment/ccm/_internal/legacy/triangular_linear.py,
# 산출물은 experiment/ccm/_internal/variant_linear/ 에 보존한다.
import os as _os

UTILITY_MODE = "clip"  # 고정. 되살리려면 legacy 파일 상단 주석의 3단계를 따른다.
_UTILITY_IMPL = "triangular_clip"

# --- 표본 구성 스위치 (🟡 P2 open, 2026-07-28 사용자 지시) --------------
# ★ 2026-07-28 정본 전환: 무작위(pooled)가 기본이다. 층화(mixed)는 지우지 않고
#   register option으로 남겨 CCM_SAMPLING_MODE=mixed로 대조 실행할 수 있게 둔다.
#   전환 근거: 연령 층화가 코호트 중앙값 23.5세(전원 20대) 분할이라 실질 이질성을
#   만들지 못했고, 실측에서도 층화/무작위 형평 차이가 2~3% 이내였다.
#   pooled = pooled_random (정본. 층화 없음 → 이질성 축이 사라짐)
#   mixed  = form_mixed    (option. 성별/연령/성별×연령 1:1 층화)
#   subject = subject_pool_random (정본. 개인별 20관측 빈도 DSF pool에서 피험자만 추출)
SAMPLING_MODE = _os.environ.get("CCM_SAMPLING_MODE", "subject")
if SAMPLING_MODE not in ("mixed", "pooled", "subject"):
    raise ValueError(
        f"CCM_SAMPLING_MODE는 mixed|pooled|subject만 허용 (받은 값: {SAMPLING_MODE})"
    )
_SAMPLING_IMPL = {
    "mixed": "form_mixed",
    "pooled": "pooled_random",
    "subject": "subject_pool_random",
}[SAMPLING_MODE]

# --- 관측 grain 스위치 (2026-08-13 사용자 확정) -------------------------
# session = 행이 피험자×세션×시간창(1,240). desired가 그 시점 P9_filled = 노출조건 반응이 섞임.
# subject_frequency = ★정본. 행이 피험자(62). desired = 전체 20개 P9_filled의 개인별 최빈값.
#   상세 tie 규칙은 desired_at23.py docstring 참조(파일명은 import 호환을 위해 유지).
PERSON_GRAIN = _os.environ.get("CCM_PERSON_GRAIN", "subject_frequency")
if PERSON_GRAIN not in ("session", "subject_frequency"):
    raise ValueError(
        f"CCM_PERSON_GRAIN은 session|subject_frequency만 허용 (받은 값: {PERSON_GRAIN})"
    )

# --- 결정입력 스위치 (2026-08-04 사용자 지시) ---------------------------
# ⚠️ prediction(=TabPFN deploy) 판본은 **2026-08-04 유기 결정**이다. 산출물은
#    _internal/trash_bin/2026-08-04/ccm_tabpfn/ 으로 옮겼고 RETIRE_NOTE.md가 사유를 소유한다.
#    스위치·코드는 되살릴 수 있게 남겨 두지만, 재실행 전에 먼저 정해야 할 것이 있다:
#    개인단위 축약(PERSON_GRAIN=subject_frequency)에서 **예측치를 개인 1값으로 어떻게 접을 것인가**.
#    지금 adapter는 20행의 평균을 쓰지만 이는 잠정이며 검토된 바 없다.
# CCM_DECISION_SOURCE=prediction 이면 oracle(실측 P9_filled)을 쓰지 않고 PCM(TabPFN)
# OOF 예측치로 setpoint를 정한다 = "설문 없이 배포했을 때" 실제 경로.
#   oracle     = ground_truth    (🔒 legacy escape hatch. 비교축·기존 정본)
#   prediction = pcm_prediction  (✅ 배포 경로. 산출물은 별도 실험 폴더로 분리)
# ★ 평가(효용·4축 채점)는 두 모드 모두 항상 실측 actual로 한다 — 결정입력만 바뀐다.
#   그래야 (oracle 결과 − prediction 결과) = PCM 예측오차의 순수 전파량이 된다.
DECISION_SOURCE = _os.environ.get("CCM_DECISION_SOURCE", "oracle")
if DECISION_SOURCE not in ("oracle", "prediction"):
    raise ValueError(
        f"CCM_DECISION_SOURCE는 oracle|prediction만 허용 (받은 값: {DECISION_SOURCE})"
    )
_DECISION_IMPL = {"oracle": "ground_truth", "prediction": "pcm_prediction"}[
    DECISION_SOURCE
]
# 결과 컬럼 접미사. figure·검증이 이 값을 읽어 컬럼명을 만든다(하드코딩 금지).
SOURCE_TAG = {"oracle": "oracle", "prediction": "deploy"}[DECISION_SOURCE]

# 정본은 clip 효용 + pooled 표본. 그 밖의 조합은 variant 하위폴더로 갈라 덮어쓰기를 막는다.
_variant = ""
if UTILITY_MODE != "clip":
    _variant += f"/variant_{UTILITY_MODE}"
if SAMPLING_MODE != "subject":  # 정본이 subject로 바뀜(2026-08-04) — 그 밖이 variant
    _variant += f"/variant_{SAMPLING_MODE}"
if PERSON_GRAIN != "subject_frequency":
    _variant += f"/variant_grain_{PERSON_GRAIN}"
# prediction 모드는 아예 다른 실험 폴더로 뺀다 — oracle 산출물과 같은 트리에 두면
# 파일명이 같아 덮어쓰거나, 나중에 어느 쪽 숫자인지 헷갈린다(2026-08-04 사용자 지시).
_EXP_ROOT = "outputs" if DECISION_SOURCE == "oracle" else "outputs_tabpfn"
# 이 배포 저장소는 산출물 트리가 하나뿐이라 원본의 `_internal` 단계를 두지 않는다.
CCM_OUT_RELPATH = _EXP_ROOT + _variant

# figure는 _internal이 아니라 실험 폴더 루트 직하에 둔다(2026-07-28 사용자 지시) —
# 사람이 바로 여는 산출물이라 내부 계산물과 섞지 않는다. variant는 자기 폴더 안에 둔다.
CCM_FIG_RELPATH = _EXP_ROOT if not _variant else CCM_OUT_RELPATH + "/figures"

# figure 포맷 — 2026-07-28부터 전 figure를 벡터(SVG)로 낸다(확대·인쇄 손실 없음).
FIG_EXT = "svg"

# --- 2. 합의 탐색 격자 ------------------------------------------------
SETPOINT_MIN_C = (
    15.0  # full LUT preset과 동일; 합의 규칙은 raw desired를 임의로 자르지 않는다.
)
SETPOINT_MAX_C = 31.0
SETPOINT_STEP_C = 0.1

# Baltimore DOE Small Office 4A LUT의 15.0–31.0°C, 0.1°C 정본 격자만 정확히 조회한다.
# key가 없으면 보간·외삽하지 않고 필요한 점을 요청 파일에 기록한 뒤 중단한다.
ENERGY_MODE = "lut_exact"

# --- 3. 그룹 규모 -----------------------------------------------------
# 공유 HVAC의 실제 효용 구간(사용자 지정): 1~10명
# ★ 2026-08-04 사용자 지시("N=1~10에 대하여 300회")로 전 정수 격자 복원.
#   2026-07-28에 7점(1,2,3,4,6,8,10)으로 줄였던 이유는 계산량이었는데, 개인단위 축약으로
#   프레임이 1,240행 → 62행이 되어 그 비용 논거가 사라졌다.
GROUP_SIZES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

# --- 4. PROVISIONAL 대장 (🟡 지금 legacy 값으로 돌지만 재검토 예정) -----
# ★ 이 dict가 ARCHITECTURE.md §6.2 표의 코드측 정본이다. 문서와 항상 일치시킬 것.
#   각 값은 legacy 실측치이며, 나중에 사용자가 결과를 보고 재검토한다.
PROVISIONAL = {
    "P1": {
        "항목": "이질성 정의",
        "legacy": "그룹 내 desired SD, 3분위(tertile) 이산구간",
        "값": {"stat": "sd", "binning": "tertile", "quantiles": (1 / 3, 2 / 3)},
        "출처": "_fig_ccm_heterogeneity.py:48",
        "주의": "경계가 표본 의존적(quantile) — 표본이 바뀌면 경계도 바뀐다",
    },
    "P2": {
        "항목": "sampling 방식",
        "legacy": "demographic 혼합(1:1, 1:1:1:1) 재샘플, 그룹당 반복 R",
        "값": {"R_full": 300, "R_smoke": 300},  # ★smoke도 동일 R — 아래 SMOKE 주석 참조
        "출처": "engine form_mixed() §5 + _exp_ccm_tstar_sweep.py:32",
    },
    "P3": {
        "항목": "operational setpoint 산정",
        "legacy": "격자 1회 argmax + 동점 후보 균등 무작위 선택",
        "값": {
            "method": "grid_argmax",
            "tie_break": "uniform_random",
            "reproducibility": "sha256(desired_group + tied_grid_indices)",
        },
        "출처": "rules._argmax_tie_random() + experiment/tie-break/README.md",
        "주의": "fairness·median 등 보조축 없음. 동일 입력은 같은 고정 seed를 써 재현 가능",
    },
    "P4": {
        "항목": "형평 수식",
        "legacy": "CVaR 하위 10% 평균 효용",
        "값": {"equity": "cvar", "q": 0.10, "fairness": "1_minus_gini"},
        "출처": "engine cvar(x, q=0.10) / gini()",
        "주의": "용어 고정 — 형평(equity)=CVaR, 공정(fairness)=1−Gini",
    },
    "P5": {
        "항목": "효용 수식 (+ 하한 clip on/off)",
        "legacy": "clip(1 − |desired − setpoint| / W, 0, 1)",
        "값": {
            "form": "triangular_clip",
            "W_c": 6.0,
            "clip_mode": "clip",
            "floor": 1e-3,
        },
        "출처": "W_c=6.0은 ASHRAE 55/ISO 7730 PMV-PPD + TSV 척도 환산(2026-08-13 사용자 확정)",
        "주의": (
            "★ 2026-08-13 W_c 7.0 → 6.0 확정. 근거: 열감각투표(TSV) 1 scale unit ≈ 3°C "
            "(Wang et al., Building and Environment 138:181-193, 2018, 피인용 634) → "
            "W=6°C는 2.00 scale unit → PPD=76.8%에 대응한다. 구 3.5와 7.0은 이전 "
            "판본이다. clip은 |Δ|≥W인 사람을 utility floor로 처리하며, 이 값은 결과를 좌우하는 "
            "provisional parameter다. "
            "하한은 utility.triangular_clip에서 1e-3으로 통일한다."
        ),
    },
    "P8": {
        "항목": "효용 바닥값 (Atkinson 정의역 0<u 보장)",
        "legacy": "social.FLOOR=1e-3을 nash(가산형)·atkinson(클램프형)이 각자 적용",
        "값": {"floor": 1e-3, "적용위치": "utility.triangular_clip"},
        "출처": "2026-08-04 사용자 지시 — 'flooring은 개인 효용 자체에 넣고 rule에 넣지 마라'",
        "주의": (
            "Atkinson(1970) 각주 2는 정의역을 0<y로 못박는다. 삼각형 clip이 u=0을 만들어 "
            "그 정의역을 깨므로 ε>=1(기하·조화평균)과 Nash의 log가 0으로 붕괴한다. "
            "바닥을 효용 한 곳에 두면 utilitarian≡atkinson(ε=0)·nash≡atkinson(ε=1)이 "
            "정확히 일치한다(실측 0/24,000 불일치). 값 1e-3 자체는 미검증 — spread>2W "
            "구간의 순위를 이 값만이 정하므로 1e-2/1e-4 민감도 확인이 남아 있다."
        ),
    },
    "P7": {
        "항목": "파레토 축에서의 에너지 스케일 (효용과의 공정 비교)",
        "legacy": "없음 — 원단위 MWh를 그대로 최소화축으로 사용",
        "값": {"axis_display": (40.0, 50.0), "interval": 2.0, "normalization": None},
        "출처": "2026-07-28 사용자 제기(OPEN)",
        "주의": (
            "파레토 '지배 판정'은 각 축의 단조변환에 불변이라 스케일과 무관하다. 스케일이 "
            "바꾸는 것은 (a) 그림에서 읽히는 frontier 모양, (b) tolerance·knee 분석, "
            "(c) '에너지 1%와 효용 얼마를 맞바꾸나' 류의 tradeoff 진술이다. "
            "특히 F0c의 tolerance 열은 축을 셀내 range로 정규화하므로 이 결정에 종속된다."
        ),
    },
    "P6": {
        "항목": "effect size 수식 (N × 이질성)",
        "legacy": "effect = util_worst − maximin_worst, floor = (max−min)/2",
        "값": {"util_sp": "median", "maximin_sp": "midrange"},
        "출처": "_fig_effectsize.py:59-61",
        "주의": (
            "⚠️ legacy figure(F0)는 fig_F0_caption.md에서 스스로 'INVALID (2026-07-01)' 판정됨 — "
            "이질성을 PT(지각온도)로 잡았는데 PT는 선호가 아님. 수식은 재사용 가능하나 "
            "입력을 P9_filled로 바꿔 반드시 재실행해야 한다."
        ),
    },
}

# --- 5. 기본 선택 (교체축별로 이번 run이 쓸 구현 이름) -----------------
# registry.resolve(axis, name)에 그대로 들어간다. 바꾸려면 여기만 고친다.
DEFAULT_SELECTION = {
    "decision_source": _DECISION_IMPL,  # oracle이면 ground_truth(gated), prediction이면 pcm_prediction
    "utility": _UTILITY_IMPL,  # 🟡 P5 (UTILITY_MODE로 전환)
    "heterogeneity_binning": "tertile_sd",  # 🟡 P1
    "sampling": _SAMPLING_IMPL,  # 🟡 P2 (SAMPLING_MODE로 전환)
    "representative": "collapse_legacy",  # 🟡 P1 의존(binning 주입받음)
}

# 축 축소는 **둘 다 항상 출력**한다 (2026-07-23 사용자 지시).
AXIS_REDUCE_OUTPUTS = ("axes4", "axes2_legacy")

# --- 6. SMOKE 정의 (★재활용 가능해야 한다 — 사용자 지시) ---------------
# ⚠️ 핵심 설계: smoke를 "R을 줄인 저정밀 실행"으로 만들면 checkpoint를 full이 재사용할 수 없다
#    (config_hash가 달라지므로). 그래서 smoke는 **정밀도를 낮추지 않고**
#    vital few 축만 남긴 **부분집합**으로 정의한다 → smoke가 만든 checkpoint를 full이 그대로 재사용.
#    = "smoke 먼저 + 재활용 가능" 두 요구를 동시에 만족시키는 유일한 방법.
SMOKE = {
    "group_sizes": (2, 6),  # vital few: 최소 그룹 vs legacy 대표 N=6
    "seasons": ("annual",),  # 4계절 중 대표 1
    "rules": None,  # None = 전 규칙(규칙 간 비교가 이 연구의 본질이라 축소 금지)
    "R": 300,  # ★full과 동일 — 이래야 checkpoint 재사용됨
}


# --- 7. 완료 판정 계약 (자율 실행이 "끝났다"고 선언할 조건) -------------
# 2026-07-23 사용자 확정: 산출물 존재 + 검증 통과 + figure 눈검수.
# ★ 2026-08-10: figure 파일명을 여기 박지 않는다(사용자 지시 "이름이 바뀌어도 묶이지 않는 구조").
#   이름의 SSOT는 model/Fig_generator/figure_registry.py 한 곳이고, 여기서는 그 표에서
#   required=True인 것만 받아온다. 개명 시 이 파일은 손대지 않는다.
def _figure_required() -> tuple[str, ...]:
    """의도: figure_registry에서 완료판정 대상 figure 파일명을 가져온다.
    입력: 없음. 출력: 파일명 tuple. registry를 못 읽으면 빈 tuple(설정 파일이 import로 깨지면 안 된다).
    """
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "Fig_generator"))
    try:
        import figure_registry as _fr
    except Exception:  # registry가 없거나 깨져도 settings import 자체는 살린다
        return ()
    return _fr.required_outputs(FIG_EXT)


REQUIRED_OUTPUTS = (
    "full_p9filled.csv",  # 4축 다축 결과 (계약 D)
    *_figure_required(),  # figure 전체 — 이름은 figure_registry가 소유
    "Fig.D9_RuleParetoRate.tsv",  # 위 그림의 수치 정본 표 (registry.TABLES와 동일)
    "PROVENANCE.json",  # 선택된 구현 + provisional ID 목록 + 해시
)

# --- 8. STEP1 실행 중 발견된 누락값 (additive-only, 2026-07-24) ---------
# ★ 위 1~7절은 원안 그대로 미변경. 여기 3개는 STEP1 이식 중 "이 파일이 이미 다 갖고
#   있어야 할 값인데 빠져 있던" 것들만 추가한다(governance §5-2: 설정값은 settings.py가 소유,
#   로직 모듈은 자체 보유 금지) — _internal/governance/decisions/actions/2026-07-24-001_ccm_module_port/decision.md 참조.
SEASONS = (
    "annual",
    "spring",
    "summer",
    "fall",
    "winter",
)  # legacy SEASONS(엔진 160행)와 동일 5종. LUT의 cold/hot 추가키는 이 sweep 축이 아님(별도 극한일 분석용)
# legacy demographic 축(엔진 run_m9 인자) 동일. pooled 모드에서는 층화를 안 쓰므로
# 축이 사라진다 — 같은 계산을 3번 반복하지 않도록 단일값 ("pooled",)로 둔다.
DEMOGRAPHICS = ("sex", "age", "sexage") if SAMPLING_MODE == "mixed" else ("pooled",)
ENERGYPLUS_LUT_M9_RELPATH = "data/energyplus_lut_baltimore_4a_15.0_31.0_step0.1.json"
ENERGYPLUS_LUT_REQUEST_RELPATH = "outputs/REQUESTED_MISSING_LUT_POINTS.json"
