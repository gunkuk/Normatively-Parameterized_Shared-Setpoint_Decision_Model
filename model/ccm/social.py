# =====================================================
# 파일명: social.py
# 역할: 계약 D(SocialValue)의 사회적 가치 집계 함수 3종 — gini(공정)·cvar(형평)·atkinson(ε-knob).
# 입력: 개인별 효용 배열
# 출력: 스칼라 집계값
# 의존: numpy
# =====================================================
"""사회적 가치 집계 — ARCHITECTURE.md 계약 D. legacy 수식 그대로(§2 절대규칙: 상수·수식 불변).

registry 등록 대상이 아니다: PLAN.md STEP1 표에 이 세 함수는 "@register" 지시가 없다
(utility·rules·sampling·binning만 명시적으로 registry 대상). 대신 rules.py가 nash·atkinson
rule 계산에, runner.py가 SocialValue 4축(efficiency=mean, fairness=1-gini, equity=cvar) 계산에
이 모듈을 직접 import해 쓴다.
"""

from __future__ import annotations

import numpy as np

# ★ 2026-08-04: 바닥값은 utility.UTILITY_FLOOR로 이관됐다(사용자 지시 — "flooring은 개인
#   효용 자체에 넣고 rule에 넣지 마라"). 근거는 utility.py 상단 주석 참조(Atkinson 정의역 0<y).
#   이 이름은 legacy 호환을 위해 남기지만 이 모듈은 더 이상 스스로 바닥을 적용하지 않는다.
from .utility import UTILITY_FLOOR as FLOOR  # noqa: F401  (구 social.FLOOR 참조 호환)


def gini(x) -> float:
    """의도: Gini 계수(불평등도, 0=완전평등~1=완전불평등). fairness = 1 - gini(x).
    입력: 효용 배열. 출력: 스칼라. 원본: engine gini() 그대로."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    if n == 0 or x.sum() <= 0:
        return 0.0
    return float((2 * (np.arange(1, n + 1) * x).sum()) / (n * x.sum()) - (n + 1) / n)


def cvar(x, q: float = 0.10) -> float:
    """의도: 하위 q분위 평균 효용(equity=CVaR_q). q=0.10 = 최악 10% 평균.
    입력: 효용 배열, q(분위, 기본 0.10). 출력: 스칼라. 원본: engine cvar() 그대로."""
    x = np.sort(np.asarray(x, float))
    k = max(1, int(np.ceil(len(x) * q)))
    return float(x[:k].mean())


def atkinson(u, eps: float) -> float:
    """의도: Atkinson 등분배등가(EDE) 사회후생. eps=0→산술평균(=utilitarian),
    eps=1→기하평균, eps→∞→최솟값(=maximin). 원본: Atkinson(1970) 식 (5).
    입력: 효용 배열(**전부 > 0 이어야 한다** — Atkinson 정의역 0<y), eps(불평등회피도).
    출력: 스칼라.

    ★ 2026-08-04: 여기서 바닥을 씌우던 `np.maximum(u, FLOOR)`를 제거했다. 바닥은
      utility.triangular_clip이 이미 보장한다. 이 함수는 정의역을 **검사만** 한다 —
      바닥을 두 겹으로 씌우면 어느 쪽이 실효인지 추적이 안 되기 때문이다.
    ⚠️ triangular_linear(민감도 판본)는 u<=0을 낼 수 있어 여기서 걸린다. 그건 버그가 아니라
      "Atkinson은 그 판본에서 정의되지 않는다"는 사실이 드러난 것이다(조용한 폴백 없음).
    """
    u = np.asarray(u, float)
    if u.size and u.min() <= 0:
        raise ValueError(
            f"atkinson: 효용에 0 이하 값이 있다(min={u.min():.6g}). Atkinson 정의역은 0<y다 "
            "— triangular_clip을 쓰거나(바닥 보장), linear 판본에서는 이 지표를 쓰지 마라."
        )
    if np.isinf(eps):
        return float(u.min())
    if abs(eps - 1) < 1e-9:  # eps=1 특이점 — 기하평균으로 극한 처리
        return float(np.exp(np.mean(np.log(u))))
    return float((np.mean(u ** (1 - eps))) ** (1 / (1 - eps)))
