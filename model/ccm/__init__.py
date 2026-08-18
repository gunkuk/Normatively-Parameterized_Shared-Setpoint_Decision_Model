# =====================================================
# 파일명: __init__.py
# 역할: ccm 패키지 진입점. 하위 로직 모듈을 전부 import해 registry에 @register 등록을 강제한다.
# 입력: 없음
# 출력: 없음 (import 시점의 부수효과 — registry 채움)
# 의존: 하위 모듈 전부
# =====================================================
"""C-PCM CCM(Consensus Comfort Model) 모듈 패키지.

★ 이 파일이 없으면 `python -c "import ccm.registry as r; print(r.describe())"`
(PLAN.md verify 1)이 빈 registry를 보여준다 — `import ccm.registry`는 먼저 `ccm` 패키지의
`__init__`을 실행하는데, 그 실행이 아래 import들을 포함해야 각 모듈의 `@registry.register(...)`
데코레이터가 실제로 실행되기 때문이다(pcm/__init__.py와 동일 관행).

표준 실행 순서는 STEP2 adapter → STEP3 runner이며, 이 파일 자체는 조립하지 않는다
(모듈 등록만 보장 — pcm의 `build()`에 해당하는 것은 runner.py의 CLI가 맡는다).
"""

from __future__ import annotations

from . import (  # noqa: F401  (import만으로 @register 부수효과를 일으킨다)
    binning,
    reduce,
    registry,
    representative,
    rules,
    sampling,
    settings,
    social,
    sources,
    utility,
)

# energy는 registry 대상이 아니라(LUT 고정 구현 1종) 여기 강제-import 목록에 없다 —
# EnergyPlus/ 폴더로 분리 이동(2026-08-03)했고, 필요한 곳(interpreter.py)만 직접 import한다.

__all__ = [
    "registry",
    "settings",
    "sources",
    "utility",
    "social",
    "rules",
    "sampling",
    "binning",
    "reduce",
    "representative",
]
