"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { supabase } from "@/lib/supabase";

const periods = [["day", "День"], ["week", "Неделя"], ["month", "Месяц"]];
const modes = [["videos", "По видео"], ["users", "По пользователям"]];

function Inner() {
  const [period, setPeriod] = useState("week");
  const [mode, setMode] = useState("videos");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const rpc = mode === "users" ? "user_leaderboard" : "leaderboard";
    supabase.rpc(rpc, { period }).then(({ data }) => {
      setRows(data || []);
      setLoading(false);
    });
  }, [period, mode]);

  const sub = mode === "users"
    ? "Кто сколько загрузил видео среди всех пользователей"
    : "Топ загруженных видео по просмотрам среди всех пользователей";

  return (
    <div>
      <h1 className="h1">Рейтинг</h1>
      <p className="sub">{sub}</p>
      <div className="tabs" style={modeStyle}>
        {modes.map((m) => (
          <button key={m[0]} className={mode === m[0] ? "btn" : "btn ghost"} onClick={() => setMode(m[0])}>{m[1]}</button>
        ))}
      </div>
      <div className="tabs" style={tabsStyle}>
        {periods.map((p) => (
          <button key={p[0]} className={period === p[0] ? "btn" : "btn ghost"} onClick={() => setPeriod(p[0])}>{p[1]}</button>
        ))}
      </div>
      <div className="card">
        {mode === "users" ? (
          <table className="table">
            <thead><tr><th>#</th><th>Пользователь</th><th>Загружено видео</th><th>Просмотры</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan="4" className="muted">Загрузка…</td></tr> : null}
              {!loading && rows.map((r, i) => (
                <tr key={i}>
                  <td className="rank">{i + 1}</td>
                  <td>{r.uploader}</td>
                  <td><strong>{r.uploads || 0}</strong></td>
                  <td className="muted">{r.total_views || 0}</td>
                </tr>
              ))}
              {!loading && !rows.length ? <tr><td colSpan="4" className="muted">Нет данных за этот период.</td></tr> : null}
            </tbody>
          </table>
        ) : (
          <table className="table">
            <thead><tr><th>#</th><th>Видео</th><th>Автор</th><th>Аккаунт</th><th>Просмотры</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan="5" className="muted">Загрузка…</td></tr> : null}
              {!loading && rows.map((r, i) => (
                <tr key={i}>
                  <td className="rank">{i + 1}</td>
                  <td>{r.video_url ? <a href={r.video_url} target="_blank" rel="noreferrer">{r.title || "—"}</a> : (r.title || "—")}</td>
                  <td>{r.uploader}</td>
                  <td className="muted">{r.account_label || "—"}</td>
                  <td>{r.views || 0}</td>
                </tr>
              ))}
              {!loading && !rows.length ? <tr><td colSpan="5" className="muted">Нет данных за этот период.</td></tr> : null}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const tabsStyle = { maxWidth: "320px", marginBottom: "16px" };
const modeStyle = { maxWidth: "260px", marginBottom: "10px" };

export default function Page() {
  return (<AuthGuard><Inner /></AuthGuard>);
}
