import { DateTime } from "luxon";
import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, Flower2, Plus, Sprout, Sun } from "lucide-react";
import { useAuth } from "../../app/context";
import { useData } from "../../hooks/data";
import type { Insights, JournalSummary, Page } from "../../api/types";
import { Empty, ErrorState, Heading, Pill } from "../../components/UI";

export function Home() {
  const { user } = useAuth();
  const now = DateTime.now().setZone(user?.timezone);
  const stats = useData<Insights>("insights", "/insights");
  const journals = useData<Page<JournalSummary>>(
    "journals",
    "/journals?page_size=3",
  );
  return (
    <>
      <Heading
        eyebrow={now.setLocale("en").toFormat("cccc, LLLL dd").toUpperCase()}
        title={`你好，${user?.nickname || "心晴朋友"}`}
        subtitle="今天，也留一点时间听听自己的声音。"
        action={
          <span className="weather">
            <Sun size={18} /> 内心天气，由你记录
          </span>
        }
      />
      <section className="hero">
        <div>
          <Pill>你的每一种感受，都值得被看见</Pill>
          <h2>
            此刻的你，
            <br />
            心情是什么颜色？
          </h2>
          <p>
            不需要组织好语言，简单记录就好。
            <br />
            从一个小小的停顿，开始关心自己。
          </p>
          <Link className="button" to="/journals/new">
            <Plus size={18} />
            记录此刻
            <ArrowRight size={17} />
          </Link>
        </div>
        <div className="garden" aria-hidden="true">
          <div className="garden-sun" />
          <div className="garden-hill" />
          <Sprout className="garden-plant" strokeWidth={0.8} />
          <span className="garden-caption">BREATHE. FEEL. GROW.</span>
        </div>
      </section>
      <div className="stat-grid">
        <div className="stat card">
          <span>近 7 天的记录</span>
          <strong>
            {stats.data?.entry_count ?? "—"}
            <small> 条</small>
          </strong>
          <p>每一笔，都是倾听自己</p>
        </div>
        <div className="stat card">
          <span>有记录的日子</span>
          <strong>
            {stats.data?.recorded_days ?? "—"}
            <small> 天</small>
          </strong>
          <p>按自己的节奏就好</p>
        </div>
        <div className="stat card">
          <span>完成的关怀活动</span>
          <strong>
            {stats.data?.care_summary.completed_count ?? "—"}
            <small> 次</small>
          </strong>
          <p>给自己一点温柔的照顾</p>
        </div>
      </div>
      <ErrorState error={stats.error} />
      <Link className="text-button" to="/insights">
        看看近来的情绪变化 <ArrowRight size={15} />
      </Link>
      <div className="home-grid">
        <section>
          <div className="section-title">
            <h2>
              <BookOpen size={19} />
              最近的心情片段
            </h2>
            <Link to="/journals">
              全部记录 <ArrowRight size={15} />
            </Link>
          </div>
          <ErrorState error={journals.error} />
          {journals.data?.items.length === 0 && <Empty />}
          {journals.data?.items.map((j) => (
            <Link
              to={`/journals/${j.id}`}
              className="card journal-row"
              key={j.id}
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
                      .toFormat("MM.dd HH:mm")}
                  </time>
                </div>
                <p>{j.body_preview || "给此刻的心情做了一个小小标记。"}</p>
                <div>
                  {j.event_tags.map((t) => (
                    <Pill key={t.code + t.label}>{t.label}</Pill>
                  ))}
                </div>
              </div>
              <ArrowRight size={16} />
            </Link>
          ))}
        </section>
        <section className="card care-invite">
          <Flower2 size={30} strokeWidth={1.2} />
          <span className="eyebrow">A MOMENT OF CARE</span>
          <h2>
            给自己，
            <br />
            一段慢下来的时间
          </h2>
          <p>
            写一句话、休息一小会儿，
            <br />
            挑选此刻适合你的关怀活动。
          </p>
          <Link className="button secondary" to="/care">
            去看看 <ArrowRight size={16} />
          </Link>
          <small>每一步都可以选择，也随时可以停下。</small>
        </section>
      </div>
    </>
  );
}
