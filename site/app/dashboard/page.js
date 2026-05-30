"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import BarChart from "@/components/BarChart";
import { supabase } from "@/lib/supabase";

function Inner() {
  const [stats, setStats] = useState(null);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const s = await supabase.rpc("my_stats");
      if (s.data && s.data.length) setStats(s.data[0]);
      const v = await supabase
        .from("videos")
        .select("title,views,account_label,video_url,uploaded_at")
        .order("views", { ascending: false })
        .limit(10);
      setVideos(v.data || []);
      setLoading(false);
    })();
  }, []);

  const chart = videos.slice(0, 8).map((v) => ({
    label: (v.title || "—").slice(0, 6),
    value: Number(v.views) || 0,
  }));

  if (loading) return <div className="muted">Загрузка данных…</div>;

  return (
    <div>
      <h1 className="h1">Обзор</h1>
      <p className="sub">Ваша статистика загрузок и просмотров</p>
      <div className="grid">
        <div className="card stat"><div className="v">{stats ? stats.total_views : 0}</div><div className="l">Всего просмотров</div></div>
        <div className="card stat"><div className="v">{stats ? stats.total_videos : 0}</div><div className="l">Видео</div></div>
        <div className="card stat"><div className="v">{stats ? stats.total_accounts : 0}</div><div className="l">Аккаунтов</div></div>
        <div className="card stat"><div className="v">{stats ? stats.views_week : 0}</div><div className="l">Просмотры за неделю</div></div>
      </div>
      <div style={mt}>
        <div className="card">
          <h3>Топ видео по просмотрам</h3>
          <p className="muted" style={sm}>Первые 8 видео</p>
          <BarChart data={chart} />
        </div>
      </div>
      <div style={mt}>
        <div className="card">
          <h3>Последние видео</h3>
          <table className="table">
            <thead><tr><th>Название</th><th>Аккаунт</th><th>Просмотры</th></tr></thead>
            <tbody>
              {videos.map((v, i) => (
                <tr key={i}>
                  <td>{v.video_url ? <a href={v.video_url} target="_blank" rel="noreferrer">{v.title || "—"}</a> : (v.title || "—")}</td>
                  <td className="muted">{v.account_label || "—"}</td>
                  <td>{v.views || 0}</td>
                </tr>
              ))}
              {!videos.length ? <tr><td colSpan="3" className="muted">Пока нет данных. Загрузите видео в программе.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const mt = { marginTop: "16px" };
const sm = { fontSize: "13px", margin: "0 0 10px" };

export default function Page() {
  return (<AuthGuard><Inner /></AuthGuard>);
}
