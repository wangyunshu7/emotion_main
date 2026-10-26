import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DateTime } from "luxon";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import type { Insights as Stats, Page, Receipt, Review } from "../../api/types";
import { api, message } from "../../api/client";
import { useAuth } from "../../app/context";
import { useData } from "../../hooks/data";
import { Empty, ErrorState, Heading, Loading, Pill } from "../../components/UI";
import { JobPanel } from "../../components/JobPanel";

function Statistics({ data }: { data: Stats }) {
  return (
    <>
      <div className="stat-grid">
        <div className="stat card">
          <span>记录条数</span>
          <strong>{data.entry_count}</strong>
        </div>
        <div className="stat card">
          <span>有记录的日子</span>
          <strong>
            {data.recorded_days}
            <small> 天</small>
          </strong>
        </div>
        <div className="stat card">
          <span>自述心情平均分</span>
          <strong>
            {data.mean_score ?? "—"}
            <small> / 5</small>
          </strong>
        </div>
      </div>
      <section className="card">
        <h2>心情的起伏</h2>
        <p className="muted">
          {data.timezone} · 无记录日期留空，评分只代表你自己的感受。
        </p>
        <div className="chart">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data.days}>
              <CartesianGrid vertical={false} stroke="#e9ece3" />
              <XAxis
                dataKey="date"
                tickFormatter={(v) => String(v).slice(5)}
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[1, 5]}
                ticks={[1, 2, 3, 4, 5]}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip />
              <Line
                type="linear"
                dataKey="mean_score"
                name="心情均分"
                stroke="#6b8c63"
                strokeWidth={2.5}
                dot={{ r: 4, fill: "#6b8c63" }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <details>
          <summary>查看每日数据表</summary>
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>记录数</th>
                <th>自述均分</th>
              </tr>
            </thead>
            <tbody>
              {data.days.map((d) => (
                <tr key={d.date}>
                  <td>{d.date}</td>
                  <td>{d.entry_count}</td>
                  <td>{d.mean_score ?? "未记录"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>
      <div className="two-columns">
        <section className="card">
          <h2>情绪日历</h2>
          <div className="calendar">
            {data.days.map((d) => (
              <div
                key={d.date}
                className={`calendar-day ${d.mean_score === null ? "unrecorded" : `mood-bg-${Math.round(d.mean_score)}`}`}
                title={`${d.date}：${d.entry_count} 条，${d.mean_score ?? "未记录"}`}
              >
                <time>{d.date.slice(5)}</time>
                <strong>{d.mean_score ?? "—"}</strong>
                <small>
                  {d.entry_count ? `${d.entry_count} 条` : "未记录"}
                </small>
              </div>
            ))}
          </div>
        </section>
        <section className="card">
          <h2>出现过的感受</h2>
          <p className="muted">
            同一条记录可包含多种情绪，占比总和可超过 100%。
          </p>
          {data.emotion_distribution.map((t) => (
            <div className="distribution" key={t.code + t.label}>
              <div>
                <span>{t.label}</span>
                <small>{Math.round((t.ratio || 0) * 100)}%</small>
              </div>
              <progress value={t.ratio || 0} max={1} />
            </div>
          ))}
          {!data.emotion_distribution.length && (
            <Empty text="记录之后，就能在这里看见情绪分布。" />
          )}
          <h3>记录中的事件</h3>
          {data.tag_distribution.map((t) => (
            <Pill key={t.code + t.label}>
              {t.label} · {t.entry_count} 条
            </Pill>
          ))}
        </section>
      </div>
    </>
  );
}

export function Insights() {
  const { user } = useAuth();
  const today = DateTime.now().setZone(user?.timezone).toISODate()!;
  const [days, setDays] = useState(7);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [job, setJob] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const from =
    start ||
    DateTime.fromISO(today)
      .minus({ days: days - 1 })
      .toISODate()!;
  const to = end || today;
  const query = useData<Stats>(
    "insights",
    `/insights?start_date=${from}&end_date=${to}`,
  );
  const reviews = useData<Page<Review>>("reviews", "/reviews?page_size=5");
  const generate = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api<Receipt>("/reviews", "POST", {
        start_date: DateTime.fromISO(to).minus({ days: 6 }).toISODate(),
        end_date: to,
      });
      if ("job_id" in r) setJob(r.job_id);
      else if ("review_id" in r) navigate(`/reviews/${r.review_id}`);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Heading
        eyebrow="LOOK BACK, GENTLY"
        title="情绪回顾"
        subtitle="从记录里看见自己，不急着给感受下结论。"
      />
      <div className="filters">
        <div className="chips">
          {[7, 30].map((n) => (
            <button
              key={n}
              className={`chip ${days === n && !start && !end ? "selected" : ""}`}
              onClick={() => {
                setDays(n);
                setStart("");
                setEnd("");
              }}
            >
              近 {n} 天
            </button>
          ))}
        </div>
        <label>
          从
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          到
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
      </div>
      <ErrorState error={query.error} />
      {query.isLoading && <Loading />}
      {query.data && <Statistics data={query.data} />}
      <section className="card review-generator">
        <div>
          <Pill>一次温柔的回望</Pill>
          <h2>给这一周，留一份回顾</h2>
          <p>
            按所选结束日期回顾最近 7 天。记录日不足 3 天时只展示统计；AI
            未授权也能生成。
          </p>
        </div>
        <button
          className="button"
          disabled={busy}
          onClick={() => void generate()}
        >
          {busy ? "正在提交…" : "生成 7 天回顾"}
        </button>
        <ErrorState error={error} />
        {job && (
          <JobPanel
            id={job}
            onDone={(result) => {
              setJob(null);
              navigate(`/reviews/${result}`);
            }}
          />
        )}
      </section>
      {reviews.data && reviews.data.items.length > 0 && (
        <section>
          <h2>已生成的回顾</h2>
          {reviews.data.items.map((r) => (
            <Link className="card card-link" key={r.id} to={`/reviews/${r.id}`}>
              {r.start_date} — {r.end_date}
              <span>查看回顾 →</span>
            </Link>
          ))}
        </section>
      )}
    </>
  );
}
export function ReviewDetail() {
  const { id } = useParams();
  const query = useData<Review>("review", `/reviews/${id}`);
  if (query.isLoading) return <Loading />;
  if (query.error)
    return (
      <>
        <ErrorState error={query.error} />
        <Link to="/insights">记录可能已更新，返回重新生成</Link>
      </>
    );
  const r = query.data;
  if (!r) return null;
  return (
    <>
      <Heading
        title="这一周的你"
        subtitle={`${r.start_date} — ${r.end_date} · 统计截至生成时`}
      />
      <section className="card">
        <Pill>{r.ai_status === "succeeded" ? "AI 整理" : "基础统计回顾"}</Pill>
        <p className="entry-body">
          {r.narrative ||
            {
              insufficient: "记录天数还不多，先看看这些小片段。",
              disabled: "AI 未启用，以下统计由程序计算。",
              failed: "AI 文字整理未完成，基础统计仍可查看。",
              safety_blocked:
                "本次未生成文字分析，可以在需要时寻求可信任的人或专业支持。",
            }[r.ai_status] ||
            "按自己的理解回顾这些记录。"}
        </p>
        {r.observations.map((o, i) => (
          <article className="factor" key={i}>
            <p>{o.text}</p>
            {o.evidence.map((e, k) => (
              <div key={k}>
                {e.journal_id ? (
                  <Link to={`/journals/${e.journal_id}`}>
                    “{e.quote}” · 查看原文
                  </Link>
                ) : (
                  <small>统计依据：{e.stat_path}</small>
                )}
              </div>
            ))}
          </article>
        ))}
      </section>
      <Statistics data={r.statistics} />
    </>
  );
}
