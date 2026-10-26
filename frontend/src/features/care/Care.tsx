import { useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { Clock3, Flower2, ArrowRight } from "lucide-react";
import type {
  Activity,
  ActivitySummary,
  CareSession,
  Page,
  Recommendation,
} from "../../api/types";
import { api, message } from "../../api/client";
import { createRequestId } from "../../utils/requestId";
import { useData } from "../../hooks/data";
import { Empty, ErrorState, Heading, Loading, Pill } from "../../components/UI";

const names: Record<string, string> = {
  mindfulness: "冥想与觉察",
  music: "音乐与声音",
  movement: "轻量活动",
  writing: "书写练习",
  daily_care: "日常关怀",
};
function ActivityCard({
  item,
  reason,
  journalId,
}: {
  item: ActivitySummary;
  reason?: string;
  journalId?: string;
}) {
  return (
    <Link
      className={`card activity-card activity-${item.type}`}
      to={`/care/activities/${item.id}${journalId ? `?journal_id=${journalId}` : ""}`}
    >
      <div className="activity-icon">
        <Flower2 size={32} strokeWidth={1.2} />
      </div>
      <Pill>{names[item.type]}</Pill>
      <h3>{item.title}</h3>
      <p>{reason || item.suitability_note}</p>
      <div className="row">
        <span>
          <Clock3 size={14} /> {item.duration_minutes} 分钟
        </span>
        <ArrowRight size={18} />
      </div>
    </Link>
  );
}
export function Care() {
  const [params] = useSearchParams();
  const journalId = params.get("journal_id") || undefined;
  const [type, setType] = useState("");
  const [minutes, setMinutes] = useState(5);
  const [scene, setScene] = useState("home");
  const [excluded, setExcluded] = useState<string[]>([]);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const query = useData<Page<ActivitySummary>>(
    "activities",
    `/activities?page_size=100${type ? `&type=${type}` : ""}`,
  );
  const recommend = async () => {
    setBusy(true);
    setError("");
    try {
      setRec(
        await api<Recommendation>("/care/recommendations", "POST", {
          available_minutes: minutes,
          scene,
          excluded_types: excluded,
          ...(journalId ? { journal_id: journalId } : {}),
        }),
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Heading
        eyebrow="SMALL ACTS OF KINDNESS"
        title="给自己一点关怀"
        subtitle="不需要做很多，一个小小的行动也可以。"
      />
      <section className="card recommendation-form">
        <div>
          <Pill>从此刻出发</Pill>
          <h2>找一个适合现在的活动</h2>
          <p className="muted">根据你选择的时间与场景筛选，无需 AI 授权。</p>
        </div>
        <div className="filters">
          <label>
            我有多少时间
            <select
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            >
              {[2, 3, 5, 10, 15, 30, 60].map((n) => (
                <option value={n} key={n}>
                  {n} 分钟
                </option>
              ))}
            </select>
          </label>
          <label>
            现在在哪里
            <select value={scene} onChange={(e) => setScene(e.target.value)}>
              <option value="home">在家</option>
              <option value="office">办公室／学校</option>
              <option value="outdoor">户外</option>
              <option value="any">不限</option>
            </select>
          </label>
          <button
            className="button"
            disabled={busy}
            onClick={() => void recommend()}
          >
            {busy ? "正在寻找…" : "为我推荐"}
          </button>
        </div>
        <details>
          <summary>暂时不想尝试的类型</summary>
          <div className="chips">
            {Object.entries(names).map(([code, label]) => (
              <label className="check" key={code}>
                <input
                  type="checkbox"
                  checked={excluded.includes(code)}
                  onChange={() =>
                    setExcluded((old) =>
                      old.includes(code)
                        ? old.filter((c) => c !== code)
                        : [...old, code],
                    )
                  }
                />
                {label}
              </label>
            ))}
          </div>
        </details>
        <ErrorState error={error} />
      </section>
      {rec && (
        <section>
          <h2>此刻的小选择</h2>
          <div className="activity-grid">
            {rec.items.map((r) => (
              <ActivityCard
                key={r.activity.id}
                item={r.activity}
                reason={r.reason}
                journalId={journalId}
              />
            ))}
          </div>
          {!rec.items.length && (
            <Empty text={rec.empty_reason || "暂时没有匹配的活动。"} />
          )}
        </section>
      )}
      <div className="section-title">
        <h2>关怀活动库</h2>
      </div>
      <div className="chips">
        <button
          className={`chip ${!type ? "selected" : ""}`}
          onClick={() => setType("")}
        >
          全部
        </button>
        {Object.entries(names).map(([code, label]) => (
          <button
            key={code}
            className={`chip ${type === code ? "selected" : ""}`}
            onClick={() => setType(code)}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorState error={query.error} />
      {query.isLoading && <Loading />}
      <div className="activity-grid">
        {query.data?.items.map((a) => (
          <ActivityCard key={a.id} item={a} journalId={journalId} />
        ))}
      </div>
      {query.data?.items.length === 0 && (
        <Empty text="目前没有符合条件的已审核活动。部署维护者可导入审核内容；本地开发可显式创建演示样例。" />
      )}
      <CareHistory />
    </>
  );
}
function CareHistory() {
  const query = useData<Page<CareSession>>(
    "care-history",
    "/care/sessions?page_size=10",
  );
  return query.data?.items.length ? (
    <section>
      <h2>我的关怀记录</h2>
      {query.data.items.map((c) => (
        <Link
          className="card card-link"
          key={c.id}
          to={`/care/sessions/${c.id}`}
        >
          <span>{String(c.activity_snapshot.title || "关怀活动")}</span>
          <Pill>
            {
              {
                running: "进行中",
                paused: "已暂停",
                completed: "已完成",
                stopped: "已结束",
              }[c.status]
            }
          </Pill>
        </Link>
      ))}
    </section>
  ) : null;
}

export function ActivityDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const query = useData<Activity>("activity", `/activities/${id}`);
  const navigate = useNavigate();
  const [before, setBefore] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestId] = useState(() => createRequestId());
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const c = await api<CareSession>("/care/sessions", "POST", {
        activity_id: id,
        client_request_id: requestId,
        journal_id: params.get("journal_id"),
        before_score: before ? Number(before) : null,
      });
      navigate(`/care/sessions/${c.id}`);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const a = query.data;
  if (!a) return null;
  return (
    <>
      <Link className="text-button back" to="/care">
        ← 关怀活动
      </Link>
      <Heading
        title={a.title}
        subtitle={`${names[a.type]} · 约 ${a.duration_minutes} 分钟`}
      />
      <section className="card activity-detail">
        <p className="notice">{a.suitability_note} 你可以随时停止。</p>
        <ol>
          {a.steps.map((s) => (
            <li key={s.order}>{s.text}</li>
          ))}
        </ol>
        <label>
          开始前的心情 <small>选填</small>
          <select value={before} onChange={(e) => setBefore(e.target.value)}>
            <option value="">暂不填写</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option value={n} key={n}>
                {n} / 5
              </option>
            ))}
          </select>
        </label>
        <ErrorState error={error} />
        <button className="button" disabled={busy} onClick={() => void start()}>
          {busy ? "正在开始…" : "开始这段关怀"}
        </button>
        <div className="source">
          <p>内容来源：{a.source_name}</p>
          <p>授权说明：{a.license_note}</p>
          {a.source_url && (
            <a href={a.source_url} target="_blank" rel="noreferrer">
              查看来源
            </a>
          )}
        </div>
      </section>
    </>
  );
}
