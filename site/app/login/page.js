"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password: pw });
        if (error) throw error;
      }
      const { error: e2 } = await supabase.auth.signInWithPassword({ email, password: pw });
      if (e2) throw e2;
      let { data: ok } = await supabase.rpc("has_active_license");
      if (!ok) {
        if (!key.trim()) throw new Error("Нет активной лицензии. Введите ключ доступа.");
        const { error: e3 } = await supabase.rpc("redeem_license", { license_key: key.trim() });
        if (e3) throw e3;
        const r = await supabase.rpc("has_active_license");
        ok = r.data;
        if (!ok) throw new Error("Ключ не активировал доступ.");
      }
      router.replace("/dashboard");
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <div className="authcard">
        <div className="h1" style={brandStyle}>▶ YT Uploader</div>
        <p className="sub">Войдите в личный кабинет</p>
        <div className="card">
          <div className="tabs">
            <button className={mode === "login" ? "btn" : "btn ghost"} onClick={() => setMode("login")}>Вход</button>
            <button className={mode === "signup" ? "btn" : "btn ghost"} onClick={() => setMode("signup")}>Регистрация</button>
          </div>
          <form onSubmit={submit}>
            <label className="label">Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <label className="label">Пароль</label>
            <input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required />
            <label className="label">Ключ доступа (при первом входе)</label>
            <input className="input" value={key} onChange={(e) => setKey(e.target.value)} placeholder="YTU-XXXX-XXXX-XXXX" />
            <div style={gapStyle} />
            <button className="btn" style={fullBtn} disabled={busy}>{busy ? "Подключение…" : (mode === "login" ? "Войти" : "Создать аккаунт")}</button>
            {err ? <div className="err">⚠ {err}</div> : null}
          </form>
        </div>
        <p className="muted" style={footStyle}>Нет ключа? Обратитесь к администратору.</p>
      </div>
    </div>
  );
}

const brandStyle = { color: "#4f46e5" };
const gapStyle = { height: "8px" };
const fullBtn = { width: "100%" };
const footStyle = { fontSize: "12px", marginTop: "16px", textAlign: "center" };
