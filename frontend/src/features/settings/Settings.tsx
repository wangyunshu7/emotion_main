import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, LockKeyhole, ShieldCheck, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  api,
  clearPrivateStorage,
  downloadExport,
  message,
} from "../../api/client";
import { useAuth } from "../../app/context";
import { useInvalidate, useMetadata } from "../../hooks/data";
import { Confirm, ErrorState, Heading, Pill } from "../../components/UI";

export function Settings() {
  const auth = useAuth();
  const user = auth.user!;
  const meta = useMetadata();
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const client = useQueryClient();
  const [name, setName] = useState(user.nickname || "");
  const [zone, setZone] = useState(user.timezone);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const save = () =>
    run(async () => {
      await api("/me", "PATCH", { nickname: name || null, timezone: zone });
      await auth.refresh();
      await invalidate();
      setNotice("设置已保存");
    });
  const toggleAI = () =>
    run(async () => {
      await api("/me/consents/ai", "PUT", {
        enabled: !user.ai_enabled,
        policy_version: "v1",
      });
      setConsent(false);
      await auth.refresh();
      await invalidate();
      setNotice(
        user.ai_enabled
          ? "已撤回 AI 授权，原始日记仍保留。"
          : "已记录授权。AI 分析仍由你逐条主动触发。",
      );
    });
  const remove = () =>
    run(async () => {
      await api("/me", "DELETE", { password, confirmation });
      clearPrivateStorage();
      client.clear();
      await auth.refresh();
      navigate("/login", { replace: true });
    });
  return (
    <>
      <Heading
        eyebrow="YOUR SPACE, YOUR CHOICE"
        title="我的设置"
        subtitle="你可以决定记录什么，以及如何使用自己的数据。"
      />
      <ErrorState error={error} />
      {notice && (
        <div className="success" role="status">
          {notice}
        </div>
      )}
      <section className="card">
        <h2>关于你</h2>
        <div className="two-columns">
          <label>
            昵称
            <input
              value={name}
              maxLength={30}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            记录时区
            <input
              value={zone}
              list="timezones"
              onChange={(e) => setZone(e.target.value)}
            />
            <datalist id="timezones">
              {[
                "Asia/Shanghai",
                "Asia/Tokyo",
                "Europe/London",
                "America/New_York",
                "UTC",
              ].map((z) => (
                <option key={z}>{z}</option>
              ))}
            </datalist>
          </label>
        </div>
        <p className="muted">
          账号：{user.email}。修改时区后，统计会重新分组，已有周回顾将失效。
        </p>
        <button
          className="button secondary"
          disabled={busy}
          onClick={() => void save()}
        >
          保存设置
        </button>
      </section>
      <section className="card">
        <div className="section-title">
          <h2>
            <ShieldCheck size={20} /> AI 处理设置
          </h2>
          <Pill>{user.ai_enabled ? "已授权" : "未授权"}</Pill>
        </div>
        <p>
          AI
          可整理你主动提交的日记，提示可能的关联。它不提供诊断，也不承诺实时监护。
        </p>
        <div className="notice">
          <strong>当前部署说明</strong>
          <p>{meta.data?.ai_description || "正在读取…"}</p>
          <p>
            单条分析只发送本条正文、情绪、评分与标签；周回顾在样本足够时发送必要统计、抽样记录及你确认的线索。不发送邮箱、会话或
            IP。
          </p>
        </div>
        <p className="muted">
          {meta.data?.ai_mode === "fake"
            ? "当前为本地开发模拟，结果不是实际模型分析。"
            : !meta.data?.ai_available
              ? "本部署暂未启用模型，授权后仍需部署者完成服务配置。"
              : "真实服务仅在你授权并主动触发时使用。"}
        </p>
        <button
          className="button secondary"
          disabled={busy}
          onClick={() => setConsent(true)}
        >
          {user.ai_enabled ? "撤回 AI 授权" : "阅读并授权 AI 处理"}
        </button>
      </section>
      <section className="card">
        <h2>
          <LockKeyhole size={20} /> 隐私与数据
        </h2>
        <p>
          日记默认私密。主库删除会同时清理相关分析和回顾。备份按部署者设置的保留期淘汰；外部服务数据按实际供应商策略处理。
        </p>
        <div className="actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await downloadExport();
                setNotice("导出文件已生成。");
              })
            }
          >
            <Download size={17} />
            导出我的数据
          </button>
          <button
            className="button danger"
            disabled={busy}
            onClick={() => setDeleting(true)}
          >
            <Trash2 size={17} />
            注销账号
          </button>
        </div>
        <p className="muted">
          导出内容含私密日记，请妥善保存。首版不支持邮件找回密码。
        </p>
      </section>
      <Confirm
        open={consent}
        title={user.ai_enabled ? "撤回 AI 授权？" : "授权 AI 处理 v1"}
        busy={busy}
        onCancel={() => setConsent(false)}
        onConfirm={() => void toggleAI()}
      >
        {user.ai_enabled ? (
          <p>
            会删除已有 AI
            分析、线索修正与周回顾，原始日记保留。建议先导出需要保存的内容。
          </p>
        ) : (
          <>
            <p>{meta.data?.ai_description}</p>
            <p>
              我了解发送内容与用途，并选择授权；分析仍需主动触发，随时可撤回。
            </p>
          </>
        )}
      </Confirm>
      <Confirm
        open={deleting}
        title="注销并删除我的账号"
        busy={busy}
        confirmDisabled={confirmation !== "DELETE_MY_ACCOUNT" || !password}
        onCancel={() => setDeleting(false)}
        onConfirm={() => void remove()}
      >
        <p>将删除账号、日记、分析、反馈及回顾，无法在产品内恢复。</p>
        <label>
          当前密码
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <label>
          输入 DELETE_MY_ACCOUNT 确认
          <input
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
          />
        </label>
      </Confirm>
    </>
  );
}
