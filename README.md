# CCM — Consensus Comfort Model (재현 최소 패키지)

여러 사람이 한 공간을 공유할 때, **개인별 선호 설정온도를 하나의 공유 설정온도로 합의시키는 모델**과
그 합의의 사회적 가치를 다축으로 채점하는 재현용 최소 패키지다. 입력 데이터·실행 진입점·산출물
스키마가 모두 이 저장소 안에 들어 있어, `python run_ccm.py --full` 한 줄로 결과를 재생성할 수 있다.

---

## 0. 용어 (30초, 이 문서 전체 공통)

| 용어 | 뜻 |
|---|---|
| **PCM** (Personal Comfort Model) | 개인별 선호 설정온도를 예측하는 상류 모델. **이 저장소 범위 밖**이며, 그 결과물(OOF 예측표)만 입력으로 받는다 |
| **P9_filled** | 개인이 보고한 "혼자 재실 시 원하는 설정온도"(°C). 설문 문항 P9가 숫자면 그대로, 결측이면 같은 시점의 PT로 채운 값 |
| **OOF** (out-of-fold) | 학습에 쓰이지 않은 행에 대한 예측. 낙관 편향을 막는 표준 관행 |
| **DSF** (desired setpoint frequency) | 개인 1명의 **전체 20개 P9_filled 관측의 최빈값** = 그 사람의 desired setpoint 1개. CCM의 개인 입력 |
| **shared setpoint** | 한 그룹이 실제로 쓰게 되는 단일 설정온도. CCM의 1차 산출 |
| **효용(utility) `u_i`** | 그 shared setpoint가 개인 *i*에게 주는 만족도. `clip(1 − |desired−setpoint| / W, 1e-3, 1)`, W = 6.0 °C |
| **분배 규칙(rule)** | 개인 효용 벡터를 어떤 기준으로 합쳐 setpoint를 고를 것인가의 선택지 (평균·중앙값·공리주의·Rawls 등) |
| **4축** | 한 결정을 채점하는 네 지표 — 효율(efficiency) · 공정(fairness, 1−Gini) · 형평(equity, 하위 10% CVaR) · 에너지(MWh) |

---

## 1. BLUF

- **무엇이 들어 있나**: ① DSF 입력 행렬(`data/MODEL_OOF.tsv`) ② DSF 코드 ③ CCM 코드 ④ 실행 진입점.
- **무엇을 하나**: 62명의 개인 desired setpoint를 확정한 뒤, (그룹크기 N=1~10) × (계절 5) = 50개 조건에서
  각각 300개 그룹을 무작위로 구성하고, 9가지 결정점(분배 규칙 × 불평등회피 계수)으로 shared setpoint를
  정한 다음 4축으로 채점한다.
- **왜 재현되나**: 셀별 seed·동점 seed가 결정적으로 유도되고, 입력 provenance와 실행 hash가 기록되며,
  실행마다 `PROVENANCE.json`에 선택된 구현·해시가 기록된다.
- **범위 밖**: PCM 학습 코드, 원시 생체신호, 논문 figure 생성기 — 이 저장소에 없다(§7).

---

## 2. 빠른 시작

```bash
pip install -r requirements.txt
```

```bash
python run_ccm.py --smoke
```

```bash
python run_ccm.py --full
```

- `--smoke`: 그룹크기 2·6 × annual 2셀만 (약 20초). **입력·환경 점검용.**
- `--full`: 50셀 전체. 결과는 `outputs/` 아래에 쓰인다.
- smoke가 만든 checkpoint를 full이 그대로 재사용한다 — smoke는 정밀도를 낮춘 판본이 아니라
  같은 정밀도의 **부분집합**이기 때문이다(반복수 R=300 동일).
- 의존성은 numpy·pandas·matplotlib 뿐이다. TabPFN·torch·EnergyPlus 실행파일은 필요 없다
  (에너지는 미리 계산된 LUT 조회로 처리한다 — §3).

---

## 3. 입력 데이터 (4종, 전부 `data/`)

| 파일 | 무엇인가 | 규모 |
|---|---|---|
| **`MODEL_OOF.tsv`** | **DSF의 최종 input matrix.** PCM(TabPFN 챔피언)의 OOF 예측표. `cell=="mean"` 행이 채택 행렬이며 열 `actual`=실측 P9_filled, `prediction`=OOF 예측 | 62명 · 1,240행 · 248세션 |
| `ccm_cohort62_join.tsv` | `row_id`로 join하는 신체계측·실험조건 라벨(sex/age/BMI/weight/env_pair/feature_window). PMV 규칙의 met 계산에 쓰인다 | 1,240행 |
| `ccm_p9_raw_by_row_id.tsv` | 설문 P9 **원값**. "이 행이 P9 결측이라 PT로 대체됐는가"를 판정하는 용도 | 2,560행 (P9 결측 593) |
| `energyplus_lut_baltimore_4a_15.0_31.0_step0.1.json` | setpoint(15.0~31.0 °C, 0.1 °C 간격) × 계절 → 연간 에너지(MWh) 조회표. EnergyPlus v26.1로 DOE Reference Small Office(Baltimore 4A)를 사전 시뮬레이션한 결과 | 1,127 키 |

각 입력에 대응하는 provenance 파일이 **출처·동결 시점·sha256**을 기록한다.
`ccm_cohort62_join.tsv`는 실행할 때마다 sha256을 대조하며, 불일치하면 즉시 중단한다.

> **입력 계약**: `MODEL_OOF.tsv`의 mean cell이 62명·1,240행·248세션이 아니거나 결측이 있으면
> `adapter.load()`가 예외를 던지고 멈춘다. 폴백은 없다.

---

## 4. 파이프라인 (입력에서 결과까지)

```
data/MODEL_OOF.tsv (1,240행 = 62명 × 4세션 × 5시점)
        │
        │  ① adapter.load()  — 계약 검증 + cohort 라벨 join
        ▼
   d_valid (1,240행)
        │
        │  ② DSF: desired_at23.build()  — 개인별 20관측의 최빈값
        ▼
   62명 × desired setpoint 1개
        │
        │  ③ sampling  — 셀마다 N명 그룹을 300회 무작위 구성
        ▼
   그룹 (N=1~10) × 계절(annual·spring·summer·fall·winter)
        │
        │  ④ rule  — 15.0~31.0 °C 0.1 °C 격자에서 규칙별 shared setpoint 선택
        ▼
   shared setpoint
        │
        │  ⑤ 채점  — 개인 효용 u_i(W=6.0, floor=1e-3) → 4축 + LUT 에너지 조회
        ▼
   outputs/results/*.csv · *.tsv.gz · PROVENANCE.json
```

**② DSF 동점 해소 규칙** (`model/ccm/desired_at23.py`) — 순서 고정:

1. 전체 20관측의 최빈값. 유일하면 확정 (62명 중 57명).
2. 공동 최빈값이면 그 개인의 20관측 평균에 가장 가까운 후보 (5명 중 3명 해소).
3. 평균과의 거리까지 같은 잔여 2명은 확정된 canonical override: 피험자 19 = 24 °C, 83 = 22 °C.

**④ 분배 규칙 5종 × ε 격자 = 결정점 9개**:

| 규칙 | 내용 |
|---|---|
| `pmv` | 전통 표준 baseline. 그룹 met 구성에 맞춘 평균 PMV=0 온도 (**개인 선호를 쓰지 않는다**) |
| `mean` / `median` | 개인 desired의 산술평균 / 중앙값 |
| `threshold_cov` | 만족 밴드 안에 드는 인원수 최대화 (satisficing) |
| `atkinson` (ε = 0, 0.5, 1, 2, ∞) | 불평등회피 계수 하나로 규범을 잇는 축. **ε=0 = 공리주의**(총효용 최대), **ε=1 = Nash**(기하평균), **ε→∞ = Rawls maximin**(최악 1인 보호) |

효용에 바닥값 1e-3을 두어 Atkinson의 정의역(0 < u)을 지킨다 — 그래서 ε=0·1이 각각 공리주의·Nash와
정확히 일치한다.

격자 목적함수의 동점은 median 같은 보조 기준을 넣지 않고, 그룹 구성과 동점 집합에서 SHA-256으로
seed를 유도한 결정적 균등 무작위로 선택한다.

---

## 5. 산출물 (`outputs/`, git 추적 안 함)

| 경로 | 내용 |
|---|---|
| `outputs/results/{tag}.csv` · `{tag}_summary.tsv` | 셀 × 규칙 단위 요약 (setpoint, 4축, 표준편차) |
| `outputs/results/{tag}_groups.tsv.gz` | 그룹 단위 전수 결과 |
| `outputs/results/desired_frequency_per_subject.tsv` | **DSF 결과** — 피험자별 desired setpoint |
| `outputs/results/desired_frequency_pool.tsv` · `_resolution.tsv` | DSF 확정 근거 — 전수 20관측(대체 플래그 포함), 개인별 확정 경로 |
| `outputs/results/PROVENANCE.json` | 선택된 구현·잠정값 ID·코드 지문·계약 실측치 |
| `outputs/RESULTS_SCHEMA.md` | 위 파일들의 열 정의 (실행할 때마다 자동 갱신) |
| `outputs/checkpoints/` | 셀 단위 중간 결과. 재실행 시 재사용 |

`{tag}`는 `smoke_p9filled` 또는 `full_p9filled`이다.

---

## 6. 폴더 지도

```
.
├── run_ccm.py           ★ 단일 진입점
├── requirements.txt
├── data/                입력 4종 + provenance (§3)
├── model/
│   ├── ccm/             CCM 패키지
│   │   ├── adapter.py       입력 계약 검증 + cohort join
│   │   ├── desired_at23.py  ★ DSF (개인별 최빈값 확정)
│   │   ├── rules.py         분배 규칙 (pmv·mean·median·threshold_cov·atkinson)
│   │   ├── utility.py       개인 효용 u_i
│   │   ├── social.py        사회후생 집계 (Gini·CVaR·Atkinson)
│   │   ├── sampling.py      그룹 표본 구성
│   │   ├── interpreter.py   셀 sweep 실행 + 산출물 기록
│   │   ├── montecarlo.py    잔차 블록 치환 기반 불확실성 분석 (선택 실행)
│   │   ├── registry.py      교체축 등록/해석 (rule·utility·sampling …)
│   │   ├── settings.py      ★ 모든 설정값의 단일 진실 공급원
│   │   └── …                binning · reduce · representative · sources · visual_registry
│   └── EnergyPlus/
│       └── energy.py     LUT 정확 조회 (보간·외삽 없음)
└── outputs/             실행 산출물 (§5)
```

설정을 바꾸려면 **`model/ccm/settings.py` 한 곳만** 고친다. 그 파일은 아무것도 import하지 않고
값만 갖는다(순환 의존 차단). 아직 확정되지 않은 값은 임의 기본값으로 굳히지 않고 `PROVISIONAL`
대장에 ID(P1~P8)와 근거·주의사항을 달아 등록해 두었다 — 결과 해석 시 그 목록을 먼저 보면 된다.

환경변수로 바꿀 수 있는 축(기본값이 정본):

| 변수 | 기본값 | 다른 값 |
|---|---|---|
| `CCM_PERSON_GRAIN` | `subject_frequency` (행=피험자 62) | `session` (행=피험자×세션×시점 1,240) |
| `CCM_SAMPLING_MODE` | `subject` | `pooled` · `mixed`(성별/연령 층화) |
| `CCM_DECISION_SOURCE` | `oracle` (실측 P9_filled로 결정) | `prediction` (PCM 예측치로 결정) |

`oracle`과 `prediction`의 차이가 곧 **PCM 예측오차가 합의 결과로 전파된 양**이다 — 채점은 두 모드
모두 항상 실측값으로 하고 결정입력만 바뀐다. 다만 `prediction` 경로는 개인 1값으로 접는 집계 방식이
미확정(잠정)이므로 그대로 해석하지 말 것.

---

## 7. 범위 밖 (여기 없는 것)

- **PCM 학습 코드와 원시 데이터** — 생체신호 원본(수십 GB)과 TabPFN 학습 파이프라인. 이 저장소는
  그 결과인 `MODEL_OOF.tsv`만 받는다.
- **논문 figure 생성기** — 별도 모듈이며 여기 포함하지 않았다. 수치 정본은 `outputs/results/`에 있다.
- **`data.xlsx` 원본 설문** — 필요한 P9 한 열만 동결본으로 떼어 왔다.

## 8. 원본 프로젝트(C-PCM)와의 코드 차이

동일 코드에서 잘라 왔고, 배포용 경로를 사용한다. 현재 canonical 실행값에 맞춰 group-level 지표는
12자리까지 보존한다.

| 파일 | 변경 |
|---|---|
| `model/ccm/settings.py` | `PCM_OOF_RELPATH`·LUT 경로를 `data/`로, 산출물 root를 `outputs/`로 (원본은 `experiment/…` 트리) |
| `adapter.py` · `interpreter.py` · `energy.py` | 저장소 루트 탐지 표식을 `CLAUDE.md` → `run_ccm.py`로 |

동일성 확인: 이 저장소의 `outputs/results/desired_frequency_per_subject.tsv`(DSF 62행)가 원본
프로젝트의 같은 산출물과 값이 일치한다.

## 9. 라이선스와 귀속

- 코드와 관련 문서: [MIT License](LICENSE), © 2026 `gunkuk`
- `data/`의 프로젝트 데이터: [CC BY 4.0](LICENSE-DATA), 귀속 `황예원·국건·정다현`

데이터를 수정·재배포할 때는 원 귀속, 라이선스 링크, 변경 여부를 함께 표시한다. EnergyPlus·DOE
기반 LUT처럼 제3자 출처가 있는 자료는 개별 provenance의 원출처 고지도 함께 유지한다.
