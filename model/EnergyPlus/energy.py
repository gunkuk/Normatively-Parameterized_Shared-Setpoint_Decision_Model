# =====================================================
# 파일명: energy.py
# 역할: 계약 F(EnergyResult)의 에너지 산출 — EnergyPlus 실측 LUT(룩업테이블) 조회.
#       매번 시뮬레이션을 돌리지 않는다. LUT 없거나 키 없으면 조용한 폴백 없이 즉시 예외.
# 입력: setpoint_c(°C 절대값), season('annual'|'spring'|'summer'|'fall'|'winter')
# 출력: 평일 occupied(08-18) 에너지(MWh)
# 의존: json, pathlib
# =====================================================
"""에너지 백엔드 — ARCHITECTURE.md 계약 F. ✅ baseline=PMV rule(개인화), LUT는 확정 구현 1종뿐이라
registry 대상이 아니다(PLAN.md STEP1 표에 @register 지시 없음 — utility/rules/sampling/binning만 대상).

full 15–31°C grid를 조회한다. LUT가 없거나 필요한 key가 비면 에너지를 추정하지 않고,
필요한 점을 명시적 request 파일에 기록한 뒤 즉시 중단한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# settings.py는 ccm 패키지 안에 있다(EnergyPlus/는 별도 폴더) — model/을 sys.path에
# 넣어 패키지-경유로 가져온다(단순 `import settings`는 pcm.settings와 이름이 겹쳐 위험).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ccm import settings  # noqa: E402

_LUT: dict[str, float] | None = None


def _setpoint_token(value: float) -> str:
    """LUT key에서 0.1°C 격자의 유효 자릿수를 보존한다."""
    token = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return token if "." in token else f"{token}.0"


def _request_path() -> Path:
    return _project_root() / settings.ENERGYPLUS_LUT_REQUEST_RELPATH


def _record_lut_request(
    *, setpoints: list[float], seasons: list[str], reason: str
) -> Path:
    """누락 LUT를 추정하지 않고 재생성에 필요한 정확한 key를 durable request로 남긴다."""
    path = _request_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    requested = {
        "setpoint_c": sorted({round(float(value), 2) for value in setpoints}),
        "seasons": sorted(set(seasons)),
        "reason": reason,
        "required_keys": sorted(
            f"{season}|{_setpoint_token(value)}"
            for season in set(seasons)
            for value in {round(float(v), 2) for v in setpoints}
        ),
        "lut_path": settings.ENERGYPLUS_LUT_M9_RELPATH,
        "resolution_c": settings.SETPOINT_STEP_C,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(requested, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
    return path


def _project_root() -> Path:
    """의도: 이 파일 기준으로 프로젝트 루트(experiments/·이 있는 곳)를 찾는다."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "data").is_dir() and (parent / "run_ccm.py").is_file():
            return parent
    raise RuntimeError("저장소 루트(run_ccm.py가 있는 폴더)를 찾을 수 없다")


def _lut() -> dict[str, float]:
    """의도: LUT를 1회만 로드해 캐시. 없거나 비어있으면 즉시 예외(§2 절대규칙 4: 조용한 fallback 금지)."""
    global _LUT
    if _LUT is None:
        p = _project_root() / settings.ENERGYPLUS_LUT_M9_RELPATH
        if not p.exists():
            full_points = [
                round(settings.SETPOINT_MIN_C + index * settings.SETPOINT_STEP_C, 2)
                for index in range(
                    round(
                        (settings.SETPOINT_MAX_C - settings.SETPOINT_MIN_C)
                        / settings.SETPOINT_STEP_C
                    )
                    + 1
                )
            ]
            request = _record_lut_request(
                setpoints=full_points,
                seasons=["annual", "spring", "summer", "fall", "winter"],
                reason="full 15–31°C LUT file is absent",
            )
            raise FileNotFoundError(
                f"full LUT 없음({p}); 명시적 재생성 요청 기록: {request}"
            )
        _LUT = json.loads(p.read_text(encoding="utf-8"))
        if not _LUT:
            raise ValueError(f"{p} 비어 있음 — LUT 재생성 필요.")
    return _LUT


def apply(setpoint_c: float, season: str) -> float:
    """의도: (setpoint, season) → 평일 occupied 에너지(MWh).
    입력: setpoint_c(15–31°C full grid 내 절대 °C), season.
    출력: MWh(float). 원본: engine `energy_eplus_c` bit-identical(클립·반올림·키 조회 순서 동일).
    """
    if settings.ENERGY_MODE == "zero_placeholder":
        return 0.0
    if settings.ENERGY_MODE != "lut_exact":
        raise ValueError(f"알 수 없는 ENERGY_MODE: {settings.ENERGY_MODE!r}")
    lut = _lut()
    raw = float(setpoint_c)
    # REAL_GRID 끝값의 부동소수점 오차는 먼저 동일한 LUT 격자점으로 정규화한다.
    # 그 밖의 값은 필요한 LUT 격자점을 요청할 뿐, 에너지 값을 추정하지 않는다.
    sp = round(round(raw / settings.SETPOINT_STEP_C) * settings.SETPOINT_STEP_C, 2)
    if not settings.SETPOINT_MIN_C <= sp <= settings.SETPOINT_MAX_C:
        request = _record_lut_request(
            setpoints=[sp], seasons=[season], reason="setpoint outside full grid"
        )
        raise ValueError(
            f"setpoint {raw:.3f}°C가 full grid 밖; 명시적 LUT 요청 기록: {request}"
        )
    key = f"{season}|{_setpoint_token(sp)}"
    if key not in lut:
        request = _record_lut_request(
            setpoints=[sp], seasons=[season], reason="missing LUT key"
        )
        raise KeyError(f"LUT key 없음: {key!r}; 명시적 재생성 요청 기록: {request}")
    return lut[key]
