import { Link, NavLink, Navigate, Outlet } from "react-router-dom";
import {
  BookHeart,
  ChartNoAxesCombined,
  Flower2,
  House,
  LogOut,
  Settings2,
  Sprout,
} from "lucide-react";
import { useAuth } from "./context";
import { Loading } from "../components/UI";

export function Layout() {
  const { user, loading, logout } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <Sprout />
          <span>
            心晴<small>MOOD & MOMENTS</small>
          </span>
        </Link>
        <span className="nav-caption">留一点时间给自己</span>
        <nav>
          <NavLink to="/" end>
            <House />
            今天
          </NavLink>
          <NavLink to="/journals">
            <BookHeart />
            我的日记
          </NavLink>
          <NavLink to="/insights">
            <ChartNoAxesCombined />
            情绪回顾
          </NavLink>
          <NavLink to="/care">
            <Flower2 />
            自我关怀
          </NavLink>
          <NavLink to="/settings">
            <Settings2 />
            我的设置
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <span>☀</span>
          <p>
            所有感受，
            <br />
            都值得被看见。
          </p>
          <small>按自己的节奏，慢慢来。</small>
        </div>
        <button
          className="logout"
          onClick={() =>
            void logout().catch(() => window.alert("退出未完成，请重试"))
          }
        >
          <LogOut size={17} />
          退出登录
        </button>
      </aside>
      <main className="main">
        <div className="topbar">
          <span>给情绪一点空间</span>
          <Link to="/settings" className="profile">
            <span className="avatar">
              {(user.nickname || "晴").slice(0, 1)}
            </span>
            {user.nickname || "心晴朋友"}
          </Link>
        </div>
        <Outlet />
        <footer>心晴 · 记录当下，温柔地照顾自己</footer>
      </main>
      <nav className="mobile-nav">
        <NavLink to="/" end>
          <House />
          今天
        </NavLink>
        <NavLink to="/journals">
          <BookHeart />
          日记
        </NavLink>
        <NavLink to="/care">
          <Flower2 />
          关怀
        </NavLink>
        <NavLink to="/settings">
          <Settings2 />
          我的
        </NavLink>
      </nav>
    </div>
  );
}
