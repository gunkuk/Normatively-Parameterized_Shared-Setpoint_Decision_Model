# =====================================================
# 파일명: visual_registry.py
# 역할: CCM figure의 허용 source(oracle-only gate)와 모든 색을 단독 소유하는 색 register(SSOT).
# 입력: 없음 (figures.py·effectsize.py가 import해 읽어간다)
# 출력: 색 hex 문자열·순서 tuple·gate 예외
# 의존: matplotlib.colors
# =====================================================
"""CCM figure visual register — figure는 자기 색을 갖지 않는다.

모든 figure가 이 모듈을 import하므로, rule 계열·순서·색을 바꾸는 곳이 한 군데다.
`FIGURE_SOURCES`는 동시에 hard gate다: deployable 결과가 내부 계산표에 남아 있어도
이 register를 의도적으로 고쳐 review하기 전에는 렌더링될 수 없다.

★ 색 체계 = 3-family (2026-07-28 사용자 지시로 통합)
  1. **회색 계열(gray)** — baseline·기타 규칙(PMV·전통 4규칙·minimax_regret).
     가치판단 축이 아니므로 채도를 주지 않는다. PMV는 기준선이라 가장 진하게 고정.
  2. **Atkinson ε 계열(warm→cool ramp)** — 불평등 회피 ε=0(효율 우선, 따뜻함)에서
     ε=∞(형평 우선, 차가움)로 가는 순서형 연속 램프. 이것이 유일한 '가치판단' 축이다.
  3. **이질성 계열(green ramp)** — 집단 이질성 수준(성별 < 연령 < 성별×연령,
     effect size figure의 낮음<중간<높음)도 순서형이므로 spread 램프로 준다.

★ Atkinson 등가 규칙(핵심): utilitarian·nash·maximin은 각각 Atkinson ε=0·1·∞와
  수학적으로 같은 목적함수다. 실제 산출에서도 setpoint 차이가 각각 ≤0.037·≤0.006·0.000 °C로
  JND(0.5°C)의 1/13 이하다. 따라서 **같은 색을 준다** — 다른 색을 주면 독립 규칙처럼 읽힌다.
"""

from __future__ import annotations

from math import isinf

from matplotlib.colors import LinearSegmentedColormap, to_hex

from . import settings

# --- 0. source gate (한 run = 한 source) --------------------------------
# ★ 2026-08-04 사용자 지시로 gate 성격을 바꿨다. 이전에는 "oracle만 허용"으로 하드코딩해
#   deploy(PCM 예측 결정) panel의 우발적 재등장을 막았다. 이제는 settings의 명시적
#   스위치(CCM_DECISION_SOURCE)로만 source가 정해지고, gate는 그 선택이
#   **정확히 하나이고 등록된 값인지**를 강제한다. 즉 막는 대상이 "deploy 자체"에서
#   "암묵적·혼합 source"로 바뀌었다 — oracle과 deploy가 한 표에 섞여 어느 쪽 숫자인지
#   모르게 되는 것이 원래 막으려던 사고였고, 산출물 폴더도 모드별로 갈라져 있다.
ALLOWED_SOURCES = ("oracle", "deploy")
ANALYSIS_SOURCES = (settings.SOURCE_TAG,)
FIGURE_SOURCES = ANALYSIS_SOURCES
SOURCE_LABELS = {
    "oracle": "Oracle (실측 P9_filled로 결정)",
    "deploy": "Deploy (PCM TabPFN 예측으로 결정)",
}

# --- 0.5 모든 Pareto Figure의 기호·선 표현 규약 ---------------------------
# figure는 이 상수를 직접 참조한다. 규칙색뿐 아니라 marker·지배 상태·frontier 선도
# 여기서만 바꿔야 여러 Figure의 의미가 갈라지지 않는다.
RULE_MARKER = "o"
RULE_MARKER_EDGE_WIDTH = 1.8
NONDOMINATED_FACE = "rule_color"
DOMINATED_FACE = "none"
FRONTIER_LINESTYLE = "--"
FRONTIER_LINE_COLOR = "#555555"
PARALLEL_FRONTIER_LINESTYLE = "-"
PARALLEL_DOMINATED_LINESTYLE = "--"


# --- 1. 회색 계열 — baseline·기타 규칙 -----------------------------------
# 표시 순서일 뿐 성능 주장이 아니다. PMV는 비교 기준선이라 계열에서 가장 진한 색으로
# 고정하고, 나머지는 밝은 회색에서 중간 회색으로 가는 ramp를 준다.
PMV_COLOR = "#1f1f1f"
# minimax_regret은 2026-07-28 계산에서 제외됐다(maximin 중복) — 계열에서도 뺀다.
BASELINE_ORDER = ("mean", "median", "threshold_cov")
_GRAY_RAMP = LinearSegmentedColormap.from_list("ccm_gray", ["#c4c4c4", "#5c5c5c"])
BASELINE_COLORS = {
    name: to_hex(_GRAY_RAMP(i / (len(BASELINE_ORDER) - 1)))
    for i, name in enumerate(BASELINE_ORDER)
}

# --- 2. Atkinson ε 계열 — 유일한 가치판단 축 -----------------------------
# ε는 실질적 순서가 있다: ε=0은 공리주의(효율 우선), ε가 커질수록 불평등 회피가 강해져
# ε=∞에서 Rawls maximin이 된다. plasma 계열을 뒤집어 warm(효율)→cool(형평)으로 읽히게 했다.
# 지각적으로 균일하고 색각이상에서도 순서가 유지된다.
ATKINSON_EPS = (0.0, 0.5, 1.0, 2.0, float("inf"))
ATKINSON_LEGEND_LABELS = {
    0.5: "ε=0.5 · low inequality aversion",
    2.0: "ε=2 · high inequality aversion",
}
ATKINSON_CMAP = LinearSegmentedColormap.from_list(
    "atkinson_epsilon",
    ["#f89540", "#e16462", "#b12a90", "#6a00a8", "#2c0594"],
)
# 등가 규칙 → ε 매핑. 값이 아니라 '같은 결정규칙'이라는 사실을 색으로 말한다.
ATKINSON_ALIASES = {"utilitarian": 0.0, "nash": 1.0, "maximin": float("inf")}

# --- 3. 이질성 계열 — 집단 조건(데이터 축) --------------------------------
# 규칙이 아니라 '어떤 집단이냐'를 나타내므로 rule 계열과 겹치지 않는 녹색 ramp로 분리한다.
HETEROGENEITY_ORDER = ("sex", "age", "sexage")
_HET_RAMP = LinearSegmentedColormap.from_list(
    "ccm_heterogeneity", ["#a1d99b", "#41ab5d", "#00441b"]
)
HETEROGENEITY_COLORS = {
    name: to_hex(_HET_RAMP(i / (len(HETEROGENEITY_ORDER) - 1)))
    for i, name in enumerate(HETEROGENEITY_ORDER)
}
# effect size figure의 이질성 3구간도 같은 ramp를 쓴다(같은 개념 = 같은 색).
EFFECTSIZE_HETEROGENEITY_ORDER = ("낮음 <6°C", "중간 6~11°C", "높음 >11°C")
EFFECTSIZE_HETEROGENEITY_COLORS = {
    name: to_hex(_HET_RAMP(i / (len(EFFECTSIZE_HETEROGENEITY_ORDER) - 1)))
    for i, name in enumerate(EFFECTSIZE_HETEROGENEITY_ORDER)
}


# --- 4. 축 눈금 규약 — 파레토 그림의 축을 서로 비교 가능하게 고정 -----------
# (2026-07-28 사용자 지시) 파레토 frontier는 4축이든 2축이든 X·Y가 **같은 span·같은 간격**
# 이어야 모양을 왜곡 없이 읽는다. 축마다 제멋대로 autoscale하면 같은 데이터도 다른 곡률로
# 보이기 때문이다. 시작·끝 수치는 반드시 표시하고 0.05 배수에 맞춘다.
UTILITY_AXIS_SPAN = 0.25  # 효용계 축의 기본 span (데이터가 넘치면 0.05 단위로 확장)
UTILITY_AXIS_INTERVAL = 0.05  # 눈금 간격
UTILITY_AXIS_ROUND = 0.05  # 시작·끝 값을 맞출 격자
# 대표셀을 버리고 전 셀을 한 그림에 담으면 span이 0.25를 크게 넘는다(실측: efficiency 0.545,
# fairness 0.418, equity 1.000). 확장을 허용하되 간격은 span에 맞춰 성글게 해 눈금이
# 뭉개지지 않게 한다 — 시작·끝 표기와 0.05 배수 규칙은 그대로 유지된다.
UTILITY_AXIS_MAX_TICKS = 7  # 눈금이 이보다 많아지면 간격을 0.05씩 키운다

# ⚠️ OPEN DECISION (D-CCM-ENERGY, 2026-07-28): 에너지를 효용과 '공정하게' 비교하려면
# 어떤 스케일이어야 하는지가 아직 미정이다. 아래 40~50 MWh·간격 2는 **잠정 표시 규약**일 뿐
# 정규화 근거가 아니다. 근거·후보안은 experiment/ccm/README.md §8 참조.
ENERGY_AXIS_RANGE = (40.0, 50.0)  # 관측 최대가 50 이하인 동안 쓰는 잠정 고정 범위
ENERGY_AXIS_INTERVAL = 2.0


def utility_axis_bounds(low: float, high: float) -> tuple[float, float]:
    """의도: 데이터 범위를 감싸면서 끝값이 0.05 배수인 축을 만든다.
    입력: 그 축 데이터의 min·max.
    출력: (시작, 끝). 기본 span보다 넓으면 0.05 단위로만 늘려 데이터를 자르지 않는다.
    """
    import math

    start = math.floor(low / UTILITY_AXIS_ROUND) * UTILITY_AXIS_ROUND
    span = UTILITY_AXIS_SPAN
    while start + span < high:
        span += UTILITY_AXIS_ROUND
    return (round(start, 2), round(start + span, 2))


def utility_axis_interval(span: float) -> float:
    """의도: span에 맞는 눈금 간격을 고른다(0.05의 배수, 눈금 수 상한 준수).
    입력: 축 span.
    출력: 간격. x·y에 같은 값을 쓰려면 호출자가 둘 중 큰 span으로 한 번만 구해야 한다.
    """
    interval = UTILITY_AXIS_INTERVAL
    while span / interval > UTILITY_AXIS_MAX_TICKS:
        interval += UTILITY_AXIS_INTERVAL
    return round(interval, 2)


def axis_ticks(start: float, end: float, interval: float) -> list[float]:
    """의도: 시작~끝을 interval로 나눈 눈금 목록(끝점 포함)을 준다.
    입력: 시작·끝·간격.
    출력: float 리스트. 부동소수 누적오차를 막으려 인덱스로 만든다.
    """
    n = int(round((end - start) / interval))
    return [round(start + i * interval, 10) for i in range(n + 1)]


def enabled_sources() -> tuple[str, ...]:
    """의도: 이번 run의 결정입력 source가 '명시적으로 선택된 단 하나'임을 강제한다.
    입력: 없음 (settings.SOURCE_TAG를 읽는다).
    출력: ("oracle",) 또는 ("deploy",). 위반 시 RuntimeError로 렌더링 자체를 막는다.

    막는 것: ① 등록되지 않은 source ② 한 run에 두 source가 섞이는 것
    (섞이면 표·그림의 어느 숫자가 어느 결정입력인지 사후 판별이 불가능해진다).
    """
    if len(ANALYSIS_SOURCES) != 1 or ANALYSIS_SOURCES[0] not in ALLOWED_SOURCES:
        raise RuntimeError(
            f"CCM source gate: source는 {ALLOWED_SOURCES} 중 정확히 하나여야 한다 "
            f"(현재 {ANALYSIS_SOURCES}). CCM_DECISION_SOURCE 환경변수로만 바꾼다."
        )
    if FIGURE_SOURCES != ANALYSIS_SOURCES:
        raise RuntimeError(
            f"CCM source gate: 계산 source {ANALYSIS_SOURCES} 와 figure source "
            f"{FIGURE_SOURCES} 가 다르다 — 한 run은 한 source여야 한다"
        )
    return FIGURE_SOURCES


def atkinson_color(eps: float) -> str:
    """의도: 순서형 ε를 등록된 warm→cool ramp 위 한 점으로 옮긴다.
    입력: ε (0~4 또는 inf).
    출력: hex 색 문자열. ε=2와 ε=∞가 붙지 않게 ∞를 ramp 끝으로 따로 보낸다.
    """
    if isinf(float(eps)):
        return to_hex(ATKINSON_CMAP(1.0))
    # 유한 ε는 ramp의 앞 5/6 구간에 배치 — 마지막 1/6은 ∞ 전용으로 비워 둔다.
    position = min(1.0, max(0.0, float(eps) / 2.0)) * (4.0 / 5.0)
    return to_hex(ATKINSON_CMAP(position))


def rule_color(rule: str, eps: float | None = None) -> str:
    """의도: 어떤 figure에서 부르든 한 규칙에 항상 같은 색을 준다(색 통일의 단일 입구).
    입력: rule 이름, atkinson이면 eps.
    출력: hex 색 문자열.

    등가 규칙(utilitarian·nash·maximin)은 대응하는 Atkinson ε 색을 그대로 돌려준다.
    """
    if rule == "pmv":
        return PMV_COLOR
    if rule == "atkinson":
        if eps is None:
            raise ValueError("atkinson colour requires eps")
        return atkinson_color(eps)
    if rule in ATKINSON_ALIASES:  # 공리주의·Nash·maximin = ε 0·1·∞와 같은 규칙
        return atkinson_color(ATKINSON_ALIASES[rule])
    return BASELINE_COLORS.get(rule, "#8c8c8c")


def heterogeneity_color(name: str) -> str:
    """의도: 이질성 수준(sex/age/sexage)의 등록 색을 준다.
    입력: 이질성 키.
    출력: hex 색 문자열. 미등록 키는 계열 중간색으로 떨어뜨린다.
    """
    return HETEROGENEITY_COLORS.get(name, to_hex(_HET_RAMP(0.5)))
