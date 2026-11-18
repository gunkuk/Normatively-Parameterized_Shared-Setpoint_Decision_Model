"use client";
import { FigureFrame } from "./figure";
type Data = Record<string, any>;
const number = (value: number | null) =>
  value === null ? "∞" : Number(value).toFixed(2);
const intervals = (data: Data) =>
  (data.credible_set ?? [])
    .map(([a, b]: [number, number | null]) => `[${number(a)}, ${number(b)}]`)
    .join(" ∪ ");

export function PosteriorChart({ data }: { data: Data }) {
  const weights: number[] = data.weights ?? [];
  const maximum = Math.max(...weights, 0.001);
  const x = (q: number) => 76 + q * 820;
  const y = (p: number) => 250 - (p / maximum) * 180;
  const identified = data.status !== "UNIDENTIFIED";
  const selected = (node: number) =>
    data.credible_set?.some(
      ([lo, hi]: [number, number | null]) =>
        node >= lo && (hi === null || node <= hi),
    );
  return (
    <div className="posterior-plot">
      <svg
        viewBox="0 0 960 350"
        role="img"
        aria-label="사후확률 질량과 ε 신용집합. 가로축은 q=ε/(1+ε) 변환 좌표입니다."
      >
        <text x="76" y="27" fontSize="18">
          {identified ? "사후확률 질량" : "사전확률 질량"} / 적분 셀 (%)
        </text>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1="76"
              x2="896"
              y1={y(f * maximum)}
              y2={y(f * maximum)}
              stroke="#d7e0e2"
            />
            <text x="63" y={y(f * maximum) + 6} textAnchor="end" fontSize="17">
              {(100 * f * maximum).toFixed(1)}
            </text>
          </g>
        ))}
        {weights.map((w, i) => (
          <rect
            key={i}
            x={x(i / weights.length) + 1}
            y={y(w)}
            width={Math.max(1, 820 / weights.length - 2)}
            height={250 - y(w)}
            fill={identified && selected(data.nodes[i]) ? "#086b62" : "#a1aeb5"}
          >
            <title>
              ε {number(data.nodes[i])}: {(100 * w).toFixed(3)}%
            </title>
          </rect>
        ))}
        {identified && (
          <line
            x1={x(data.median / (1 + data.median))}
            x2={x(data.median / (1 + data.median))}
            y1="57"
            y2="250"
            stroke="#172b37"
            strokeDasharray="5 4"
            strokeWidth="2"
          />
        )}
        {[0, 0.25, 0.5, 0.75, 1].map((q, i) => (
          <g key={q}>
            <line x1={x(q)} x2={x(q)} y1="250" y2="257" stroke="#172b37" />
            <text x={x(q)} y="279" textAnchor="middle" fontSize="19">
              {["0", "⅓", "1", "3", "∞"][i]}
            </text>
          </g>
        ))}
        <text x="486" y="309" textAnchor="middle" fontSize="18">
          불평등 회피 계수 ε · q = ε / (1 + ε) 변환 축
        </text>
        <text x="76" y="340" fontSize="16">
          작은 ε: 평균 효용 중시
        </text>
        <text x="896" y="340" textAnchor="end" fontSize="16">
          큰 ε: 낮은 효용을 더 중시
        </text>
      </svg>
      <p className="plot-legend">
        {identified
          ? "■ 녹색: 신용집합에 포함된 셀 · 회색: 나머지 셀 · 점선: 사후 중앙값"
          : "■ 회색: 응답 전 사전분포 · 아직 개인의 선호를 추정하지 않았습니다."}
      </p>
    </div>
  );
}

export function ResultFigure({
  result,
  count,
}: {
  result: Data;
  count: number;
}) {
  const data = result.common;
  const identified = data.status !== "UNIDENTIFIED";
  const contextual = result.stage === "CONTEXTUAL";
  return (
    <FigureFrame title="결과">
      <header className="figure-heading">
        <span className="eyebrow">
          선호 추정 결과 · {count}개 유효 응답 ·{" "}
          {contextual ? "구간별 추정" : "공통 기준 추정"}
        </span>
        <h2>
          {contextual
            ? "상황에 따라 달라지는 선택 기준"
            : "공유 온도를 선택하는 나의 기준"}
        </h2>
        <p>
          두 온도 중 선택한 기록을 바탕으로, 평균 효용과 낮은 효용을 얼마나
          중시하는지 추정합니다.
        </p>
      </header>
      <div className="result-stat-grid">
        <div>
          <span>
            {contextual
              ? "공통 비교 기준 · 사후 중앙값"
              : "공통 ε · 사후 중앙값"}
          </span>
          <strong>{identified ? number(data.median) : "미식별"}</strong>
          <small>
            {identified
              ? "모형에 조건부인 잠정 추정"
              : "응답을 선택하면 추정이 시작됩니다"}
          </small>
        </div>
        <div>
          <span>
            {(100 * data.requested_mass).toFixed(0)}% 베이지안 신용집합
          </span>
          <strong className="interval-value">
            {identified ? intervals(data) : "아직 보고하지 않음"}
          </strong>
          <small>
            {identified
              ? `선택된 셀의 실제 확률 질량 ${(100 * data.attained_mass).toFixed(1)}% · 분리된 구간은 ∪로 표시`
              : "사전분포의 중앙값을 개인의 추정값으로 제시하지 않습니다"}
          </small>
        </div>
      </div>
      <PosteriorChart data={data} />
      {identified && data.warnings?.length > 0 && (
        <p className="result-caution">
          {data.warnings.includes("BOUNDARY_TAIL_UNIDENTIFIED") &&
            "신용집합이 경계에 닿아 꼬리 영역이 충분히 식별되지 않았습니다. "}
          {data.warnings.includes("MULTIMODAL_CREDIBLE_SET") &&
            "신용집합은 여러 구간으로 나뉩니다."}
        </p>
      )}
      {contextual && (
        <section className="context-summary">
          <h3>구간별 ε · 숫자는 사후 중앙값</h3>
          <p>
            각 칸은 인원수(N)와 희망 온도 이질성 구간(H)의 조합입니다. 미식별
            칸에는 숫자를 부여하지 않습니다.
          </p>
          <div className="heatmap">
            {Object.entries(result.grids).map(([key, value]) => {
              const v = value as Data;
              return (
                <div className="cell" key={key}>
                  <span>{key}</span>
                  <strong>
                    {v.status === "UNIDENTIFIED" ? "미식별" : number(v.median)}
                  </strong>
                </div>
              );
            })}
          </div>
          <p>
            위 공통 분포는 비교 기준입니다. 구간별 정책과 전체 구간에 적용할
            고정 ε 정책은 별도로 검토합니다.
          </p>
        </section>
      )}
      <footer className="figure-footnote">
        ε는 정답이나 성향 점수가 아닙니다. 신용집합은 엄격한 일관성 구간과
        다릅니다. 사전분포·응답 모형에 의존하며 현장 보정 전입니다.
      </footer>
    </FigureFrame>
  );
}
