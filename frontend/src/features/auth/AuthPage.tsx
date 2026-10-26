import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Sprout, ArrowRight } from "lucide-react";
import { api, message } from "../../api/client";
import type { SessionInfo } from "../../api/types";
import { useAuth } from "../../app/context";
import { ErrorState, Loading } from "../../components/UI";

type Fields = {
  email: string;
  password: string;
  nickname: string;
  adult: boolean;
  terms: boolean;
};
export function AuthPage({ registering = false }: { registering?: boolean }) {
  const auth = useAuth(),
    navigate = useNavigate();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>();
  if (auth.loading) return <Loading />;
  if (auth.user)
    return <Navigate to={registering ? "/welcome" : "/"} replace />;
  const submit = handleSubmit(async (fields) => {
    setError("");
    try {
      const session = await api<SessionInfo>(
        registering ? "/auth/register" : "/auth/login",
        "POST",
        registering
          ? {
              email: fields.email,
              password: fields.password,
              nickname: fields.nickname || null,
              adult_confirmed: fields.adult,
              terms_version: "v1",
              privacy_version: "v1",
            }
          : { email: fields.email, password: fields.password },
      );
      auth.accept(session);
      navigate(registering ? "/welcome" : "/");
    } catch (e) {
      setError(message(e));
    }
  });
  return (
    <div className="auth-page">
      <section className="auth-story">
        <Link className="brand" to="/">
          <Sprout />
          <span>
            心晴<small>MOOD & MOMENTS</small>
          </span>
        </Link>
        <div>
          <span className="eyebrow">A LITTLE SPACE FOR YOURSELF</span>
          <h1>
            让每一种情绪，
            <br />
            都有安放的地方。
          </h1>
          <p>
            记录生活的晴与雨，
            <br />
            在自己的节奏里，找回一点松弛。
          </p>
          <div className="auth-orbit">
            <Sprout size={100} strokeWidth={0.8} />
          </div>
        </div>
        <small>你的日记默认私密，只属于你。</small>
      </section>
      <section className="auth-form">
        <span className="eyebrow">WELCOME TO XINQING</span>
        <h2>{registering ? "从认识自己开始" : "欢迎回到自己的空间"}</h2>
        <p className="muted">
          {registering
            ? "每天一点记录，也是对自己的关心。"
            : "今天的你，感觉怎么样？"}
        </p>
        <ErrorState error={error || auth.error} />
        {auth.error && (
          <button className="text-button" onClick={() => void auth.refresh()}>
            重新连接
          </button>
        )}
        <form onSubmit={submit}>
          <label>
            邮箱
            <input
              type="email"
              autoComplete="email"
              {...register("email", { required: "请填写邮箱" })}
            />
          </label>
          {registering && (
            <label>
              怎么称呼你
              <input
                maxLength={30}
                autoComplete="nickname"
                {...register("nickname")}
              />
            </label>
          )}
          <label>
            密码
            <input
              type="password"
              autoComplete={registering ? "new-password" : "current-password"}
              {...register("password", {
                required: "请填写密码",
                minLength: registering
                  ? { value: 12, message: "密码至少 12 个字符" }
                  : undefined,
                maxLength: 128,
              })}
            />
          </label>
          {errors.password && (
            <p role="alert" className="field-error">
              {errors.password.message}
            </p>
          )}
          {registering && (
            <>
              <label className="check">
                <input
                  type="checkbox"
                  {...register("adult", { required: true })}
                />
                我确认已年满 18 岁
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  {...register("terms", { required: true })}
                />
                我已阅读并接受下方使用与隐私说明
              </label>
              <details className="notice">
                <summary>使用与隐私说明 v1</summary>
                <p>
                  本应用用于私人情绪记录和自我关怀，不提供诊断或实时监护。日记默认私密；AI
                  可单独授权并随时关闭。可以导出、删除数据与注销。主库删除即时处理，备份和外部服务按实际部署说明处理。首版暂不提供邮件找回，请妥善保管密码。
                </p>
              </details>
            </>
          )}
          {(errors.adult || errors.terms) && (
            <p className="field-error">请确认年龄并阅读使用说明</p>
          )}
          <button
            className="button full"
            disabled={isSubmitting || !!auth.error}
          >
            {isSubmitting ? "正在处理…" : registering ? "创建我的空间" : "登录"}
            <ArrowRight size={17} />
          </button>
        </form>
        <p className="auth-switch">
          {registering ? "已经有账号？" : "还没有账号？"}{" "}
          <Link to={registering ? "/login" : "/register"}>
            {registering ? "去登录" : "创建一个私密空间"}
          </Link>
        </p>
      </section>
    </div>
  );
}

export function Welcome() {
  return (
    <div className="card welcome">
      <Sprout size={52} />
      <span className="eyebrow">HELLO, YOURSELF</span>
      <h1>这里，不需要一直开心。</h1>
      <p>你可以只选一个心情，也可以写下一整天。没有标准答案，不必每天打卡。</p>
      <div className="notice">
        记录默认私密。AI
        整理由你主动开启和触发；跳过也可以使用日记、趋势与关怀活动。
      </div>
      <Link className="button" to="/journals/new">
        写下第一条记录
      </Link>
      <Link className="text-button" to="/settings">
        先看看隐私与 AI 设置
      </Link>
    </div>
  );
}
