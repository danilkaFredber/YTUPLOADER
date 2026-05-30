"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

const links = [
  ["/dashboard", "Обзор"],
  ["/leaderboard", "Рейтинг"],
  ["/keys", "Ключи"],
  ["/profile", "Профиль"],
];

export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [admin, setAdmin] = useState(false);

  useEffect(() => {
    supabase.rpc("am_i_admin").then(({ data }) => setAdmin(!!data));
  }, []);

  async function logout() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  return (
    <div className="nav">
      <div className="in">
        <span className="brand">▶ YT Uploader</span>
        {links.map((l) => (
          <a key={l[0]} href={l[0]} className={path === l[0] ? "active" : ""}>{l[1]}</a>
        ))}
        {admin ? <a href="/admin" className={path === "/admin" ? "active" : ""}>Админ</a> : null}
        <span className="sp" />
        <a onClick={logout}>Выйти</a>
      </div>
    </div>
  );
}
