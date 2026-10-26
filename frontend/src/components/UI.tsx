import { useEffect, useRef, useState, type ReactNode } from "react";
import type { components } from "../api/generated";
import { useData } from "../hooks/data";
import { Link } from "react-router-dom";
import { ArrowUpRight, CloudSun, LoaderCircle } from "lucide-react";
import { message } from "../api/client";

export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> 正在准备你的空间…
    </div>
  );
}
export function ErrorState({ error }: { error: unknown }) {
  return error ? (
    <div className="error" role="alert">
      {message(error)}
    </div>
  ) : null;
}
export function Empty({
  text = "这里还没有记录，慢慢开始就好。",
}: {
  text?: string;
}) {
  return (
    <div className="empty">
      <CloudSun size={36} strokeWidth={1.2} />
      <p>{text}</p>
    </div>
  );
}
export function Heading({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow || "YOUR OWN PACE"}</span>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}
export function Pill({ children }: { children: ReactNode }) {
  return <span className="pill">{children}</span>;
}
export function CardLink({
  to,
  title,
  children,
}: {
  to: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <Link className="card card-link" to={to}>
      <div>
        <h3>{title}</h3>
        {children}
      </div>
      <ArrowUpRight size={20} />
    </Link>
  );
}
export function Confirm({
  open,
  title,
  children,
  onCancel,
  onConfirm,
  busy = false,
  confirmDisabled = false,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onCancel: () => void;
  onConfirm: () => void;
  busy?: boolean;
  confirmDisabled?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (open) dialog?.showModal();
    else dialog?.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
    >
      <h2>{title}</h2>
      <div>{children}</div>
      <div className="actions">
        <button
          autoFocus
          className="button secondary"
          onClick={onCancel}
          disabled={busy}
        >
          取消
        </button>
        <button
          className="button"
          onClick={onConfirm}
          disabled={busy || confirmDisabled}
        >
          {busy ? "处理中…" : "确认"}
        </button>
      </div>
    </dialog>
  );
}
export function SupportCard() {
  const [region, setRegion] = useState("CN");
  const resources = useData<components["schemas"]["SupportList"]>(
    "support",
    `/support-resources?region=${encodeURIComponent(region)}`,
  );
  return (
    <aside className="card support">
      <h3>此刻，先给自己一点支持</h3>
      <p>可以联系你信任的人，或寻求当地专业与紧急支持。这里不提供实时监护。</p>
      <p className="muted">
        具体资源请查看当地官方渠道；本应用不会自动联系他人。
      </p>
      <label>
        所在地区代码
        <input
          value={region}
          maxLength={16}
          onChange={(e) => setRegion(e.target.value.trim().toUpperCase())}
        />
      </label>
      {resources.data?.items.map((r) => (
        <div className="notice" key={r.id}>
          <strong>{r.title}</strong>
          <p>{r.description}</p>
          {r.contact_text && <p>{r.contact_text}</p>}
          {r.url && (
            <a href={r.url} target="_blank" rel="noreferrer">
              查看官方资源
            </a>
          )}
        </div>
      ))}
      {resources.data?.items.length === 0 && (
        <p className="muted">
          当前没有该地区经过核验且有效的资源条目，请查看当地官方渠道。
        </p>
      )}
      <ErrorState error={resources.error} />
    </aside>
  );
}
