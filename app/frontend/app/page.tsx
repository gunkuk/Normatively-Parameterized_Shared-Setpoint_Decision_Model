"use client";
import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ResultFigure } from "@/components/result";
import { QuestionPanel } from "@/components/question";
type Json = Record<string, any>;
const navigation = [
  { label: "시작 안내", pages: ["Overview"] },
  { label: "선호 추정", pages: ["Elicitation"] },
  {
    label: "운영",
    pages: ["Operation", "Policies", "Buildings / Zones", "Data ingest"],
  },
  {
    label: "분석·관리",
    pages: ["Analytics", "Research / Quality", "Settings / Roles"],
  },
];
const pageNames: Record<string, string> = {
  Operation: "온도 권고",
  Policies: "정책",
  "Buildings / Zones": "공간",
  "Data ingest": "사람·희망 온도 등록",
  Analytics: "운영 분석",
  "Research / Quality": "연구·품질",
  "Settings / Roles": "설정·권한",
};
function DemoEntry({
  busy,
  admin,
  onDemo,
}: {
  busy: boolean;
  admin: boolean;
  onDemo: () => void;
}) {
  return (
    <div className="notice demo-entry">
      <strong>DEMO · 가상 데이터로 온도 권고 체험</strong>
      <p>
        가상 재실자와 희망 온도를 자동으로 등록하고, 예시 정책(ε = 1)으로 권고
        온도를 계산합니다.
      </p>
      {admin ? (
        <Button disabled={busy} onClick={onDemo}>
          예시 정책 승인 후 DEMO 실행
        </Button>
      ) : (
        <p>
          예시 정책 승인은 관리자 권한이 필요합니다. 승인 정책이 있다면 운영
          화면에서 공간 선택 → DEMO → 가상 데이터 생성 → 권고 온도 계산 순서로
          진행하세요.
        </p>
      )}
    </div>
  );
}
function Detail({ data }: { data: unknown }) {
  return (
    <details>
      <summary>근거·원자료 보기</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}
export default function Home() {
  const [token, setToken] = useState("");
  const [entry, setEntry] = useState("");
  const [user, setUser] = useState<Json | null>(null);
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [zones, setZones] = useState<Json[]>([]);
  const [zone, setZone] = useState("");
  const [policies, setPolicies] = useState<Json[]>([]);
  const [policy, setPolicy] = useState("");
  const [mode, setMode] = useState("DEMO");
  const [session, setSession] = useState("");
  const [sessionInput, setSessionInput] = useState("");
  const [state, setState] = useState<Json | null>(null);
  const [result, setResult] = useState<Json | null>(null);
  const [decision, setDecision] = useState<Json | null>(null);
  const [history, setHistory] = useState<Json[]>([]);
  const [report, setReport] = useState<Json | null>(null);
  const [settings, setSettings] = useState<Json | null>(null);
  const [budget, setBudget] = useState("300");
  const [now, setNow] = useState(() => Date.now());
  const [period, setPeriod] = useState("daily");
  const [weightMode, setWeightMode] = useState("uniform_grid");
  const [weightJson, setWeightJson] = useState("{}");
  const [epsilon, setEpsilon] = useState("1");
  const [kind, setKind] = useState("COMMON_FIXED");
  const [gridEps, setGridEps] = useState("{}");
  const [fallback, setFallback] = useState("");
  const [name, setName] = useState("연구실 공유 공간");
  const [site, setSite] = useState("Research building");
  const [domain, setDomain] = useState("preferences");
  const [payload, setPayload] = useState("[]");
  const [format, setFormat] = useState("JSON");
  const [actionValue, setActionValue] = useState("");
  const [note, setNote] = useState("");
  const [at, setAt] = useState("");
  const [message, setMessage] = useState("");
  const api = useCallback(
    async (path: string, method = "GET", body?: unknown, raw = false) => {
      const response = await fetch(`/api/v1${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": raw ? "text/plain" : "application/json",
        },
        body:
          body === undefined
            ? undefined
            : raw
              ? String(body)
              : JSON.stringify(body),
      });
      if (!response.ok) {
        const e = await response
          .json()
          .catch(() => ({ detail: response.statusText }));
        throw Error(
          typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
        );
      }
      return response.json();
    },
    [token],
  );
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    const z = await api("/sites/zones");
    setZones(z);
    if (!zone && z.length) setZone(z[0].id);
    const p = await api("/policies");
    setPolicies(p);
    if (!policy && p.length) setPolicy(p[0].id);
    setHistory(await api("/operations/history"));
  }
  useEffect(() => {
    if (token)
      run(async () => {
        setUser(await api("/me"));
        await refresh();
        setSettings(await api("/settings"));
      });
  }, [token]);
  useEffect(() => {
    if (!session || !["COMPUTING", "READY"].includes(state?.status ?? ""))
      return;
    const timer = setInterval(() => {
      api(`/elicitation/${session}/next-or-response`)
        .then(setState)
        .catch((e) => setError(e.message));
    }, 2500);
    return () => clearInterval(timer);
  }, [session, state?.status, api]);
  const activeSession = ["READY", "IDLE", "COMPUTING"].includes(state?.status);
  const deadline = state?.time_budget_seconds
    ? Date.parse(state.created_at) + state.time_budget_seconds * 1000
    : null;
  const remaining =
    deadline === null ? null : Math.max(0, Math.ceil((deadline - now) / 1000));
  useEffect(() => {
    if (!activeSession || deadline === null) return;
    setNow(Date.now());
    const tick = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(tick);
  }, [activeSession, deadline]);
  async function next() {
    setState(await api(`/elicitation/${session}/next-or-response`));
  }
  async function answer(response: number | string) {
    try {
      await api(`/elicitation/${session}/next-or-response`, "POST", {
        question_id: state?.question.id,
        response,
        request_id: crypto.randomUUID(),
      });
    } catch (error) {
      await next();
      throw error;
    }
    setResult(await api(`/elicitation/${session}/results`));
    await next();
  }
  async function startDemo() {
    const z = await api("/sites/zones", "POST", {
      site_name: "가상 체험 건물",
      name: "첫 체험 공간",
    });
    const p = await api("/policies/draft", "POST", {
      zone_id: z.id,
      kind: "COMMON_FIXED",
      epsilon: 1,
      fallback_epsilon: 1,
      rationale:
        "사용자가 예시 정책 승인 후 DEMO 실행을 선택함. 추정값이 아닌 체험용 기준.",
    });
    await api(`/policies/${p.id}/approve`, "POST");
    const data = await api(`/demo/seed?zone_id=${z.id}`, "POST");
    const d = await api("/operations/decide", "POST", {
      zone_id: z.id,
      policy_id: p.id,
      operation_mode: "DEMO",
      at: data.at,
    });
    await refresh();
    setZone(z.id);
    setPolicy(p.id);
    setMode("DEMO");
    setAt(data.at);
    setDecision(d);
    setTab("Operation");
    setMessage(
      "가상 체험을 준비했습니다. 아래 권고를 확인하고 승인·적용 기록 흐름을 체험하세요.",
    );
  }
  async function exportRun() {
    const r = await fetch(`/api/v1/exports/${session}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) throw Error("Export failed");
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `npsdm-${session}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  }
  if (!user)
    return (
      <main className="login card">
        <div className="eyebrow">NORMATIVE DECISION SUPPORT</div>
        <h1>NPSDM Console</h1>
        <p>공유 온도 결정의 근거와 운용 이력을 한곳에서 관리합니다.</p>
        <label htmlFor="access">로컬 접근 토큰</label>
        <input
          id="access"
          type="password"
          value={entry}
          onChange={(e) => setEntry(e.target.value)}
          autoComplete="off"
        />
        <p className="muted">
          관리자가 발급한 토큰을 입력하세요. 토큰은 현재 화면 메모리에만
          보관합니다.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <Button disabled={busy || !entry} onClick={() => setToken(entry)}>
          콘솔 연결
        </Button>
      </main>
    );
  const q = state?.question;
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">NPSDM</div>
        <div className="subtitle">OPERATOR CONSOLE / 01</div>
        <nav className="nav" aria-label="주 메뉴">
          {navigation.map(({ label, pages }) => (
            <button
              key={label}
              className={pages.includes(tab) ? "active" : ""}
              aria-current={pages.includes(tab) ? "true" : undefined}
              onClick={() => setTab(pages[0])}
            >
              {label}
            </button>
          ))}
        </nav>
        <footer>
          Human-approved decisions
          <br />
          No autonomous HVAC actuation
          <br />
          {user.role} · {user.tenant}
        </footer>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">SHARED SETPOINT DECISION MODEL</div>
            <h1>{tab}</h1>
          </div>
          <div>
            <span className={`badge ${mode === "DEMO" ? "demo" : ""}`}>
              {mode} · {mode === "DEMO" ? "SIMULATED" : "ACTUAL"}
            </span>
            <Button
              variant="outline"
              onClick={() => {
                setUser(null);
                setToken("");
                setEntry("");
              }}
            >
              로그아웃
            </Button>
          </div>
        </header>
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        {message && (
          <div role="status" className="notice">
            {message}
          </div>
        )}
        {navigation
          .filter(
            (group) => group.pages.length > 1 && group.pages.includes(tab),
          )
          .map((group) => (
            <nav
              key={group.label}
              className="workspace-nav actions"
              aria-label={group.label + " 세부 메뉴"}
            >
              {group.pages.map((page) => (
                <Button
                  key={page}
                  variant={tab === page ? "default" : "outline"}
                  aria-current={tab === page ? "page" : undefined}
                  onClick={() => setTab(page)}
                >
                  {pageNames[page]}
                </Button>
              ))}
            </nav>
          ))}
        {tab === "Overview" && (
          <>
            <section className="card welcome">
              <span className="eyebrow">처음 사용하는 분을 위한 안내</span>
              <h2>서로 다른 희망 온도, 하나의 공유 온도</h2>
              <p>
                어떤 사람은 22°C를, 다른 사람은 26°C를 원할 때 모두에게 같은
                온도를 적용해야 합니다. 이 앱은{" "}
                <strong>누구의 불편을 얼마나 우선할지</strong> 당신의 선택으로
                알아보고, 그 기준으로 공간의 권고 온도를 계산합니다.
              </p>
              <p>
                결과는 자동 제어 명령이 아닙니다. 운영자가 검토하고 승인한 뒤
                적용 여부를 따로 기록합니다.
              </p>
              <div className="actions">
                <Button
                  onClick={() =>
                    run(async () => {
                      const s = await api("/elicitation/sessions", "POST", {
                        time_budget_seconds: 300,
                        seed: 17,
                      });
                      setSession(s.id);
                      setState(s);
                      setResult(null);
                      setTab("Elicitation");
                    })
                  }
                >
                  데이터 없이 첫 질문 체험
                </Button>
                <Button
                  variant="outline"
                  disabled={busy || user.role !== "Admin"}
                  onClick={() => run(startDemo)}
                >
                  예시 정책 승인 후 DEMO 실행
                </Button>
              </div>
              <p className="muted">
                DEMO 버튼은 ε=1인 예시 정책을 승인하고 가상 데이터로 한 번
                계산합니다. 선호 추정 결과가 아니며 실제 설비나 실제 관측에
                영향을 주지 않습니다. Admin 권한이 필요합니다.
              </p>
            </section>
            <div className="grid">
              <section className="card">
                <h2>이 앱에서 얻게 되는 것</h2>
                <p>
                  <strong>① 선택 기준 ε</strong>
                  <br />
                  평균과 가장 불리한 사람 사이에서 어떤 결정을 선호하는지
                  나타냅니다. 정답이나 성향 점수가 아닙니다.
                </p>
                <p>
                  <strong>② 권고 온도</strong>
                  <br />
                  현재 사람들의 희망 온도와 승인한 기준을 이용해 계산합니다.
                </p>
                <p>
                  <strong>③ 결정의 근거와 이력</strong>
                  <br />
                  권고·승인·실제 적용 보고·실내 측정값을 각각 확인합니다.
                </p>
              </section>
              <section className="card">
                <h2>지금 시작하려면</h2>
                <p>
                  선호 질문만 체험하려면 준비물이 없습니다. 실제 운영에는 공간
                  정보, 현재 재실자와 각자의 최근 희망 온도가 필요합니다.
                </p>
                <p className="notice">
                  가상 데이터(DEMO)로 흐름을 익힌 뒤 실제 데이터를 등록하세요.
                  실내 온도만으로는 재실자의 희망 온도를 알 수 없습니다.
                </p>
                <p className="muted">
                  현재 등록: 공간 {zones.length}개 · 정책 {policies.length}개 ·
                  결정 {history.length}건
                </p>
              </section>
            </div>
            <section className="card">
              <h2>처음부터 실제 운영까지</h2>
              <ol className="onboarding">
                {[
                  [
                    "1",
                    "선호 선택",
                    "Elicitation",
                    "가상 그룹의 두 온도 중 하나를 선택합니다. 답변에서 공통 기준을 추정하고, 필요한 경우 그룹별 기준을 따로 보여줍니다.",
                  ],
                  [
                    "2",
                    "공간 만들기",
                    "Buildings / Zones",
                    "건물·공간과 허용 온도 범위를 등록합니다. 여기서 만든 공간이 데이터와 정책의 기준이 됩니다.",
                  ],
                  [
                    "3",
                    "사람·희망 온도 등록",
                    "Data ingest",
                    "누가 재실 중인지와 각자의 희망 온도를 CSV·JSON으로 등록합니다. DEMO는 이 단계를 가상 데이터로 대신합니다.",
                  ],
                  [
                    "4",
                    "정책 검토·승인",
                    "Policies",
                    "추정 결과 또는 명시적으로 정한 기준을 검토하고 승인합니다. 미식별 그룹의 대체 기준도 따로 지정합니다.",
                  ],
                  [
                    "5",
                    "온도 계산·처리 기록",
                    "Operation",
                    "공간·모드·승인 정책을 선택해 계산합니다. 승인했다는 사실과 실제 적용했다는 사실을 구분해 기록합니다.",
                  ],
                  [
                    "6",
                    "변화 확인·내보내기",
                    "Analytics",
                    "권고·적용·측정 온도와 유효 관측시간을 확인합니다. 추정 세션 화면에서 기록 ZIP을 내려받을 수 있습니다.",
                  ],
                ].map(([num, title, target, description]) => (
                  <li key={num}>
                    <span className="step-number">{num}</span>
                    <div>
                      <h3>{title}</h3>
                      <p>{description}</p>
                      <Button variant="outline" onClick={() => setTab(target)}>
                        {title} 화면 열기
                      </Button>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
            <section className="card">
              <h2>운영 모드 선택하기</h2>
              <table>
                <thead>
                  <tr>
                    <th>모드</th>
                    <th>언제 쓰나요?</th>
                    <th>데이터</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>DEMO</td>
                    <td>실제 자료 없이 사용 흐름 체험</td>
                    <td>가상</td>
                  </tr>
                  <tr>
                    <td>REPLAY</td>
                    <td>과거 시점의 자료로 결정을 다시 계산</td>
                    <td>실제 입력 자료</td>
                  </tr>
                  <tr>
                    <td>SHADOW</td>
                    <td>현재 자료로 권고만 비교</td>
                    <td>실제 입력 자료</td>
                  </tr>
                  <tr>
                    <td>ASSISTED_LIVE</td>
                    <td>운영자가 승인하고 적용·확인을 별도 기록</td>
                    <td>실제 입력 자료</td>
                  </tr>
                </tbody>
              </table>
            </section>
          </>
        )}
        {tab === "Buildings / Zones" && (
          <div className="grid">
            <section className="card">
              <h2>공간 등록</h2>
              <label htmlFor="site">건물 이름</label>
              <input
                id="site"
                value={site}
                onChange={(e) => setSite(e.target.value)}
              />
              <label htmlFor="zone-name">공간 이름</label>
              <input
                id="zone-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <p className="muted">
                기본 운용 범위 18–28°C · Asia/Seoul · 관측 유효시간 60분 · 결정
                간격 15분. 추가 구성은 검증된 API로 지정합니다.
              </p>
              <Button
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const z = await api("/sites/zones", "POST", {
                      site_name: site,
                      name,
                    });
                    setZone(z.id);
                    await refresh();
                    setMessage("공간을 등록했습니다.");
                  })
                }
              >
                공간 등록
              </Button>
            </section>
            <section className="card">
              <h2>등록된 공간</h2>
              {zones.map((z) => (
                <div key={z.id}>
                  <h3>{z.name}</h3>
                  <p className="muted">
                    {z.min_c}–{z.max_c}°C · {z.timezone}
                  </p>
                  <Detail data={z} />
                </div>
              ))}
            </section>
          </div>
        )}
        {tab === "Elicitation" && (
          <>
            <section className="card">
              <h2>공유 온도 선택으로 우선순위 알아보기</h2>
              <p className="muted">
                가상 그룹마다 제시되는 두 온도 중 더 적절한 안을 선택하세요. 이
                선택을 바탕으로 평균적인 만족과 가장 불리한 사람을 얼마나
                우선할지 나타내는 ε를 추정합니다. 첫 질문은 바로 표시됩니다.
              </p>
              <div className="grid">
                <div>
                  <label htmlFor="budget">설문 시간 예산</label>
                  <select
                    id="budget"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                  >
                    <option value="300">5분</option>
                    <option value="600">10분</option>
                    <option value="1800">30분</option>
                    <option value="0">무제한</option>
                  </select>
                  <div className="actions">
                    <Button
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          const s = await api("/elicitation/sessions", "POST", {
                            time_budget_seconds: Number(budget),
                            seed: 17,
                          });
                          setSession(s.id);
                          setState(s);
                          setResult(null);
                        })
                      }
                    >
                      새 세션 만들기
                    </Button>
                  </div>
                </div>
                <div>
                  <label htmlFor="session">기존 세션 ID</label>
                  <input
                    id="session"
                    value={sessionInput}
                    onChange={(e) => setSessionInput(e.target.value)}
                  />
                  <div className="actions">
                    <Button
                      variant="outline"
                      onClick={() =>
                        run(async () => {
                          const r = await api(
                            `/elicitation/${sessionInput}/results`,
                          );
                          setSession(sessionInput);
                          setResult(r);
                          setState(
                            await api(
                              `/elicitation/${sessionInput}/next-or-response`,
                            ),
                          );
                        })
                      }
                    >
                      세션 이어보기
                    </Button>
                  </div>
                </div>
              </div>
              {session && (
                <>
                  {activeSession && (
                    <p
                      className="survey-clock"
                      role="timer"
                      aria-label="설문 남은 시간"
                    >
                      남은 시간{" "}
                      <strong>
                        {remaining === null
                          ? "무제한"
                          : `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`}
                      </strong>
                      <small>
                        {remaining === 0
                          ? "시간 종료 · 이전 응답은 결과 확인에서 볼 수 있습니다."
                          : "다음 질문 계산 시간도 포함됩니다."}
                      </small>
                    </p>
                  )}
                  <p className="muted">세션 {session}</p>
                  <div className="actions">
                    <Button
                      disabled={busy || state?.status === "COMPUTING"}
                      onClick={() => run(next)}
                    >
                      다음 질문 계산
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() =>
                        run(async () =>
                          setResult(
                            await api(`/elicitation/${session}/results`),
                          ),
                        )
                      }
                    >
                      결과 확인
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() =>
                        run(async () => {
                          await api(`/elicitation/${session}/resume`, "POST");
                          await next();
                        })
                      }
                    >
                      중단 세션 재개
                    </Button>
                    <Button variant="outline" onClick={() => run(exportRun)}>
                      기록 내보내기
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() =>
                        run(async () => {
                          await api(`/elicitation/${session}/stop`, "POST");
                          setState({ ...state, status: "STOPPED" });
                        })
                      }
                    >
                      세션 종료
                    </Button>
                  </div>
                </>
              )}
            </section>
            {state?.status === "COMPUTING" && (
              <section className="card" role="status">
                <h2>선택하신 응답의 다음 질문을 준비하고 있습니다</h2>
                <p>
                  A/B 응답별 선계산이 아직 끝나지 않았습니다. 완료된 정확한
                  결과만 사용하며, 이후 같은 응답 경로에서는 캐시를 바로
                  불러옵니다.
                </p>
                <progress
                  aria-label="후보 평가 진행률"
                  max={1}
                  value={state.progress}
                />
                <p>
                  {Math.round(state.progress * 100)}% · 화면을 닫아도 서버에서
                  계산을 계속합니다.
                </p>
              </section>
            )}
            {state &&
              !["IDLE", "READY", "COMPUTING"].includes(state.status) && (
                <div className="notice">
                  세션 상태:{" "}
                  {state.status === "TIME_BUDGET_ENDED"
                    ? "시간 종료 · 00:00"
                    : state.status}
                  <Detail data={state} />
                </div>
              )}
            {q && state?.status === "READY" && (
              <QuestionPanel
                key={q.id}
                question={q}
                busy={busy || remaining === 0}
                onAnswer={(value) => run(() => answer(value))}
              />
            )}
            {result && (
              <>
                <ResultFigure result={result} count={result.response_count} />
                <section className="card">
                  <h2>{result.stage} · 공통 ε 비교 기준</h2>
                  <Detail data={result.common} />
                  <div className="notice">
                    {result.deterministic.status} · 엄격한 일관성 구간은
                    베이지안 credible set과 다릅니다. 구간 간 충돌은 실제 맥락별
                    도덕적 선호 차이를 증명하지 않습니다.
                  </div>
                  {result.stage === "COMMON" && (
                    <p className="muted">
                      공통 ε로 설명할 수 없는 두 구간이 확인되면 구간별 추정으로
                      전환합니다. 두 구간은 각각 응답을 설명할 수 있어야 하며,
                      가능한 ε 범위가 서로 겹치지 않아야 합니다.
                    </p>
                  )}
                  <Detail data={result.deterministic} />
                  <h3>사전분포·응답 모형·적분 해상도 민감도</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>가정</th>
                        <th>ε 중앙값</th>
                        <th>credible set</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.sensitivity?.map((v: Json) => (
                        <tr key={v.name}>
                          <td>{v.name}</td>
                          <td>{v.posterior.median.toFixed(3)}</td>
                          <td>{JSON.stringify(v.posterior.credible_set)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
                {result.stage === "CONTEXTUAL" && (
                  <section className="card">
                    <h2>구간별 ε · 고정 정책 비교</h2>
                    <div className="heatmap">
                      {Object.entries(result.grids).map(([g, v]) => {
                        const s = v as Json;
                        return (
                          <div
                            key={g}
                            className={`cell ${s.status !== "UNIDENTIFIED" ? "estimated" : ""}`}
                          >
                            {g}
                            <strong>
                              {s.status === "UNIDENTIFIED"
                                ? "미식별"
                                : s.median.toFixed(2)}
                            </strong>
                            {s.status === "UNIDENTIFIED"
                              ? "사전분포에 의존"
                              : "추정·미보정"}
                          </div>
                        );
                      })}
                    </div>
                    <div className="notice">
                      고정 ε는 맥락별 규범 목표에 대한 기대 후회 최소화
                      정책입니다. 전체적 참 ε를 추정하는 값이 아닙니다.
                    </div>
                    <label htmlFor="weight-mode">고정 정책의 목표 분포</label>
                    <select
                      id="weight-mode"
                      value={weightMode}
                      onChange={(e) => setWeightMode(e.target.value)}
                    >
                      <option value="uniform_grid">40개 구간 균등</option>
                      <option value="observed_frequency">
                        관측 빈도 가중치 직접 지정
                      </option>
                    </select>
                    {weightMode !== "uniform_grid" && (
                      <>
                        <label htmlFor="weights">
                          모든 구간의 가중치 JSON (합계 1, 관측 기간·출처는 정책
                          근거에 기록)
                        </label>
                        <textarea
                          id="weights"
                          value={weightJson}
                          onChange={(e) => setWeightJson(e.target.value)}
                        />
                        <Button
                          variant="outline"
                          disabled={!zone || busy}
                          onClick={() =>
                            run(async () => {
                              const w = await api(
                                `/analytics/grid-weights?zone_id=${zone}&mode=${mode}&lookback_days=30&smoothing=0`,
                              );
                              setWeightJson(JSON.stringify(w.weights, null, 2));
                              setMessage(
                                `최근 30일 관측 노출 ${w.coverage_seconds}초에서 가중치를 계산했습니다.`,
                              );
                            })
                          }
                        >
                          관측 빈도에서 가중치 가져오기
                        </Button>
                      </>
                    )}
                    <ZoneSelect zones={zones} zone={zone} setZone={setZone} />
                    <Button
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          const f = await api(
                            `/elicitation/${session}/fixed-regret${zone ? `?zone_id=${zone}` : ""}`,
                            "POST",
                            weightMode === "uniform_grid"
                              ? null
                              : JSON.parse(weightJson),
                          );
                          setResult({ ...result, fixed_policy: f });
                        })
                      }
                    >
                      고정 정책 후회 계산
                    </Button>
                    <p className="muted">
                      고정 정책 상태: {result.fixed_policy?.status ?? "대기"} ·
                      대표 ε:{" "}
                      {String(result.fixed_policy?.epsilon ?? "계산 중")} · 기대
                      후회:{" "}
                      {result.fixed_policy?.expected_regret?.toFixed(6) ?? "—"}
                    </p>
                    <Button
                      variant="outline"
                      onClick={() =>
                        run(async () =>
                          setResult(
                            await api(`/elicitation/${session}/results`),
                          ),
                        )
                      }
                    >
                      고정 정책 결과 갱신
                    </Button>
                    <div className="actions">
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setKind("CONTEXTUAL_BY_GRID");
                          setGridEps(
                            JSON.stringify(
                              Object.fromEntries(
                                Object.entries(result.grids)
                                  .filter(
                                    ([, v]) =>
                                      (v as Json).status !== "UNIDENTIFIED",
                                  )
                                  .map(([g, v]) => [g, (v as Json).median]),
                              ),
                              null,
                              2,
                            ),
                          );
                          setTab("Policies");
                        }}
                      >
                        식별된 구간별 정책 검토
                      </Button>
                      <Button
                        disabled={!result.fixed_policy?.numerical_global_search}
                        variant="secondary"
                        onClick={() => {
                          setKind("REGRET_OPTIMAL_FIXED");
                          setEpsilon(String(result.fixed_policy.epsilon));
                          setTab("Policies");
                        }}
                      >
                        고정 ε 정책 검토
                      </Button>
                    </div>
                    <Detail data={result.fixed_policy} />
                  </section>
                )}
              </>
            )}
          </>
        )}
        {tab === "Policies" && (
          <div className="grid">
            <section className="card">
              <h2>정책 초안</h2>
              <ZoneSelect zones={zones} zone={zone} setZone={setZone} />
              <label htmlFor="kind">정책 종류</label>
              <select
                id="kind"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option>COMMON_FIXED</option>
                <option>CONTEXTUAL_BY_GRID</option>
                <option>REGRET_OPTIMAL_FIXED</option>
              </select>
              <label htmlFor="epsilon">ε (또는 infinity)</label>
              <input
                id="epsilon"
                value={epsilon}
                onChange={(e) => setEpsilon(e.target.value)}
              />
              <label htmlFor="grid-eps">구간별 ε (JSON)</label>
              <textarea
                id="grid-eps"
                value={gridEps}
                onChange={(e) => setGridEps(e.target.value)}
              />
              <label htmlFor="fallback">미식별·범위 밖 fallback ε (선택)</label>
              <input
                id="fallback"
                value={fallback}
                onChange={(e) => setFallback(e.target.value)}
              />
              <p className="muted">
                미식별 구간은 추정된 값으로 승인할 수 없습니다. fallback은
                별도의 운영자 선택입니다.
              </p>
              <Button
                disabled={busy || !zone}
                onClick={() =>
                  run(async () => {
                    const parse = (s: string) =>
                      s === "infinity" ? s : Number(s);
                    await api("/policies/draft", "POST", {
                      zone_id: zone,
                      kind,
                      epsilon: parse(epsilon),
                      grid_epsilons: JSON.parse(gridEps),
                      fallback_epsilon: fallback ? parse(fallback) : null,
                      session_id: session || null,
                      rationale: "Operator-reviewed explicit policy",
                    });
                    await refresh();
                  })
                }
              >
                검토용 초안 저장
              </Button>
            </section>
            <section className="card">
              <h2>버전별 승인</h2>
              {policies.map((p) => (
                <div className="card" key={p.id}>
                  <h3>{p.kind}</h3>
                  <p>
                    ε {String(p.epsilon)} ·{" "}
                    <span className="badge">{p.status}</span>
                  </p>
                  <Detail data={p} />
                  {p.status !== "APPROVED" && (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await api(`/policies/${p.id}/approve`, "POST");
                          await refresh();
                        })
                      }
                    >
                      이 정책 승인
                    </Button>
                  )}
                </div>
              ))}
            </section>
          </div>
        )}
        {tab === "Operation" && (
          <>
            <section className="card">
              <h2>운영 입력</h2>
              <DemoEntry
                busy={busy}
                admin={user.role === "Admin"}
                onDemo={() => run(startDemo)}
              />
              <div className="grid">
                <div>
                  <ZoneSelect zones={zones} zone={zone} setZone={setZone} />
                  <label htmlFor="mode">운영 모드</label>
                  <select
                    id="mode"
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    {["DEMO", "REPLAY", "SHADOW", "ASSISTED_LIVE"].map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="policy">승인 정책</label>
                  <select
                    id="policy"
                    value={policy}
                    onChange={(e) => setPolicy(e.target.value)}
                  >
                    <option value="">정책 선택</option>
                    {policies
                      .filter(
                        (p) => p.status === "APPROVED" && p.zone_id === zone,
                      )
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.kind} · ε {String(p.epsilon)}
                        </option>
                      ))}
                  </select>
                  <label htmlFor="at">결정 시각 (ISO 8601, 비우면 현재)</label>
                  <input
                    id="at"
                    value={at}
                    onChange={(e) => setAt(e.target.value)}
                    placeholder="2026-11-17T12:00:00+09:00"
                  />
                </div>
              </div>
              <div className="actions">
                <Button
                  variant="secondary"
                  disabled={busy || !zone || mode !== "DEMO"}
                  onClick={() =>
                    run(async () => {
                      const r = await api(`/demo/seed?zone_id=${zone}`, "POST");
                      setAt(r.at);
                      setMessage(
                        `가상 관측 ${r.count}개 생성. 실제 관측과 분리됩니다.`,
                      );
                    })
                  }
                >
                  가상 데이터 생성
                </Button>
                <Button
                  disabled={busy || !zone || !policy}
                  onClick={() =>
                    run(async () => {
                      setDecision(
                        await api("/operations/decide", "POST", {
                          zone_id: zone,
                          policy_id: policy,
                          operation_mode: mode,
                          at: at || new Date().toISOString(),
                        }),
                      );
                      await refresh();
                    })
                  }
                >
                  권고 온도 계산
                </Button>
              </div>
            </section>
            {decision && (
              <section className="card">
                <h2>권고 검토 · 아직 적용되지 않음</h2>
                {decision.mode === "DEMO" && (
                  <p className="notice">
                    DEMO · 가상 재실자·희망 온도·실내 온도를 사용한 권고입니다.
                    실내 온도는 시뮬레이션에서 생성한 값입니다.
                  </p>
                )}
                <div className="stats">
                  <div className="stat">
                    권고<strong>{decision.recommended_c.toFixed(1)}°C</strong>
                  </div>
                  <div className="stat">
                    <span>
                      {decision.mode === "DEMO"
                        ? "모의 실내 온도"
                        : "실내 측정"}
                    </span>
                    <strong>
                      {decision.measured_environment?.indoor_temperature_c?.toFixed(
                        1,
                      ) ?? "없음"}
                      {decision.measured_environment?.indoor_temperature_c !=
                        null && "°C"}
                    </strong>
                  </div>
                  <div className="stat">
                    평균 모델 효용
                    <strong>
                      {decision.modeled_metrics.efficiency.toFixed(3)}
                    </strong>
                  </div>
                  <div className="stat">
                    최저 모델 효용
                    <strong>
                      {decision.modeled_metrics.equity.toFixed(3)}
                    </strong>
                  </div>
                </div>
                <p className="muted">
                  {decision.n}명 · {decision.grid ?? "범위 밖"} ·{" "}
                  {decision.quality.join(", ") || "입력 검사 통과"}
                </p>
                <label htmlFor="action-value">변경·수동 적용·확인 온도</label>
                <input
                  id="action-value"
                  type="number"
                  step="0.1"
                  value={actionValue}
                  onChange={(e) => setActionValue(e.target.value)}
                />
                <label htmlFor="note">처리 근거</label>
                <input
                  id="note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <div className="actions">
                  {[
                    ["APPROVED", "승인"],
                    ["REJECTED", "거부"],
                    ["OVERRIDE", "변경"],
                    ["MANUALLY_APPLIED", "수동 적용 기록"],
                    ["INDEPENDENTLY_CONFIRMED", "관측 확인 기록"],
                  ].map(([kind, label]) => (
                    <Button
                      key={kind}
                      variant="outline"
                      disabled={busy || !note}
                      onClick={() =>
                        run(async () => {
                          await api(
                            `/operations/${decision.id}/actions`,
                            "POST",
                            {
                              kind,
                              setpoint_c: actionValue
                                ? Number(actionValue)
                                : null,
                              note,
                              request_id: crypto.randomUUID(),
                            },
                          );
                          setMessage(
                            `${label}을 저장했습니다. 설비에 명령을 전송하지 않습니다.`,
                          );
                        })
                      }
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <Detail data={decision} />
              </section>
            )}
            <section className="card">
              <h2>운영 이력</h2>
              <History
                zones={zones}
                rows={history
                  .filter((d) => d.mode === mode && d.zone_id === zone)
                  .slice(-20)
                  .reverse()}
              />
            </section>
          </>
        )}
        {tab === "Data ingest" && (
          <section className="card">
            <h2>사람·희망 온도 등록</h2>
            <DemoEntry
              busy={busy}
              admin={user.role === "Admin"}
              onDemo={() => run(startDemo)}
            />
            <h3>파일 또는 직접 입력</h3>
            <p className="muted">
              시간대가 포함된 observed_at, zone_id, ACTUAL/SIMULATED
              data_origin과 출처 source를 명시하세요. 전체 요청을 검증한 후
              저장합니다.
            </p>
            <div className="grid">
              <div>
                <label htmlFor="domain">관측 종류</label>
                <select
                  id="domain"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                >
                  {[
                    "preferences",
                    "occupancy",
                    "environment",
                    "feedback",
                    "metering",
                  ].map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="format">입력 형식</label>
                <select
                  id="format"
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                >
                  <option>JSON</option>
                  <option>CSV</option>
                </select>
              </div>
            </div>
            <label htmlFor="file">파일 불러오기</label>
            <input
              id="file"
              type="file"
              accept=".csv,.json"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) f.text().then(setPayload);
              }}
            />
            <label htmlFor="payload">입력 내용</label>
            <textarea
              id="payload"
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
            />
            <div className="actions">
              <Button
                variant="outline"
                onClick={() => {
                  setFormat("JSON");
                  setPayload(
                    JSON.stringify(
                      [
                        {
                          zone_id: zone,
                          observed_at: new Date().toISOString(),
                          data_origin: "ACTUAL",
                          source: "actual_report",
                          occupant_id: "opaque-001",
                          desired_setpoint_c: 23,
                        },
                      ],
                      null,
                      2,
                    ),
                  );
                }}
              >
                선호 입력 예시
              </Button>
              <Button
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const r = await api(
                      `/ingest/${domain}${format === "CSV" ? "/csv" : ""}`,
                      "POST",
                      format === "CSV" ? payload : JSON.parse(payload),
                      format === "CSV",
                    );
                    setMessage(`${r.count}개 관측 저장 완료`);
                  })
                }
              >
                검증 후 저장
              </Button>
            </div>
          </section>
        )}
        {tab === "Analytics" && (
          <>
            <section className="card">
              <h2>노출시간 기반 운영 분석</h2>
              <ZoneSelect zones={zones} zone={zone} setZone={setZone} />
              <label htmlFor="analysis-mode">데이터 모드</label>
              <select
                id="analysis-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                {["DEMO", "REPLAY", "SHADOW", "ASSISTED_LIVE"].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
              <label htmlFor="period">집계 기간</label>
              <select
                id="period"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
              >
                {["daily", "weekly", "monthly"].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
              <div className="actions">
                <Button
                  disabled={busy || !zone}
                  onClick={() =>
                    run(async () =>
                      setReport(
                        await api(
                          `/analytics/summary?zone_id=${zone}&mode=${mode}&period=${period}`,
                        ),
                      ),
                    )
                  }
                >
                  분석 조회
                </Button>
              </div>
            </section>
            {report && (
              <section className="card">
                <h2>
                  {report.timezone} · {mode}
                </h2>
                <p className="muted">
                  권고 온도로 계산한 모델 효용입니다. 측정 쾌적감이나 인과적
                  에너지 절감 효과가 아닙니다.
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>기간</th>
                      <th>유효 초</th>
                      <th>사람×초</th>
                      <th>평균 모델 효용</th>
                      <th>환경 관측 누락 초</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.buckets.map((b: Json) => (
                      <tr key={b.period}>
                        <td>{b.period}</td>
                        <td>{b.coverage_seconds.toFixed(0)}</td>
                        <td>{b.person_seconds.toFixed(0)}</td>
                        <td>
                          {b.exposure_weighted_modeled_utility?.toFixed(3)}
                        </td>
                        <td>{b.missing_environment_seconds.toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <TemperatureChart
                  rows={report.series}
                  actions={report.actions}
                />
                <History zones={zones} rows={report.series} />
                <h3>승인·적용 기록</h3>
                <table>
                  <thead>
                    <tr>
                      <th>시각</th>
                      <th>처리 상태</th>
                      <th>온도</th>
                      <th>근거</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.actions.map((a: Json) => (
                      <tr key={a.id}>
                        <td>{a.recorded_at}</td>
                        <td>{a.kind}</td>
                        <td>{a.setpoint_c ?? "—"}</td>
                        <td>{a.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Detail data={report} />
              </section>
            )}
          </>
        )}
        {tab === "Research / Quality" && (
          <section className="card">
            <h2>검증 범위와 과학적 가정</h2>
            <p>
              62명에서 반복 표집한 2,400개 그룹이며, 독립적인 외부 검증 표본
              2,400개가 아닙니다.
            </p>
            <p>
              응답 모형의 κ=30, lapse=0.05와 q 균등 사전분포는 보정되지 않은
              기본 가정입니다. 추정 정확도나 운영 효과를 보장하지 않습니다.
            </p>
            <p>
              전체 후보 53,172,000개 · 64개 적분 노드 · float64 · 첫 전체 탐색
              실측 377초.
            </p>
            <Button
              onClick={() =>
                run(async () =>
                  setReport(await api("/question-bank/provenance")),
                )
              }
            >
              출처·구간 경계 조회
            </Button>
            <Detail data={report} />
            <div className="notice">
              기술 검증 결과와 미완료 항목은 저장소
              app/validation/TEST_REPORT.md를 확인하세요.
            </div>
          </section>
        )}
        {tab === "Settings / Roles" && (
          <section className="card">
            <h2>과학 설정과 접근 권한</h2>
            <p>
              {user.id} · {user.role} · tenant {user.tenant}
            </p>
            <p className="muted">
              Admin: 공간·설정 관리 / Researcher: 추론·분석 / Operator: 정책
              승인·운영 / Viewer: 조회. 서버에서 권한을 검사합니다.
            </p>
            <p>
              과학 설정은 SETTINGS.yaml의 버전을 변경하고 검증·재시작해
              적용합니다. 기존 세션의 설정을 소급 변경하지 않습니다.
            </p>
            <p className="notice">
              후보 수는 2,400 × M(M−1)/2입니다. M은 설정한 온도 개수이며, 간격을
              절반으로 줄이면 후보 수가 약 4배 증가합니다. 범위·간격 변경은 새
              은행 버전과 새 성능 검증을 필요로 합니다.
            </p>
            <Detail data={settings} />
          </section>
        )}
      </main>
    </div>
  );
}
function ZoneSelect({
  zones,
  zone,
  setZone,
}: {
  zones: Json[];
  zone: string;
  setZone: (s: string) => void;
}) {
  return (
    <>
      <label htmlFor="zone-select">운영 공간</label>
      <select
        id="zone-select"
        value={zone}
        onChange={(e) => setZone(e.target.value)}
      >
        <option value="">공간 선택</option>
        {zones.map((z) => (
          <option key={z.id} value={z.id}>
            {z.name}
          </option>
        ))}
      </select>
    </>
  );
}
function History({ rows, zones = [] }: { rows: Json[]; zones?: Json[] }) {
  return rows.length ? (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>시간</th>
            <th>모드</th>
            <th>권고 °C</th>
            <th>측정 °C</th>
            <th>N / 구간</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                {new Date(r.observed_at).toLocaleString("ko-KR", {
                  timeZone:
                    zones.find((z) => z.id === r.zone_id)?.timezone || "UTC",
                })}
                <br />
                <small>
                  {zones.find((z) => z.id === r.zone_id)?.timezone || "UTC"}
                </small>
              </td>
              <td>{r.mode}</td>
              <td>{r.recommended_c.toFixed(1)}</td>
              <td>
                {r.measured_environment?.indoor_temperature_c?.toFixed(1) ??
                  "미관측"}
              </td>
              <td>
                {r.n} / {r.grid ?? "범위 밖"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <div className="empty">아직 기록된 결정이 없습니다.</div>
  );
}

function TemperatureChart({
  rows,
  actions,
}: {
  rows: Json[];
  actions: Json[];
}) {
  const series = rows.map((r) => ({
    id: r.id,
    time: Date.parse(r.observed_at),
    recommended: r.recommended_c,
    measured: r.measured_environment?.indoor_temperature_c,
    applied: actions
      .filter((a) => a.decision_id === r.id && a.kind === "MANUALLY_APPLIED")
      .at(-1)?.setpoint_c,
  }));
  if (!series.length) return null;
  const values = series
    .flatMap((r) => [r.recommended, r.measured, r.applied])
    .filter((v) => typeof v === "number");
  const low = Math.floor(Math.min(...values)) - 1,
    high = Math.ceil(Math.max(...values)) + 1;
  const t0 = Math.min(...series.map((r) => r.time)),
    t1 = Math.max(...series.map((r) => r.time));
  const coords = (r: (typeof series)[number], v: number) =>
    `${40 + ((r.time - t0) / Math.max(1, t1 - t0)) * 580},${130 - ((v - low) / (high - low)) * 110}`;
  return (
    <>
      <h3>권고·수동 적용·실내 측정 온도</h3>
      <svg
        className="chart"
        viewBox="0 0 640 155"
        role="img"
        aria-label="시간별 권고·수동 적용·측정 온도"
      >
        <text x="0" y="22" fontSize="11">
          {high}°C
        </text>
        <text x="0" y="132" fontSize="11">
          {low}°C
        </text>
        {(
          [
            ["recommended", "#08786a"],
            ["measured", "#a45d12"],
            ["applied", "#4159b1"],
          ] as const
        ).map(([key, color]) => (
          <g key={key}>
            {series.map((r, i) =>
              r[key] === undefined ? null : (
                <circle
                  key={i}
                  cx={coords(r, r[key]).split(",")[0]}
                  cy={coords(r, r[key]).split(",")[1]}
                  r="3"
                  fill={color}
                />
              ),
            )}
            <polyline
              points={series
                .filter((r) => r[key] !== undefined)
                .map((r) => coords(r, r[key]))
                .join(" ")}
              fill="none"
              stroke={color}
              strokeWidth="1.5"
            />
          </g>
        ))}
      </svg>
      <p className="muted">
        녹색: 권고 / 갈색: 실내 측정 / 파랑: 수동 적용 보고. 점 사이 선은 시각적
        연결이며 연속 관측을 뜻하지 않습니다.
      </p>
    </>
  );
}
