"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { supabase } from "@/lib/supabase";

function fmt(d) { return d ? new Date(d).toLocaleDateString("ru-RU") : "бессрочно"; }

function Inner() {
  const [rows, setRows] = useState([]);
  const [newKey, setNewKey] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const { data } = await supabase
      .from("licenses")
      .select("key,status,plan,expires_at,activated_at")
      .order("created_at", { ascending: false });
    setRows(data || []);
  }
  useEffect(() => { load(); }, []);

  async function redeem(e) {
    e.preventDefault();
    setMsg(""); setBusy(true);
    const { error } = await supabase.rpc("redeem_license", { license_key: newKey.trim() });
    setBusy(false);
    if (error) { setMsg("⚠ " + error.message); return; }
    setMsg("✓ Ключ активирован"); setNewKey(""); load();
  }

  return (
    <div>
      <h1 className="h1">Ключи доступа</h1>
      <p className="sub">Ваши лицензии и активация новых ключей</p>
      <div className="card" style={mb}>
        <h3>Активировать ключ</h3>
        <form onSubmit={redeem} className="row" style={formRow}>
          <input className="input" style={grow} value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="YTU-XXXX-XXXX-XXXX" required />
          <button className="btn" disabled={busy}>{busy ? "…" : "Активировать"}</button>
        </form>
        {msg ? <div className={msg[0] === "✓" ? "ok" : "err"}>{msg}</div> : null}
      </div>
      <div className="card">
        <h3>Мои ключи</h3>
        <table className="table">
          <thead><tr><th>Ключ</th><th>Статус</th><th>Тариф</th><th>Действует до</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td><span className="code">{r.key}</span></td>
                <td><span className={r.status === "active" ? "pill ok" : "pill off"}>{r.status === "active" ? "активен" : "отключён"}</span></td>
                <td className="muted">{r.plan}</td>
                <td className="muted">{fmt(r.expires_at)}</td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan="4" className="muted">Нет привязанных ключей.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const mb = { marginBottom: "16px" };
const formRow = { alignItems: "center" };
const grow = { flex: 1, minWidth: "220px" };

export default function Page() {
  return (<AuthGuard><Inner /></AuthGuard>);
}
