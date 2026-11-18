"use client";
import { useState } from "react";
import { Button } from "./ui/button";
type Question = Record<string, any>;
export function QuestionPanel({
  question: q,
  busy,
  onAnswer,
}: {
  question: Question;
  busy: boolean;
  onAnswer: (value: number | string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const n = q.scenario.n;
  return (
    <section className="question-panel" aria-label="공유 온도 선택 질문">
      <header className="card scenario">
        <span className="eyebrow">가상 상황 · {n}명 · 한 공간</span>
        <h2>{n}명이 함께 사용할 온도를 정해주세요</h2>
        <p>{q.scenario.description}</p>
        <p>
          이 사람들의 희망 온도는{" "}
          <strong>
            {q.scenario.desired_min_c.toFixed(1)}–
            {q.scenario.desired_max_c.toFixed(1)}°C
          </strong>
          입니다. 모든 사람에게 같은 온도를 적용합니다.
        </p>
        <p className="muted">{q.scenario.provenance}</p>
      </header>
      <h2>어떤 공유 온도를 선택하시겠어요?</h2>
      <p className="muted">
        온도차이는 각자의 희망 온도와 설정 온도 간 절대 차이입니다. 작을수록
        희망 온도에 가깝습니다.
      </p>
      <div className="grid">
        {q.display_order.map((index: number, position: number) => (
          <article className="card choice" key={index}>
            <span className="eyebrow">
              {position === 0 ? "왼쪽 안" : "오른쪽 안"}
            </span>
            <div className="temperature">
              {q.temperatures[index].toFixed(1)}
              <small>°C</small>
            </div>
            <div className="difference">
              <span>{n}명의 평균 온도차이</span>
              <strong>
                {q.temperature_difference.mean_c[index].toFixed(2)}°C
              </strong>
            </div>
            <div className="difference">
              <span>가장 차이가 큰 사람의 온도차이</span>
              <strong>
                {q.temperature_difference.worst_c[index].toFixed(2)}°C
              </strong>
            </div>
            <Button disabled={busy} onClick={() => onAnswer(index)}>
              {q.temperatures[index].toFixed(1)}°C 선택
            </Button>
          </article>
        ))}
      </div>
      <details
        className="card"
        onToggle={(e) => setExpanded(e.currentTarget.open)}
      >
        <summary>익명 개인별 효용 그래프 보기</summary>
        {expanded && (
          <>
            <h3>사람마다 두 온도를 어떻게 경험할까요?</h3>
            <p className="muted">
              각 막대는 희망 온도와의 차이를 0–1의 모델 효용으로 환산한
              값입니다. 1은 희망 온도와 같음을 뜻합니다. 실제 쾌적감 측정값은
              아닙니다. 사람을 누르면 연구 자료의 상세정보가 열립니다.
            </p>
            <div className="utility-legend">
              {q.display_order.map((ix: number, pos: number) => (
                <span key={ix}>
                  <i className={pos === 0 ? "left-key" : "right-key"} />
                  {q.temperatures[ix].toFixed(1)}°C
                </span>
              ))}
            </div>
            <div
              className="utility-chart"
              aria-label="참여자별 두 선택안의 모델 효용 비교"
            >
              {q.participants.map((person: Question, i: number) => (
                <button
                  key={i}
                  className={`person-row ${selected === i ? "selected" : ""}`}
                  aria-label={`${person.label} 상세정보`}
                  aria-expanded={selected === i}
                  aria-controls="person-detail"
                  onClick={() => setSelected(selected === i ? null : i)}
                >
                  <span>{person.label}</span>
                  <span className="paired-bars">
                    {q.display_order.map((ix: number, pos: number) => (
                      <span className="utility-track" key={ix}>
                        <span
                          className={pos === 0 ? "left-fill" : "right-fill"}
                          style={{ width: `${q.utilities[ix][i] * 100}%` }}
                        />
                        <b>{q.utilities[ix][i].toFixed(3)}</b>
                      </span>
                    ))}
                  </span>
                  <span aria-hidden="true">상세 ›</span>
                </button>
              ))}
            </div>
            <p className="muted">
              모델 효용 축: 0 → 1 · 막대 길이가 길수록 희망 온도에 가깝습니다.
            </p>
            {selected !== null && (
              <aside
                id="person-detail"
                className="person-detail"
                aria-live="polite"
              >
                <h3>{q.participants[selected].label}</h3>
                <dl>
                  <div>
                    <dt>성별</dt>
                    <dd>{q.participants[selected].sex}</dd>
                  </div>
                  <div>
                    <dt>연구 당시 나이</dt>
                    <dd>{q.participants[selected].age}세</dd>
                  </div>
                  <div>
                    <dt>희망 온도</dt>
                    <dd>{q.participants[selected].desired_c.toFixed(1)}°C</dd>
                  </div>
                </dl>
                <p className="muted">
                  희망 온도는 연구에서 산출한 개인 대표값입니다. 성별과 나이는
                  설명용이며 질문 선택이나 효용 계산에 사용하지 않습니다.
                </p>
              </aside>
            )}
            <div className="equality-panel">
              <h3>사람 간 효용이 얼마나 고른가요?</h3>
              <p>
                균등도(equality)는 1−Gini로 계산합니다. 1에 가까울수록 사람
                사이의 효용 차이가 작습니다. 모두의 효용이 낮아도 균등도는 높을
                수 있습니다.
              </p>
              <div className="grid">
                {q.display_order.map((ix: number) => (
                  <p key={ix}>
                    {q.temperatures[ix].toFixed(1)}°C의 균등도{" "}
                    <strong>{q.metrics.equality[ix].toFixed(3)}</strong>
                  </p>
                ))}
              </div>
            </div>
          </>
        )}
      </details>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => onAnswer("skip")}
      >
        건너뛰기 — 선호 응답으로 사용하지 않음
      </Button>
    </section>
  );
}
