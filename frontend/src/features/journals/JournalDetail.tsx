import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DateTime } from "luxon";
import { ArrowLeft, Pencil, Sparkles, Trash2 } from "lucide-react";
import { api, ApiError, message } from "../../api/client";
import type { Analysis, Factor, Journal, Receipt } from "../../api/types";
import { useAuth } from "../../app/context";
import { useData, useInvalidate, useMetadata } from "../../hooks/data";
import {
  Confirm,
  ErrorState,
  Heading,
  Loading,
  Pill,
} from "../../components/UI";
import { JobPanel } from "../../components/JobPanel";

function FactorCard({
  factor,
  analysisId,
  onSaved,
}: {
  factor: Factor;
  analysisId: string;
  onSaved: () => void;
}) {
  const [text, setText] = useState(factor.user_text || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async (status: Factor["review_status"]) => {
    setBusy(true);
    setError("");
    try {
      await api(`/analyses/${analysisId}/factors/${factor.id}`, "PATCH", {
        review_status: status,
        user_text: text.trim() || null,
      });
      onSaved();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <article className="factor">
      <h3>{factor.label}</h3>
      <p>{factor.hypothesis}</p>
      <blockquote>
        “{factor.evidence_quote}”<small>来自你的原文</small>
      </blockquote>
      <label>
        你自己的理解 <small>选填</small>
        <input
          maxLength={300}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="也可以按自己的理解修改这条线索"
        />
      </label>
      <div className="chips">
        {(
          [
            ["matches", "符合"],
            ["partial", "部分符合"],
            ["rejected", "不符合"],
          ] as const
        ).map(([status, label]) => (
          <button
            key={status}
            className={`chip ${factor.review_status === status ? "selected" : ""}`}
            disabled={busy}
            onClick={() => void save(status)}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorState error={error} />
    </article>
  );
}
export function JournalDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const meta = useMetadata();
  const query = useData<Journal>("journal", `/journals/${id}`);
  const analysis = useData<Analysis>("analysis", `/journals/${id}/analysis`);
  const [job, setJob] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const analyze = async () => {
    setBusy(true);
    setError("");
    setJob(null);
    try {
      const r = await api<Receipt>(`/journals/${id}/analysis-jobs`, "POST", {
        journal_version: query.data!.version,
      });
      if ("job_id" in r) setJob(r.job_id);
      else await analysis.refetch();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    try {
      await api(`/journals/${id}?version=${query.data!.version}`, "DELETE");
      await invalidate();
      navigate("/journals");
    } catch (e) {
      setError(message(e));
      setDeleting(false);
    } finally {
      setBusy(false);
    }
  };
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const j = query.data;
  if (!j) return null;
  return (
    <>
      <Link to="/journals" className="text-button back">
        <ArrowLeft size={16} />
        全部日记
      </Link>
      <Heading
        title={j.emotions.map((t) => t.label).join(" · ")}
        subtitle={DateTime.fromISO(j.occurred_at)
          .setZone(user?.timezone)
          .toFormat("yyyy 年 MM 月 dd 日 HH:mm")}
        action={
          <div className="actions">
            <Link className="button secondary" to={`/journals/${id}/edit`}>
              <Pencil size={15} />
              编辑
            </Link>
            <button
              className="icon-button"
              aria-label="删除日记"
              onClick={() => setDeleting(true)}
            >
              <Trash2 size={18} />
            </button>
          </div>
        }
      />
      <section className="card entry">
        <div className="row">
          <Pill>心情评分 {j.mood_score} / 5</Pill>
          <span className="muted">私密记录</span>
        </div>
        <p className="entry-body">
          {j.body || "这次只记录了情绪，没有填写正文。"}
        </p>
        <div>
          {j.event_tags.map((t) => (
            <Pill key={t.code + t.label}>{t.label}</Pill>
          ))}
        </div>
      </section>
      <ErrorState error={error} />
      <section className="card analysis-panel">
        <div className="section-title">
          <h2>
            <Sparkles size={19} />
            一起看看这段心情
          </h2>
          <Pill>AI 整理</Pill>
        </div>
        <p className="muted">分析只是可能的线索，你对自己的理解始终最重要。</p>
        {!user?.ai_enabled ? (
          <div className="notice">
            AI 处理尚未授权。你可以继续使用记录和基础统计，或
            <Link to="/settings">阅读处理说明</Link>后自主开启。
          </div>
        ) : (
          <>
            <p className="muted">
              {meta.data?.ai_mode === "fake"
                ? "当前为开发模拟模式，结果明确标记为模拟。"
                : meta.data?.ai_description}
            </p>
            <button
              className="button secondary"
              disabled={busy || !j.body.trim()}
              onClick={() => void analyze()}
            >
              {busy
                ? "正在提交…"
                : analysis.data
                  ? "查看／重新请求整理"
                  : "主动整理这条日记"}
            </button>
          </>
        )}
        {job && (
          <JobPanel
            id={job}
            onDone={() => {
              setJob(null);
              void analysis.refetch();
            }}
          />
        )}
        {analysis.error &&
          !(
            analysis.error instanceof ApiError && analysis.error.status === 404
          ) && <ErrorState error={analysis.error} />}{" "}
        {analysis.data &&
          !analysis.error &&
          !analysis.isFetching &&
          analysis.data.journal_version === j.version && (
            <>
              <p className="analysis-summary">{analysis.data.summary}</p>
              {analysis.data.factors.map((f) => (
                <FactorCard
                  key={f.id}
                  factor={f}
                  analysisId={analysis.data!.id}
                  onSaved={() => {
                    void analysis.refetch();
                    void invalidate();
                  }}
                />
              ))}
              {analysis.data.reflection_question && (
                <div className="reflection">
                  一个可选的小问题<p>{analysis.data.reflection_question}</p>
                  <small>不用急着回答，也可以跳过。</small>
                </div>
              )}
            </>
          )}
      </section>
      <Link className="button" to={`/care?journal_id=${id}`}>
        给自己一点关怀
      </Link>
      <Confirm
        open={deleting}
        title="删除这条日记？"
        busy={busy}
        onCancel={() => setDeleting(false)}
        onConfirm={() => void remove()}
      >
        原文与对应分析会删除，相关回顾会失效。活动反馈会保留，但不再关联这条日记。
      </Confirm>
    </>
  );
}
