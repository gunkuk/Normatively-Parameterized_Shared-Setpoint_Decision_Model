# =====================================================
# 파일명: rules.py
# 역할: 계약 B(Decision)의 분배 규칙 교체축. legacy CCM_RULES 10종(그중 atkinson은 ε격자로
#       6개 결정점 확장 → 총 15개 결정점) + PMV(Fanger) group-adaptive baseline 계산을 이식.
# 입력: 그룹의 desired 배열, REAL_GRID(격자), utility_fn(주입), eps(atkinson 전용), met_grp(pmv 전용)
# 출력: shared setpoint(°C) 스칼라
# 의존: numpy, math, social(atkinson), registry
# =====================================================
"""분배 규칙 — ARCHITECTURE.md 계약 B. 🟡 P3(격자탐색·동점처리 방식)에 전 규칙이 해당한다.

원본: `_exp_ccm_phase2_engine.py`의 `CCM_RULES`·`choose_c`·`_argmax_center`·
PMV 섹션(`_pmv_fanger`·`_met_from_demo`·`_met_for`·`pmv_setpoint_c`) — 수식·상수 불변.

★ 이식 시 구조 변경 한 가지(수식 불변, 디스패치만 변경): legacy `choose_c`는 하나의
if/elif 함수였다. registry 원칙(§5 governance 1항 "교체 가능 구현은 registry에 등록,
파이프라인은 이름으로만 부른다")에 따라 규칙마다 별도 함수로 쪼개 각각 등록했다.
그 결과 utility 행렬 U(grid×n)를 규칙마다 다시 계산하지만(legacy는 1회 공유),
grid=65점(15–31°C, 0.25°C)×n≤10명이라 비용은 무시할 수준이다.

★ CCM_RULES 개수 불일치 기록: PLAN.md STEP1 표는 "11 규칙 전부"라 적었으나, 실제 engine의
CCM_RULES는 10개다(egalitarian은 engine 자체에서 2026-07-02 T3로 폐기된 주석이 남아있음 —
"utilitarian+atkinson-ε족과 잉여"). 11이라는 숫자는 폐기 전 카운트가 PLAN 작성 시 갱신되지 않은
것으로 보인다. engine이 원본이므로 engine의 10개를 그대로 이식했다(REPORT.md에 기록).
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

from . import registry, settings
from .social import atkinson as _atkinson_w

# --- 0. 격자 (settings SSOT에서 구성) --------------------------------
# ★ 2026-08-04 수정: np.arange는 시작값에 step을 누적 가산해 격자를 만들기 때문에
#   0.1처럼 이진수로 정확히 표현 못 하는 step에서 오차가 쌓인다. 실제로 이전 판본은
#   19.0을 18.999999999999986, 27.0을 26.999999999999957로 만들었고, 그 결과
#   _argmax_center의 동점 판정(median에서 등거리인 후보 중 선택)이 5.7e-14 크기의
#   노이즈로 갈렸다 — desired=[19,27] 같은 그룹에서 setpoint가 19°C냐 27°C냐가
#   부동소수 오차로 정해졌다(8°C 차이). 실측 영향: utilitarian 결정의 5.56%,
#   nash 0.61%, threshold_cov 0.17%(1,800그룹 기준).
#   인덱스를 정수로 만든 뒤 곱하고 round하면 각 격자점이 십진값의 최근접 double이
#   되어 등거리 판정이 정확히 0으로 떨어진다.
_GRID_N = (
    int(
        round(
            (settings.SETPOINT_MAX_C - settings.SETPOINT_MIN_C)
            / settings.SETPOINT_STEP_C
        )
    )
    + 1  # 끝점 포함(arange의 half-open 구간과 달리 끝점이 확실히 들어간다)
)
REAL_GRID = np.round(
    settings.SETPOINT_MIN_C + np.arange(_GRID_N) * settings.SETPOINT_STEP_C, 10
)

# ★ minimax_regret 제외(2026-07-28 사용자 확정) — 규칙이 아니라 maximin의 중복이다.
# 개인 효용은 자기 desired에서 1로 최대이므로 regret_i(t) = 1 - U_i(t)이고,
# min_t max_i regret_i = max_t min_i U_i = 효용공간 maximin이 된다. 산출에서도 setpoint
# 차이가 max 0.213°C(JND 0.5°C 미만)뿐이며 그 잔차는 규칙 차이가 아니라 clip·tie-break
# 구현 차이다. 증명·수치는 experiment/ccm/README.md §5.1 참조.
# 함수 rule_minimax_regret은 그 증거를 재검증할 수 있도록 등록만 남겨 둔다(계산에는 불참).
# ★ 2026-08-05 중복 제거(사용자 확정): utilitarian·nash·maximin을 목록에서 뺐다.
# 이 셋은 atkinson ε=0·1·∞와 **수치적으로 완전히 동일**하다(24,000그룹 실측 0건 불일치).
#   utilitarian = Σu           ↔ ε=0  : (mean(u^1))^1 = 산술평균. argmax 동일(n 고정)
#   nash        = Σlog u       ↔ ε=1  : exp(mean(log u)) = 기하평균. 단조변환이라 argmax 동일
#   maximin     = max min u    ↔ ε=∞  : u.min(). 같은 코드 경로
# 이전에는 FLOOR를 세 곳이 서로 다르게(가산형/클램프형/없음) 적용해 0.4~0.5%가 어긋났고,
# 그 상태로 figures.py가 "같은 규칙"이라며 합쳐 평균을 냈다 — 서로 다른 두 규칙의 평균이었다.
# 바닥을 utility 한 곳으로 통합(P8)하면서 동치가 실제로 성립해, 이제 목록에서 뺀다.
# 함수 자체는 registry에 남겨 두어 동치 재검증이 가능하다(계산에는 불참).
# → 결정점 수: 4(비-atkinson) + 5(EPS_GRID) = **9개**.
CCM_RULES = [
    "pmv",
    "mean",
    "median",
    "threshold_cov",
    "atkinson",
]

# 표시용 등가 라벨 — figures가 "A0 (≡utilitarian)"처럼 병기할 때 쓴다.
ATKINSON_ALIASES = {0.0: "utilitarian", 1.0: "nash", float("inf"): "maximin"}

EPS_GRID = [0.0, 0.5, 1.0, 2.0, float("inf")]

# --- 1. PMV(Fanger) group-adaptive baseline (engine 그대로 이식) -------
PMV_CLO = 0.6  # 착의(사용자 확정 2026-07-04)
PMV_VEL = 0.2  # 기류 m/s(사용자 확정 2026-07-04)
PMV_RH = 50.0  # 상대습도 %(표준, 미측정)
OFFICE_MET_BASE = 1.1  # 착석 사무직 표준 대사량(met) — BMR-met 표본평균을 여기로 정규화


def _pmv_fanger(ta, tr, vel, rh, met, clo, wme=0.0) -> float:
    """ISO 7730 PMV 반복계산. 원본: engine `_pmv_fanger` bit-identical 이식."""
    pa = rh * 10.0 * math.exp(16.6536 - 4030.183 / (ta + 235.0))  # 수증기 분압
    icl = 0.155 * clo  # 착의 열저항
    m = met * 58.15
    w = wme * 58.15
    mw = m - w
    fcl = 1.05 + 0.645 * icl if icl > 0.078 else 1.00 + 1.29 * icl
    hcf = 12.1 * math.sqrt(vel)
    taa = ta + 273.0
    tra = tr + 273.0
    tcla = taa + (35.5 - ta) / (3.5 * icl + 0.1)
    p1 = icl * fcl
    p2 = p1 * 3.96
    p3 = p1 * 100.0
    p4 = p1 * taa
    p5 = 308.7 - 0.028 * mw + p2 * (tra / 100.0) ** 4
    xn = tcla / 100.0
    hc = hcf
    for _ in range(150):  # 착의표면온도 수렴 반복
        xf = xn
        hcn = 2.38 * abs(100.0 * xf - taa) ** 0.25
        hc = hcf if hcf > hcn else hcn
        xn = (p5 + p4 * hc - p2 * xf**4) / (100.0 + p3 * hc)
        if abs(xn - xf) <= 1e-5:
            break
    tcl = 100.0 * xn - 273.0
    hl1 = 3.05e-3 * (5733.0 - 6.99 * mw - pa)
    hl2 = 0.42 * (mw - 58.15) if mw > 58.15 else 0.0
    hl3 = 1.7e-5 * m * (5867.0 - pa)
    hl4 = 0.0014 * m * (34.0 - ta)
    hl5 = 3.96 * fcl * (xn**4 - (tra / 100.0) ** 4)
    hl6 = fcl * hc * (tcl - ta)
    ts = 0.303 * math.exp(-0.036 * m) + 0.028
    return ts * (mw - hl1 - hl2 - hl3 - hl4 - hl5 - hl6)


def _met_from_demo(age, bmi, weight, is_male) -> float:
    """age/BMI/weight/sex → met(Mifflin-St Jeor BMR / DuBois 체표면적). 원본 이식."""
    h_m = math.sqrt(weight / bmi)
    h_cm = h_m * 100.0
    bmr = 10 * weight + 6.25 * h_cm - 5 * age + (5 if is_male else -161)
    bmr_w = bmr * 4184.0 / 86400.0
    bsa = 0.007184 * weight**0.425 * h_cm**0.725
    return (bmr_w / bsa) / 58.15


def met_for(
    sex: np.ndarray, age: np.ndarray, bmi: np.ndarray, weight: np.ndarray
) -> np.ndarray:
    """의도: 표본 전체의 met 배열(1회 계산). 원본 engine `_met_for`를 배열 입력 형태로 이식
    (원본은 DataFrame 행 인자를 받았으나, adapter가 이미 배열을 넘기므로 시그니처만 조정 — 계산은 동일).
    입력: sex(1=남/0=여 or 'M'/'F' 등), age, bmi, weight — 전부 길이 n 배열.
    출력: met 배열(길이 n), [0.8, 2.0]로 클립.
    """
    sex = np.asarray(sex)
    if sex.dtype.kind in "OU":  # object/string dtype
        is_male = np.isin(
            np.char.upper(sex.astype(str)), ["M", "1", "1.0", "MALE", "남"]
        )
    else:
        # 원본 관행: 두 값 중 min을 male로(상대비교엔 무관)
        uniq = (
            np.unique(sex[~np.isnan(sex.astype(float))])
            if sex.dtype.kind == "f"
            else np.unique(sex)
        )
        is_male = sex == uniq.min()
    n = len(sex)
    raw = np.full(n, np.nan)
    for i in range(n):
        try:
            raw[i] = _met_from_demo(
                float(age[i]), float(bmi[i]), float(weight[i]), bool(is_male[i])
            )
        except Exception:
            raw[i] = np.nan
    mu = np.nanmean(raw)
    raw[np.isnan(raw)] = mu
    met = raw * (OFFICE_MET_BASE / mu)
    return np.clip(met, 0.8, 2.0)


def pmv_setpoint_c(met_grp: np.ndarray, grid: np.ndarray = REAL_GRID) -> float:
    """의도: 그룹 met 배열 → 그룹 평균 PMV=0 되는 격자 온도(°C). 원본 이식."""
    best_T, best_abs = float(grid[0]), 1e18
    for T in grid:
        mp = float(
            np.mean([_pmv_fanger(T, T, PMV_VEL, PMV_RH, m, PMV_CLO) for m in met_grp])
        )
        if abs(mp) < best_abs:
            best_abs, best_T = abs(mp), float(T)
    return best_T


# --- 2. 동점 처리 — 전 규칙 공통 무작위 선택 ----------------------------
def _argmax_tie_random(
    scores: np.ndarray, grid: np.ndarray, desired_grp: np.ndarray, tol: float = 1e-9
) -> int:
    """의도: 목적함수 최댓값을 내는 격자점이 여럿이면 그중 **하나를 균등확률로 무작위 선택**한다.
    유일하면 순수 argmax와 동일.
    입력: scores(격자별 목적함수 값), grid(격자), desired_grp(난수 seed 유도용), tol(동점 허용오차).
    출력: 선택된 격자 인덱스.

    ★ 왜 무작위인가 (2026-08-05 사용자 확정) — **규칙의 독립성 보장**:
      동점이란 그 규칙이 두 해를 정확히 동등하게 평가했다는 뜻이다. 여기서 median·중점·
      최근접 같은 **2차 기준(secondary criterion)으로 자르는 표준적 방법을 의도적으로 쓰지
      않는다.** 2차 기준을 넣으면 그 순간 "utilitarian + median"이라는 혼합 규칙이 되어,
      규칙 간 비교(이 연구의 본질)가 오염된다. 특히 중점 계열 2차 기준은 사실상 maximin·
      median 규칙을 몰래 섞는 것이라, 별도 규칙으로 이미 존재하는 것과 중복된다.
      무작위 선택은 어떤 가치판단도 주입하지 않는 유일한 선택지다.
      그룹당 R=300회 재표집으로 평균 내므로, 셀 단위 통계에서는 편향 없이 상쇄된다.

    ★ 재현성: `np.random.default_rng()`를 매번 새로 쓰면 실행마다 결과가 달라져
      checkpoint·config_hash 규율이 깨진다. 그래서 (desired 구성 + 동점 집합)에서 sha256으로
      seed를 유도한다 — 같은 입력이면 항상 같은 선택, 다른 입력끼리는 무상관.
      = "결정적이면서 편향 없는" 무작위.

    ★ 동점의 두 종류 (manuscript 보고용 — 비율은 REPORT.md 참조):
      (a) 0.1°C 해상도 문제: 연속 최적점이 격자 사이에 있어 인접 두 점이 동점.
          실제 최적해는 유일하며, 선택 오차는 최대 0.05°C.
      (b) 진짜 동점: 목적함수가 구간에서 평탄(연결)하거나 봉우리가 여럿(비연결).
          실제 최적해가 하나가 아니므로 규칙 자체가 우열을 정하지 못한다.
    """
    best = scores.max()
    tie_idx = np.flatnonzero(scores >= best - tol)
    if len(tie_idx) == 1:
        return int(tie_idx[0])
    # 그룹 구성과 동점 집합으로 seed를 유도해 결정적 재현성을 확보한다.
    digest = hashlib.sha256(
        np.asarray(desired_grp, float).tobytes() + tie_idx.astype(np.int64).tobytes()
    ).digest()[:8]
    rng = np.random.default_rng(int.from_bytes(digest, "little"))
    return int(tie_idx[rng.integers(len(tie_idx))])


# 구 이름 호환(외부에서 참조하던 곳이 있으면 그대로 동작) — 정본은 위 이름이다.
_argmax_center = _argmax_tie_random


def _U(grid: np.ndarray, desired_grp: np.ndarray, utility_fn) -> np.ndarray:
    """의도: 격자 × 개인 효용 행렬(grid, n). 매 rule 호출마다 재계산(§ 상단 설명 — 비용 무시 가능)."""
    return np.stack([utility_fn(t, desired_grp) for t in grid])


# --- 3. 규칙별 등록 함수 (전부 동일 시그니처, 미사용 kwarg는 무시) -------
# 시그니처: (desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None) -> setpoint(°C)


@registry.register("rule", "pmv", provisional="P3")
def rule_pmv(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """전통 표준: 그룹 met 구성에 맞춘 평균PMV=0 온도(개인선호 미사용). met_grp 필수 주입."""
    if met_grp is None:
        raise ValueError(
            "rule_pmv는 met_grp(그룹 met 배열)를 반드시 받아야 한다 — 조용한 폴백 없음"
        )
    return pmv_setpoint_c(met_grp, grid)


@registry.register("rule", "mean", provisional="P3")
def rule_mean(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """전통: 개인 desired 산술평균."""
    return float(np.mean(desired_grp))


@registry.register("rule", "median", provisional="P3")
def rule_median(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """전통: 중앙값."""
    return float(np.median(desired_grp))


@registry.register("rule", "utilitarian", provisional="P3")
def rule_utilitarian(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """공리주의: 총 효용(Σu_i) 최대화."""
    U = _U(grid, desired_grp, utility_fn)
    return float(grid[_argmax_tie_random(U.sum(1), grid, desired_grp)])


@registry.register("rule", "maximin", provisional="P3")
def rule_maximin(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """Rawls maximin: 최악 1인의 효용 min(u_i) 최대화 — 다른 규칙과 같은 효용 경로를 탄다.

    ★ 2026-08-05: raw-minimax(Chebyshev center) analytic 우회를 제거했다(사용자 지시).
      우회가 있던 이유: W=3.5일 때 spread>2W(=7°C)인 그룹에서 clip 때문에 min(u)가 격자
      전체에서 0이 되어(=Helly 교집합 공집합) argmax가 grid[0]=15°C에 pin됐다
      (engine 2026-07-02 A 버그). W=7.0으로 올린 뒤 그 붕괴 경계가 spread>2W(1-FLOOR)=13.99°C가
      됐는데, 코호트 desired 범위가 18~30°C라 **최대 spread 12°C < 13.99°C** — 원리적으로
      포화가 불가능하다. 실측 12,000그룹에서 우회판과 효용판의 답이 0건 불일치(최대차 0.0000°C).
      우회를 지우면 (a) 이 규칙만 W·clip에 둔감하던 비대칭이 사라지고,
      (b) atkinson(ε=∞)과 코드 경로가 완전히 같아진다.
    ⚠️ W를 다시 낮추거나 desired 범위가 넓은 코호트를 쓰면 포화가 되살아난다 — 그때는
      settings.PROVISIONAL["P5"]의 W_c를 함께 재검토해야 한다.
    """
    U = _U(grid, desired_grp, utility_fn)
    return float(grid[_argmax_tie_random(U.min(1), grid, desired_grp)])


@registry.register("rule", "nash", provisional="P3")
def rule_nash(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """Nash social welfare: Σlog(u_i) 최대화.

    ★ 2026-08-04: 규칙 안에서 바닥을 씌우던 `np.maximum(U,0)+FLOOR`(가산형)를 제거했다.
      바닥은 utility.triangular_clip이 (0,1]로 보장한다 — 사용자 지시("flooring은 개인 효용
      자체에 넣고 rule에 넣지 마라"). 이전에는 여기(가산형)와 social.atkinson(클램프형)이
      서로 다른 바닥을 써서 nash ≠ atkinson(ε=1)이 0.450%에서 발생했다. 이제 둘은
      **단조변환 관계**(Σlog u = n·log(기하평균))라 argmax가 정확히 일치한다.
    ⚠️ triangular_linear 판본은 u<=0을 낼 수 있어 log가 -inf/NaN이 된다. Atkinson과 같은
      이유로 Nash도 그 판본에서는 정의되지 않는다.
    """
    U = _U(grid, desired_grp, utility_fn)
    if U.min() <= 0:
        raise ValueError(
            f"rule_nash: 효용에 0 이하 값이 있다(min={U.min():.6g}). Nash는 log를 쓰므로 "
            "정의역이 0<u다 — triangular_clip을 쓰거나 linear 판본에서는 이 규칙을 빼라."
        )
    return float(grid[_argmax_tie_random(np.log(U).sum(1), grid, desired_grp)])


# --- 만족밴드 폭 (2026-08-05 사용자 확정: 1.0 → 3.0) ---------------------
# ★ 근거 — utility.W_DEFAULT_C(=7.0)와 **같은 문헌**을 쓴다:
#   열감각투표(TSV, Thermal Sensation Vote) 1 scale unit ≈ 중립온도 기준 약 3°C
#   (Wang et al., "Individual difference in thermal comfort: A literature review",
#    Building and Environment 138:181-193, 2018. doi:10.1016/j.buildenv.2018.04.040, 피인용 634).
#   → 밴드 ±3°C = "열감각 1단계 이내" = 같은 열감각 범주 안에 든 인원수를 센다는 뜻.
#   구 1.0°C는 desired 폭만 보고 고른 무근거 값이었다(2026-08-03).
#   W=7.0(=2.33 unit, PPD 89.3%)과 같은 척도 위에 있어 두 상수의 관계가 해석 가능해진다:
#   밴드 3°C = 1 unit(만족 경계), W 7°C = 2.33 unit(효용 0 = PPD≈90%).
THRESHOLD_COV_BAND_C = 3.0


@registry.register("rule", "threshold_cov", provisional="P3")
def rule_threshold_cov(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """만족밴드(|desired-setpoint|<=THRESHOLD_COV_BAND_C) 인원수 최대화(satisficing/coverage 계열).
    maximin과 동일하게 utility_fn(W=3.5 삼각형 clip) 우회, raw 온도차 직접 비교(2026-08-03)."""
    desired = np.asarray(desired_grp, float)
    covered = (
        (np.abs(grid[:, None] - desired[None, :]) <= THRESHOLD_COV_BAND_C)
        .sum(1)
        .astype(float)
    )
    return float(grid[_argmax_tie_random(covered, grid, desired_grp)])


@registry.register("rule", "minimax_regret", provisional="P3")
def rule_minimax_regret(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """최대 후회(regret) 최소화."""
    U = _U(grid, desired_grp, utility_fn)
    reg = U.max(0, keepdims=True) - U
    return float(grid[_argmax_tie_random(-reg.max(1), grid, desired_grp)])


@registry.register("rule", "atkinson", provisional="P3")
def rule_atkinson(desired_grp, grid, utility_fn, *, eps=1.0, met_grp=None):
    """Atkinson ε-knob: ε=0=utilitarian(산술평균), ε=1=nash(기하평균), ε→∞=maximin(최솟값).

    ★ 2026-08-05: ε=∞ 전용 raw-minimax 우회를 제거했다(사용자 지시) — 근거는 rule_maximin
      docstring 참조. 이제 모든 ε이 social.atkinson() 한 경로만 탄다(isinf는 그 안에서
      u.min()으로 처리된다).
    """
    U = _U(grid, desired_grp, utility_fn)
    W = np.array([_atkinson_w(U[i], eps) for i in range(len(grid))])
    return float(grid[_argmax_tie_random(W, grid, desired_grp)])
