"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { supabase } from "@/lib/supabase";

function fmt(d) { return d ? new Date(d).toLocaleDateString("ru-RU") : "бессрочно"; }

function Inner() {
  const [isAdmin, setIsAdmin] = useState(null);
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(5);
  const [days, setDays] = useState("");
  const [generated, setGenerated] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function loadKeys() {
    const { data } = await supabase.rpc("admin_list_keys");
    setRows(data || []);
  }

  useEffect(() => {
    supabase.rpc("am_i_admin").then(({ data }) => {
      setIsAdmin(!!data);
      if (data) loadKeys();
    });
  }, []);

  async function generate(e) {
    e.preventDefault();
    setBusy(true); setMsg(""); setGenerated([]);
    const args = { n: Number(count) || 1, p_plan: "standard", p_days: days ? Number(days) : null };
    const { data, error } = await supabase.rpc("admin_generate_keys", args);
    setBusy(false);
    if (error) { setMsg("⚠ " + error.message); return; }
    setGenerated((data || []).map((r) => r.key));
    loadKeys();
  }

  async function toggle(key, status) {
    const next = status === "active" ? "disabled" : "active";
    await supabase.rpc("admin_set_key_status", { p_key: key, p_status: next });
    loadKeys();
  }

  if (isAdmin === null) return <div className="muted">Загрузка…</div>;
  if (!isAdmin) return <div className="card">Доступ только для администраторов.</div>;

  return (
    <div>
      <h1 className="h1">Админ-панель</h1>
      <p className="sub">Выдача и управление ключами доступа</p>
      <div className="card" style={mb}>
        <h3>Выдать новые ключи</h3>
        <form onSubmit={generate} className="row" style={formRow}>
          <div>
            <label className="label">Количество</label>
            <input className="input" type="number" min="1" max="100" value={count} onChange={(e) => setCount(e.target.value)} style={num} />
          </div>
          <div>
            <label className="label">Срок, дней (пусто = бессрочно)</label>
            <input className="input" type="number" min="1" value={days} onChange={(e) => setDays(e.target.value)} style={num} />
          </div>
          <div style={btnWrap}><button className="btn" disabled={busy}>{busy ? "…" : "Создать"}</button></div>
        </form>
        {msg ? <div className="err">{msg}</div> : null}
        {generated.length ? (
          <div style={genBox}>
            <div className="muted" style={sm}>Новые ключи (скопируйте):</div>
            {generated.map((k, i) => (<div key={i} className="code" style={genKey}>{k}</div>))}
          </div>
        ) : null}
      </div>
      <div className="card">
        <h3>Все ключи</h3>
        <table className="table">
          <thead><tr><th>Ключ</th><th>Статус</th><th>Тариф</th><th>До</th><th>Активирован</th><th></th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td><span className="code">{r.key}</span></td>
                <td><span className={r.status === "active" ? "pill ok" : "pill off"}>{r.status === "active" ? "активен" : "отключён"}</span></td>
                <td className="muted">{r.plan}</td>
                <td className="muted">{fmt(r.expires_at)}</td>
                <td className="muted">{r.activated_at ? "да" : "нет"}</td>
                <td><button className={r.status === "active" ? "btn ghost" : "btn"} onClick={() => toggle(r.key, r.status)} style={smbtn}>{r.status === "active" ? "Отключить" : "Включить"}</button></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan="6" className="muted">Ключей пока нет.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const mb = { marginBottom: "16px" };
const formRow = { alignItems: "flex-end" };
const num = { width: "140px" };
const btnWrap = { display: "flex", alignItems: "flex-end" };
const genBox = { marginTop: "14px" };
const sm = { fontSize: "12px", marginBottom: "6px" };
const genKey = { display: "inline-block", marginRight: "8px", marginBottom: "8px" };
const smbtn = { padding: "6px 10px", fontSize: "13px" };

export default function Page() {
  return (<AuthGuard><Inner /></AuthGuard>);
}
