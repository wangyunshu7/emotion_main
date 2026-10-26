import { useState } from "react";
import { Link } from "react-router-dom";
import { DateTime } from "luxon";
import { Plus } from "lucide-react";
import { useAuth } from "../../app/context";
import { useData, useMetadata } from "../../hooks/data";
import type { JournalSummary, Page } from "../../api/types";
import { Empty, ErrorState, Heading, Loading, Pill } from "../../components/UI";

export function Journals() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [tag, setTag] = useState("");
  const [emotion, setEmotion] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const meta = useMetadata();
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  if (tag) params.set("tag_code", tag);
  if (emotion) params.set("emotion_code", emotion);
  if (start && end) {
    params.set("start_date", start);
    params.set("end_date", end);
  }
  const query = useData<Page<JournalSummary>>(
    "journals",
    `/journals?${params}`,
  );
  return (
    <>
      <Heading
        eyebrow="SMALL MOMENTS, REAL FEELINGS"
        title="我的日记"
        subtitle="生活的晴与雨，都可以在这里停留。"
        action={
          <Link className="button" to="/journals/new">
            <Plus size={17} />
            记录此刻
          </Link>
        }
      />
      <div className="card filters">
        <label>
          情绪
          <select
            value={emotion}
            onChange={(e) => {
              setEmotion(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部情绪</option>
            {meta.data?.emotions.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          事件
          <select
            value={tag}
            onChange={(e) => {
              setTag(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部事件</option>
            {meta.data?.event_tags.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          从
          <input
            type="date"
            value={start}
            onChange={(e) => {
              setStart(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          到
          <input
            type="date"
            value={end}
            onChange={(e) => {
              setEnd(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <button
          className="text-button"
          onClick={() => {
            setStart("");
            setEnd("");
            setTag("");
            setEmotion("");
            setPage(1);
          }}
        >
          重置
        </button>
      </div>
      {!!start !== !!end && (
        <p className="notice">
          请同时选择起止日期，范围最多 31 天；当前尚未按日期筛选。
        </p>
      )}
      <ErrorState error={query.error} />
      {query.isLoading && <Loading />}
      {query.data?.items.length === 0 && (
        <Empty
          text={
            tag || emotion || start
              ? "没有符合筛选条件的记录。"
              : "第一条日记，从此刻开始。"
          }
        />
      )}
      <div className="journal-list">
        {query.data?.items.map((j) => (
          <Link
            key={j.id}
            className="card journal-row"
            to={`/journals/${j.id}`}
          >
            <span className={`mood-dot mood-${j.mood_score}`}>
              {["", "☂", "☁", "◒", "☀", "✦"][j.mood_score]}
            </span>
            <div>
              <div className="row">
                <strong>{j.emotions.map((t) => t.label).join(" · ")}</strong>
                <time>
                  {DateTime.fromISO(j.occurred_at)
                    .setZone(user?.timezone)
                    .toFormat("yyyy.MM.dd HH:mm")}
                </time>
              </div>
              <p>{j.body_preview || "这一刻，给自己留下了一个心情标记。"}</p>
              {j.event_tags.map((t) => (
                <Pill key={t.code + t.label}>{t.label}</Pill>
              ))}
            </div>
          </Link>
        ))}
      </div>
      {query.data && query.data.total > 10 && (
        <div className="pagination">
          <button
            className="button secondary"
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            上一页
          </button>
          <span>
            第 {page} 页 · 共 {query.data.total} 条
          </span>
          <button
            className="button secondary"
            disabled={page * 10 >= query.data.total}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      )}
    </>
  );
}
