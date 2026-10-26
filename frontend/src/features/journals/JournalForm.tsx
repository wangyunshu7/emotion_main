import { useEffect, useRef, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { useBlocker, useNavigate, useParams } from "react-router-dom";
import { DateTime } from "luxon";
import { z } from "zod";
import { ArrowLeft, Save } from "lucide-react";
import { api, message } from "../../api/client";
import { createRequestId } from "../../utils/requestId";
import type { Journal, JournalCreate, Tag } from "../../api/types";
import { useAuth } from "../../app/context";
import { useData, useInvalidate, useMetadata } from "../../hooks/data";
import { Confirm, ErrorState, Heading, Loading } from "../../components/UI";

type Fields = {
  mood_score: number;
  emotions: Tag[];
  body: string;
  event_tags: Tag[];
  occurred_at: string;
};
const validator = z.object({
  mood_score: z.number().int().min(1).max(5),
  emotions: z
    .array(z.object({ code: z.string(), label: z.string() }))
    .min(1)
    .max(5),
  body: z.string().max(10000),
});
function TagPicker({
  items,
  value,
  onChange,
}: {
  items: Tag[];
  value: Tag[];
  onChange: (tags: Tag[]) => void;
}) {
  const [custom, setCustom] = useState("");
  const selected = (tag: Tag) =>
    value.some((t) => t.code === tag.code && t.label === tag.label);
  const all = [...items, ...value.filter((t) => t.code === "custom")];
  return (
    <>
      <div className="chips">
        {all.map((t) => (
          <button
            key={t.code + t.label}
            type="button"
            className={`chip ${selected(t) ? "selected" : ""}`}
            aria-pressed={selected(t)}
            onClick={() =>
              onChange(
                selected(t)
                  ? value.filter(
                      (v) => v.code !== t.code || v.label !== t.label,
                    )
                  : [...value, t].slice(0, 5),
              )
            }
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="custom-tag">
        <input
          aria-label="自定义标签名称"
          value={custom}
          maxLength={20}
          placeholder="也可以用自己的词语…"
          onChange={(e) => setCustom(e.target.value)}
        />
        <button
          type="button"
          className="text-button"
          onClick={() => {
            const label = custom.trim();
            if (
              label &&
              value.length < 5 &&
              !value.some((t) => t.label === label)
            ) {
              onChange([...value, { code: "custom", label }]);
              setCustom("");
            }
          }}
        >
          添加
        </button>
      </div>
    </>
  );
}

export function JournalForm() {
  const { id } = useParams();
  const { user } = useAuth();
  const zone = user?.timezone || "Asia/Shanghai";
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const meta = useMetadata();
  const existing = useData<Journal>("journal", `/journals/${id}`, !!id);
  const [error, setError] = useState("");
  const [restore, setRestore] = useState(false);
  const [ready, setReady] = useState(false);
  const key = `emotion-draft:${user?.id}:${id || "new"}`;
  const requestId = useRef<string>(createRequestId());
  const skip = useRef(false);
  const initialized = useRef("");
  const {
    register,
    control,
    handleSubmit,
    reset,
    getValues,
    formState: { isDirty, isSubmitting },
  } = useForm<Fields>({
    defaultValues: {
      mood_score: 0,
      emotions: [],
      body: "",
      event_tags: [],
      occurred_at: DateTime.now().setZone(zone).toFormat("yyyy-MM-dd'T'HH:mm"),
    },
  });
  const values = useWatch({ control });
  useEffect(() => {
    if (initialized.current === key || (id && !existing.data)) return;
    initialized.current = key;
    if (existing.data) {
      const j = existing.data;
      reset({
        mood_score: j.mood_score,
        emotions: j.emotions,
        body: j.body,
        event_tags: j.event_tags,
        occurred_at: DateTime.fromISO(j.occurred_at)
          .setZone(zone)
          .toFormat("yyyy-MM-dd'T'HH:mm"),
      });
    }
    setReady(true);
    if (sessionStorage.getItem(key)) setRestore(true);
  }, [key, id, existing.data, reset, zone]);
  useEffect(() => {
    if (ready && isDirty && !restore)
      sessionStorage.setItem(
        key,
        JSON.stringify({ fields: values, requestId: requestId.current }),
      );
  }, [key, ready, isDirty, restore, values]);
  useEffect(() => {
    const leave = (e: BeforeUnloadEvent) => {
      if (isDirty && !skip.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [isDirty]);
  const blocker = useBlocker(() => isDirty && !skip.current);
  const submit = handleSubmit(async (fields) => {
    setError("");
    if (!validator.safeParse(fields).success) {
      setError("请选择心情评分和至少一种情绪，正文最多 10000 字。");
      return;
    }
    const occurred = DateTime.fromISO(fields.occurred_at, { zone });
    if (!occurred.isValid) {
      setError("发生时间无效");
      return;
    }
    const payload: JournalCreate = {
      ...fields,
      occurred_at: occurred.toUTC().toISO()!,
      client_request_id: requestId.current,
    };
    try {
      const saved = await api<Journal>(
        id ? `/journals/${id}` : "/journals",
        id ? "PATCH" : "POST",
        id
          ? {
              ...fields,
              occurred_at: payload.occurred_at,
              version: existing.data!.version,
            }
          : payload,
      );
      skip.current = true;
      sessionStorage.removeItem(key);
      reset(getValues());
      await invalidate();
      navigate(`/journals/${saved.id}`, { replace: true });
    } catch (e) {
      setError(message(e));
    }
  });
  if (id && existing.isLoading) return <Loading />;
  if (existing.error) return <ErrorState error={existing.error} />;
  return (
    <>
      <button className="text-button back" onClick={() => navigate(-1)}>
        <ArrowLeft size={16} />
        返回
      </button>
      <Heading
        title={id ? "重新看看这段心情" : "记录此刻"}
        subtitle="不用写得完整，也不用急着找到答案。"
      />
      <form className="card journal-form" onSubmit={submit}>
        <fieldset>
          <legend>此刻的心情，靠近哪一种？</legend>
          <Controller
            name="mood_score"
            control={control}
            render={({ field }) => (
              <div className="mood-picker">
                {(
                  meta.data?.scores || [
                    "很不好",
                    "不太好",
                    "一般",
                    "还不错",
                    "很好",
                  ]
                ).map((label, i) => (
                  <button
                    key={label}
                    type="button"
                    aria-pressed={field.value === i + 1}
                    aria-label={label}
                    className={`mood-option ${field.value === i + 1 ? "selected" : ""}`}
                    onClick={() => field.onChange(i + 1)}
                  >
                    <span>{["☂", "☁", "◒", "☀", "✦"][i]}</span>
                    {label}
                  </button>
                ))}
              </div>
            )}
          />
        </fieldset>
        <fieldset>
          <legend>
            给感受一个名字 <small>可多选，最多 5 项</small>
          </legend>
          <Controller
            name="emotions"
            control={control}
            render={({ field }) => (
              <TagPicker
                items={meta.data?.emotions || []}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </fieldset>
        <label className="body-label">
          想写下些什么？ <small>选填</small>
          <textarea
            rows={7}
            maxLength={10000}
            placeholder="今天发生了什么？那一刻，你有什么感受？只写一句也很好。"
            {...register("body")}
          />
          <small className="char-count">
            {Array.from(values.body || "").length} / 10000
          </small>
        </label>
        <fieldset>
          <legend>
            和什么有关？ <small>选填</small>
          </legend>
          <Controller
            name="event_tags"
            control={control}
            render={({ field }) => (
              <TagPicker
                items={meta.data?.event_tags || []}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </fieldset>
        <label>
          发生时间 <small>{zone}</small>
          <input type="datetime-local" required {...register("occurred_at")} />
        </label>
        <p className="muted">
          本标签页暂存草稿；关闭标签页或清理浏览器可能丢失。保存日记不会自动发送给
          AI。
        </p>
        <ErrorState error={error} />
        {error.includes("变化") && (
          <button
            type="button"
            className="text-button"
            onClick={() => void existing.refetch()}
          >
            加载最新版本后重试（保留当前文字）
          </button>
        )}
        <div className="actions">
          <button type="submit" className="button" disabled={isSubmitting}>
            <Save size={17} />
            {isSubmitting ? "正在保存…" : "保存这段心情"}
          </button>
        </div>
      </form>
      <Confirm
        open={restore}
        title="发现这次未完成的草稿"
        onCancel={() => {
          sessionStorage.removeItem(key);
          setRestore(false);
        }}
        onConfirm={() => {
          try {
            const draft = JSON.parse(sessionStorage.getItem(key) || "{}") as {
              fields: Fields;
              requestId: string;
            };
            reset(draft.fields, { keepDefaultValues: true });
            requestId.current = draft.requestId || createRequestId();
          } catch {
            sessionStorage.removeItem(key);
          }
          setRestore(false);
        }}
      >
        要继续上次的记录吗？草稿仅保存在当前标签页。
      </Confirm>
      <Confirm
        open={blocker.state === "blocked"}
        title="离开前，留一下这段心情？"
        onCancel={() => blocker.reset?.()}
        onConfirm={() => blocker.proceed?.()}
      >
        尚未保存到账号。离开后可在当前标签页恢复草稿。
      </Confirm>
    </>
  );
}
