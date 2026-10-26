import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Activity, CareSession } from "../../api/types";
import { api, message } from "../../api/client";
import { useData, useInvalidate } from "../../hooks/data";
import { ErrorState, Heading, Loading } from "../../components/UI";

export function CareTimer() {
  const { id } = useParams();
  const query = useData<CareSession>("care-session", `/care/sessions/${id}`);
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  return query.data ? <Timer key={query.data.id} initial={query.data} /> : null;
}
function Timer({ initial }: { initial: CareSession }) {
  const [session, setSession] = useState(initial);
  const [seconds, setSeconds] = useState(initial.elapsed_seconds);
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [after, setAfter] = useState(initial.after_score?.toString() || "");
  const [help, setHelp] = useState(initial.helpfulness || "");
  const [note, setNote] = useState(initial.feedback_note || "");
  const [saved, setSaved] = useState(false);
  const baseline = useRef(initial.elapsed_seconds);
  const started = useRef(0);
  const invalidate = useInvalidate();
  const activity = session.activity_snapshot as Activity;
  const terminal = ["completed", "stopped"].includes(session.status);
  const current = () =>
    baseline.current +
    (active ? Math.floor((performance.now() - started.current) / 1000) : 0);
  useEffect(() => {
    if (!active) return;
    const interval = window.setInterval(
      () =>
        setSeconds(
          baseline.current +
            Math.floor((performance.now() - started.current) / 1000),
        ),
      250,
    );
    return () => clearInterval(interval);
  }, [active]);
  useEffect(() => {
    const hide = () => {
      if (document.hidden && active) {
        baseline.current = current();
        setSeconds(baseline.current);
        setActive(false);
      }
    };
    document.addEventListener("visibilitychange", hide);
    return () => document.removeEventListener("visibilitychange", hide);
  });
  const resume = async () => {
    if (session.status === "paused") {
      if (!(await transition("running"))) return;
    }
    started.current = performance.now();
    setActive(true);
  };
  const transition = async (status: string) => {
    setBusy(true);
    setError("");
    const elapsed = current();
    setActive(false);
    baseline.current = elapsed;
    setSeconds(elapsed);
    try {
      const next = await api<CareSession>(
        `/care/sessions/${session.id}/state`,
        "PATCH",
        { version: session.version, status, elapsed_seconds: elapsed },
      );
      setSession(next);
      await invalidate();
      return true;
    } catch (e) {
      setError(message(e));
      return false;
    } finally {
      setBusy(false);
    }
  };
  const feedback = async () => {
    setBusy(true);
    setError("");
    try {
      setSession(
        await api<CareSession>(`/care/sessions/${session.id}/feedback`, "PUT", {
          version: session.version,
          after_score: after ? Number(after) : null,
          helpfulness: help || null,
          feedback_note: note || null,
        }),
      );
      setSaved(true);
      await invalidate();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const remaining = Math.max(0, activity.duration_minutes * 60 - seconds);
  return (
    <>
      <Heading
        title={activity.title}
        subtitle="按照你的感受进行，随时都可以停下。"
      />
      <section className="card timer-card">
        <span className="eyebrow">A MOMENT JUST FOR YOU</span>
        <div className="timer-orbit">
          <strong>
            {String(Math.floor(remaining / 60)).padStart(2, "0")}:
            {String(remaining % 60).padStart(2, "0")}
          </strong>
          <span>
            {terminal ? "已结束" : active ? "慢慢来" : "页面计时已暂停"}
          </span>
        </div>
        <p className="muted">
          已记录 {seconds} 秒。离开页面或刷新后不自动累计不确定的活动时间。
        </p>
        {remaining === 0 && !terminal && (
          <p>时间到了，按自己的感受选择完成或结束。</p>
        )}
        <ErrorState error={error} />
        {!terminal && (
          <div className="actions center">
            {!active ? (
              <button
                className="button"
                disabled={busy}
                onClick={() => void resume()}
              >
                继续页面计时
              </button>
            ) : (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => void transition("paused")}
              >
                暂停
              </button>
            )}
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void transition("stopped")}
            >
              提前结束
            </button>
            <button
              className="button"
              disabled={busy || session.status === "paused"}
              onClick={() => void transition("completed")}
            >
              完成活动
            </button>
          </div>
        )}
        <ol className="timer-steps">
          {activity.steps.map((s) => (
            <li key={s.order}>{s.text}</li>
          ))}
        </ol>
      </section>
      {terminal && (
        <section className="card">
          <h2>此刻的感受，有变化吗？</h2>
          <p className="muted">
            没有变化也没关系。反馈全部选填，可以直接返回。
          </p>
          <label>
            这次活动
            <select
              value={help}
              onChange={(e) => {
                setHelp(e.target.value);
                setSaved(false);
              }}
            >
              <option value="">暂不评价</option>
              <option value="helpful">有帮助</option>
              <option value="neutral">一般</option>
              <option value="not_suitable">不适合</option>
            </select>
          </label>
          <label>
            活动后的心情
            <select
              value={after}
              onChange={(e) => {
                setAfter(e.target.value);
                setSaved(false);
              }}
            >
              <option value="">暂不填写</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} / 5
                </option>
              ))}
            </select>
          </label>
          <label>
            想补充些什么？
            <textarea
              maxLength={500}
              rows={3}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                setSaved(false);
              }}
            />
          </label>
          <div className="actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => void feedback()}
            >
              {saved ? "反馈已保存" : "保存反馈"}
            </button>
            <Link to="/care" className="button secondary">
              返回活动库
            </Link>
          </div>
        </section>
      )}
    </>
  );
}
