-- ============================================================
--  YouTube Auto Uploader — Supabase schema (Этап 2)
--  Запустите весь файл целиком: Supabase → SQL Editor → New query → Run.
--  Скрипт идемпотентный: можно запускать повторно без ошибок.
-- ============================================================

-- 1) PROFILES — зеркало пользователей из auth.users
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  is_admin boolean not null default false,
  created_at timestamptz not null default now()
);

-- 2) LICENSES — ключи доступа к программе
create table if not exists public.licenses (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  user_id uuid references auth.users(id) on delete set null,
  status text not null default 'active',      -- active | disabled
  plan text not null default 'standard',
  expires_at timestamptz,                      -- null = бессрочно
  created_at timestamptz not null default now(),
  activated_at timestamptz
);

-- 3) ACCOUNTS — профили YouTube-аккаунтов пользователя
create table if not exists public.accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  label text not null,
  created_at timestamptz not null default now(),
  unique (user_id, label)
);

-- 4) VIDEOS — статистика загруженных видео
create table if not exists public.videos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id uuid references public.accounts(id) on delete cascade,
  account_label text,
  title text,
  video_url text,
  views bigint default 0,
  uploaded_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (user_id, account_label, title)
);

-- ============================================================
--  Автосоздание профиля при регистрации
-- ============================================================
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================
--  Активация ключа (вызывается из программы/сайта)
--  Привязывает ключ к текущему пользователю и проверяет срок.
-- ============================================================
create or replace function public.redeem_license(license_key text)
returns public.licenses language plpgsql security definer set search_path = public as $$
declare lic public.licenses;
begin
  select * into lic from public.licenses where key = license_key;
  if lic.id is null then
    raise exception 'Ключ не найден';
  end if;
  if lic.status <> 'active' then
    raise exception 'Ключ отключён';
  end if;
  if lic.expires_at is not null and lic.expires_at < now() then
    raise exception 'Срок действия ключа истёк';
  end if;
  if lic.user_id is not null and lic.user_id <> auth.uid() then
    raise exception 'Ключ уже привязан к другому пользователю';
  end if;
  update public.licenses
    set user_id = auth.uid(), activated_at = coalesce(activated_at, now())
    where id = lic.id
    returning * into lic;
  return lic;
end; $$;

-- Проверка, что у текущего пользователя есть активная лицензия
create or replace function public.has_active_license()
returns boolean language sql security definer set search_path = public as $$
  select exists (
    select 1 from public.licenses
    where user_id = auth.uid()
      and status = 'active'
      and (expires_at is null or expires_at > now())
  );
$$;

-- ============================================================
--  Row Level Security: каждый видит только свои данные
-- ============================================================
alter table public.profiles  enable row level security;
alter table public.licenses  enable row level security;
alter table public.accounts  enable row level security;
alter table public.videos    enable row level security;

drop policy if exists "profiles self read"   on public.profiles;
drop policy if exists "profiles self update" on public.profiles;
drop policy if exists "licenses owner read"  on public.licenses;
drop policy if exists "accounts owner all"   on public.accounts;
drop policy if exists "videos owner all"     on public.videos;

create policy "profiles self read"   on public.profiles for select using (auth.uid() = id);
create policy "profiles self update" on public.profiles for update using (auth.uid() = id);
create policy "licenses owner read"  on public.licenses for select using (auth.uid() = user_id);
create policy "accounts owner all"   on public.accounts for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "videos owner all"     on public.videos   for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ============================================================
--  ВЫДАЧА КЛЮЧЕЙ (вручную). Раскомментируйте и измените ключи.
--  Ключи создаются с user_id = null и привязываются при активации.
-- ============================================================
-- insert into public.licenses (key, plan) values
--   ('YTU-AAAA-BBBB-CCCC', 'standard'),
--   ('YTU-DDDD-EEEE-FFFF', 'standard')
-- on conflict (key) do nothing;

-- Сгенерировать 5 случайных ключей одной командой:
-- insert into public.licenses (key)
-- select 'YTU-' || upper(substr(md5(random()::text), 1, 4)) || '-' ||
--        upper(substr(md5(random()::text), 1, 4)) || '-' ||
--        upper(substr(md5(random()::text), 1, 4))
-- from generate_series(1, 5);
