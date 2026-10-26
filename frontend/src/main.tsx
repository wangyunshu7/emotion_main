import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider, Link } from "react-router-dom";
import { AuthProvider } from "./app/context";
import { Layout } from "./app/Layout";
import { AuthPage, Welcome } from "./features/auth/AuthPage";
import { Home } from "./features/home/Home";
import { Journals } from "./features/journals/Journals";
import { JournalForm } from "./features/journals/JournalForm";
import { JournalDetail } from "./features/journals/JournalDetail";
import { Insights, ReviewDetail } from "./features/insights/Insights";
import { Care, ActivityDetail } from "./features/care/Care";
import { CareTimer } from "./features/care/CareTimer";
import { Settings } from "./features/settings/Settings";
import "./styles/global.css";

const client = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true, retry: false } },
});
const router = createBrowserRouter([
  { path: "/login", element: <AuthPage /> },
  { path: "/register", element: <AuthPage registering /> },
  {
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "/welcome", element: <Welcome /> },
      { path: "/journals", element: <Journals /> },
      { path: "/journals/new", element: <JournalForm /> },
      { path: "/journals/:id", element: <JournalDetail /> },
      { path: "/journals/:id/edit", element: <JournalForm /> },
      { path: "/insights", element: <Insights /> },
      { path: "/reviews/:id", element: <ReviewDetail /> },
      { path: "/care", element: <Care /> },
      { path: "/care/activities/:id", element: <ActivityDetail /> },
      { path: "/care/sessions/:id", element: <CareTimer /> },
      { path: "/settings", element: <Settings /> },
      {
        path: "*",
        element: (
          <div className="empty">
            <h1>这页暂时找不到了</h1>
            <Link to="/">回到今天</Link>
          </div>
        ),
      },
    ],
  },
]);
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
