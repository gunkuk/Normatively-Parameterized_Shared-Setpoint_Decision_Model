# =====================================================
# 파일명: registry.py
# 역할: CCM의 모든 교체축(분배규칙·효용·이질성binning·축축소·대표선정·결정입력원)을
#        이름으로 등록·조회하는 단일 registry. legacy gate와 잠정(provisional) 추적을 강제한다.
# 입력: 각 모듈이 @register 데코레이터로 자기 구현을 등록
# 출력: resolve()가 구현 함수를 반환. 위반 시 예외(조용한 fallback 절대 없음)
# 의존: 없음 (표준 라이브러리만 — 순환 import 방지)
# =====================================================
"""교체축 registry — 이 파일이 CCM '변경 격리'의 심장이다.

왜 필요한가: CCM은 확정된 것(8건)보다 **바뀔 수 있는 것(41건)이 훨씬 많다**.
Parnas의 정보은닉 원칙대로 "바뀔 가능성이 높은 것을 모듈 경계 뒤에 숨기려면",
구현을 직접 호출하지 않고 **이름으로만** 부르게 만들어야 한다.
그러면 구현을 통째로 갈아도 파이프라인은 코드 수정이 0이다(개방-폐쇄 원칙).

세 가지 상태를 구분한다 (ARCHITECTURE.md §6.1):
  - 일반      : 확정된 구현. 그냥 쓴다.
  - PROVISIONAL(🟡): legacy 값으로 지금 돌아가지만 **나중에 재검토 예정**.
                     돌아가되 provenance에 반드시 표기되어 '확정된 것처럼' 굳는 것을 막는다.
  - LEGACY(🔒) : 재활용 참조 전용. 실행 경로에서 부르면 **즉시 예외**.
                 (예: ground_truth oracle — PCM 예측 없이 정답을 직접 넣는 것은
                  '설문 없이 예측'이라는 프로젝트 목적에 정면으로 반한다.)
"""

from __future__ import annotations

# 축 이름 → {구현 이름 → 등록정보}
# 축(axis)은 ARCHITECTURE.md의 ⚙️ 교체축과 1:1 대응한다.
_REGISTRY: dict[str, dict[str, dict]] = {}


def register(
    axis: str, name: str, *, legacy: bool = False, provisional: str | None = None
):
    """의도: 한 교체축에 구현 하나를 이름으로 등록한다.
    입력: axis(교체축 이름), name(구현 이름), legacy(실행금지 여부),
          provisional(잠정이면 대장 ID 'P1'~'P6', 확정이면 None).
    출력: 데코레이터. 원본 함수를 그대로 돌려주므로 직접 호출도 가능하다.

    legacy=True와 provisional은 동시에 쓰지 않는다 — legacy는 아예 못 돌고,
    provisional은 돌긴 돌기 때문이다(§6.1 2단계 상태 체계).
    """
    if legacy and provisional:
        raise ValueError(
            f"{axis}.{name}: legacy와 provisional은 배타적이다 (돌 수 없는 것에 잠정 표기는 무의미)"
        )

    def deco(fn):
        _REGISTRY.setdefault(axis, {})[name] = {
            "fn": fn,
            "legacy": legacy,
            "provisional": provisional,
        }
        return fn

    return deco


def resolve(axis: str, name: str, *, allow_legacy: bool = False):
    """의도: 이름으로 구현을 찾아 반환한다. 계약 위반이면 **즉시 죽인다**.
    입력: axis, name, allow_legacy(legacy 구현을 의도적으로 쓸 때만 True).
    출력: 등록된 함수.

    ★ 조용한 fallback을 절대 하지 않는다. 이름이 틀렸는데 기본값으로 넘어가면
    '엉뚱한 설정으로 몇 시간 돌린 결과'를 진짜인 줄 알고 논문에 쓰게 된다(configuration debt).
    """
    if axis not in _REGISTRY:
        raise KeyError(
            f"등록되지 않은 교체축: {axis!r} (등록된 축: {sorted(_REGISTRY)})"
        )
    if name not in _REGISTRY[axis]:
        raise KeyError(
            f"{axis!r} 축에 {name!r} 구현이 없다 (등록된 것: {sorted(_REGISTRY[axis])})"
        )

    entry = _REGISTRY[axis][name]
    if entry["legacy"] and not allow_legacy:
        raise RuntimeError(
            f"{axis}.{name}은(는) 🔒 LEGACY·GATED다 — 실행 경로에서 쓸 수 없다(코드 참조 전용). "
            f"의도적으로 쓰려면 resolve(..., allow_legacy=True)를 명시할 것. "
            f"근거: ARCHITECTURE.md §6.1"
        )
    return entry["fn"]


def provisional_ids(selections: dict[str, str]) -> list[str]:
    """의도: 이번 run이 선택한 구현들 중 잠정(🟡)인 것의 대장 ID를 모은다.
    입력: {axis: name} 이번 run의 선택.
    출력: 정렬된 대장 ID 목록 (예: ['P1', 'P4', 'P5']).

    이 목록이 모든 산출물 provenance에 박힌다 → 몇 달 뒤 결과 파일만 봐도
    "이 수치는 어떤 잠정값 위에서 나왔나"를 즉시 안다(ARCHITECTURE.md §6.5-2).
    """
    ids = set()
    for axis, name in selections.items():
        entry = _REGISTRY.get(axis, {}).get(name)
        if entry and entry["provisional"]:
            ids.add(entry["provisional"])
    return sorted(ids)


def describe() -> dict[str, dict[str, dict]]:
    """의도: 등록 현황 전체를 반환한다(보고서·디버깅용). 함수 객체는 뺀다."""
    return {
        axis: {
            name: {"legacy": e["legacy"], "provisional": e["provisional"]}
            for name, e in impls.items()
        }
        for axis, impls in _REGISTRY.items()
    }
