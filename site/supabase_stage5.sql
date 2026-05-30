-- ============================================================
--  YouTube Auto Uploader — Supabase дополнения (Этап 5: сайт)
--  Запустите целиком после основной схемы. Идемпотентно.
-- ============================================================

-- 1) РЕЙТИНГ: топ видео по просмотрам за период (публично безопасно)
create or replace function public.leaderboard(period text default 'week')
returns table (
  title text,
  views bigint,
  uploader text,
  account_label text,
  video_url text,
  uploaded_at timestamptz
)
language sql security definer set search_path = public as $$
  select v.title, coalesce(v.views,0) as views,
         coalesce(nullif(p.display_name,''), split_part(coalesce(p.email,''),'@',1), 'user') as uploader,
         v.account_label, v.video_url, v.uploaded_at
  from public.videos v
  join public.profiles p on p.id = v.user_id
  where v.uploaded_at >= case lower(period)
      when 'day'   then now() - interval '1 day'
      when 'week'  then now() - interval '7 days'
      when 'month' then now() - interval '30 days'
      else now() - interval '7 days' end
  order by coalesce(v.views,0) desc, v.uploaded_at desc
  limit 50;
$$;
grant execute on function public.leaderboard(text) to anon, authenticated;

-- 2) СВОДКА по текущему пользователю (для дашборда)
create or replace function public.my_stats()
returns table (
  total_videos bigint,
  total_accounts bigint,
  total_views bigint,
  views_day bigint,
  views_week bigint,
  views_month bigint
)
language sql security definer set search_path = public as $$
  select
    (select count(*) from public.videos   where user_id = auth.uid()),
    (select count(*) from public.accounts where user_id = auth.uid()),
    coalesce((select sum(views) from public.videos where user_id = auth.uid()),0),
    coalesce((select sum(views) from public.videos where user_id = auth.uid() and uploaded_at >= now() - interval '1 day'),0),
    coalesce((select sum(views) from public.videos where user_id = auth.uid() and uploaded_at >= now() - interval '7 days'),0),
    coalesce((select sum(views) from public.videos where user_id = auth.uid() and uploaded_at >= now() - interval '30 days'),0);
$$;
grant execute on function public.my_stats() to authenticated;

-- 3) АДМИН: выдача ключей (только is_admin)
create or replace function public.admin_generate_keys(n int default 1, p_plan text default 'standard', p_days int default null)
returns setof public.licenses
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.profiles where id = auth.uid() and is_admin) then
    raise exception 'Нет прав админа';
  end if;
  return query
  insert into public.licenses (key, plan, expires_at)
  select 'YTU-' || upper(substr(md5(random()::text),1,4)) || '-' ||
         upper(substr(md5(random()::text),1,4)) || '-' ||
         upper(substr(md5(random()::text),1,4)),
         coalesce(p_plan,'standard'),
         case when p_days is null then null else now() + (p_days || ' days')::interval end
  from generate_series(1, greatest(coalesce(n,1),1))
  returning *;
end; $$;
grant execute on function public.admin_generate_keys(int, text, int) to authenticated;

-- 4) АДМИН: список всех ключей
create or replace function public.admin_list_keys()
returns setof public.licenses
language sql security definer set search_path = public as $$
  select * from public.licenses
  where exists (select 1 from public.profiles where id = auth.uid() and is_admin)
  order by created_at desc;
$$;
grant execute on function public.admin_list_keys() to authenticated;

-- 5) АДМИН: вкл/выкл ключа
create or replace function public.admin_set_key_status(p_key text, p_status text)
returns public.licenses
language plpgsql security definer set search_path = public as $$
declare lic public.licenses;
begin
  if not exists (select 1 from public.profiles where id = auth.uid() and is_admin) then
    raise exception 'Нет прав админа';
  end if;
  update public.licenses set status = p_status where key = p_key returning * into lic;
  return lic;
end; $$;
grant execute on function public.admin_set_key_status(text, text) to authenticated;

-- 6) Флаг админа текущему пользователю: есть ли права
create or replace function public.am_i_admin()
returns boolean language sql security definer set search_path = public as $$
  select coalesce((select is_admin from public.profiles where id = auth.uid()), false);
$$;
grant execute on function public.am_i_admin() to authenticated;

-- 7) СДЕЛАТЬ СЕБЯ АДМИНОМ (замените email при необходимости)
update public.profiles set is_admin = true
where id = (select id from auth.users where email = 'arizonabakai@gmail.com');

-- 8) РЕЙТИНГ по ПОЛЬЗОВАТЕЛЯМ: кто сколько загрузил видео за период
create or replace function public.user_leaderboard(period text default 'week')
returns table (
  uploader text,
  uploads bigint,
  total_views bigint
)
language sql security definer set search_path = public as $$
  select coalesce(nullif(p.display_name,''), split_part(coalesce(p.email,''),'@',1), 'user') as uploader,
         count(*) as uploads,
         coalesce(sum(v.views),0) as total_views
  from public.videos v
  join public.profiles p on p.id = v.user_id
  where v.uploaded_at >= case lower(period)
      when 'day'   then now() - interval '1 day'
      when 'week'  then now() - interval '7 days'
      when 'month' then now() - interval '30 days'
      else now() - interval '7 days' end
  group by 1
  order by uploads desc, total_views desc
  limit 50;
$$;
grant execute on function public.user_leaderboard(text) to anon, authenticated;
