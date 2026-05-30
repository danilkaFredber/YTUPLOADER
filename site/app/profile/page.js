"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { supabase } from "@/lib/supabase";

function Inner() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      const { data: u } = await supabase.auth.getUser();
      if (u.user) setEmail(u.user.email || "");
      const { data } = await supabase.from("profiles").select("display_name").eq("id", u.user.id).single();
      if (data) setName(data.display_name || "");
    })();
  }, []);

  async function save(e) {
    e.preventDefault();
    setMsg(""); setBusy(true);
    const { data: u } = await supabase.auth.getUser();
    const { error } = await supabase.from("profiles").update({ display_name: name }).eq("id", u.user.id);
    setBusy(false);
    setMsg(error ? "⚠ " + error.message : "✓ Сохранено");
  }

  return (
    <div>
      <h1 className="h1">Профиль</h1>
      <p className="sub">Данные вашего аккаунта</p>
      <div className="card" style={maxw}>
        <form onSubmit={save}>
          <label className="label">Email</label>
          <input className="input" value={email} disabled />
          <label className="label">Имя (отображается в рейтинге)</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ваше имя" />
          <div style={gap} />
          <button className="btn" disabled={busy}>{busy ? "…" : "Сохранить"}</button>
          {msg ? <div className={msg[0] === "✓" ? "ok" : "err"}>{msg}</div> : null}
        </form>
      </div>
    </div>
  );
}

const maxw = { maxWidth: "460px" };
const gap = { height: "8px" };

export default function Page() {
  return (<AuthGuard><Inner /></AuthGuard>);
}
