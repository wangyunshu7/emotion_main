import { useEffect } from "react";
import { api, message } from "../api/client";
import { useJob } from "../hooks/data";
import { ErrorState, SupportCard } from "./UI";

export function JobPanel({
  id,
  onDone,
}: {
  id: string;
  onDone: (id: string) => void;
}) {
  const job = useJob(id);
  useEffect(() => {
    if (job.data?.status === "succeeded" && job.data.result)
      onDone(job.data.result.id);
  }, [job.data?.status, job.data?.result, onDone]);
  if (job.error) return <ErrorState error={job.error} />;
  if (job.data?.error_code === "SAFETY_REDIRECT") return <SupportCard />;
  if (job.data?.status === "failed")
    return (
      <div className="notice">
        这次整理没有完成（{job.data.error_code}
        ），你的记录已保存。可以稍后重试。
      </div>
    );
  if (job.data?.status === "cancelled")
    return (
      <div className="notice">任务已取消，或输入记录已更新。可以重新发起。</div>
    );
  return (
    <div className="notice" role="status">
      {job.data?.status === "running"
        ? "正在整理，请稍等…"
        : "任务已排队，等待后台处理。"}
      <button
        className="text-button"
        onClick={() =>
          void api(`/jobs/${id}/cancel`, "POST", {})
            .then(() => job.refetch())
            .catch((e) => window.alert(message(e)))
        }
      >
        取消
      </button>
    </div>
  );
}
