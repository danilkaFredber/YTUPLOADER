#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YouTube Auto Uploader v4 - GUI (без API, через браузер)."""

import re
import os
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False
import json
import time
import queue
import shutil
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

APP_VERSION = "v8"

BASE_DIR = Path(__file__).resolve().parent
PROFILES_DIR = BASE_DIR / "profiles"
SETTINGS_FILE = BASE_DIR / "settings.json"
ERRORS_DIR = BASE_DIR / "errors"
UPLOADS_FILE = BASE_DIR / "uploads.json"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
STUDIO_URL = "https://studio.youtube.com"
YOUTUBE_URL = "https://www.youtube.com"
UPLOAD_URL = "https://www.youtube.com/upload"

CATEGORIES = [
    "Без категории", "Film & Animation", "Autos & Vehicles", "Music",
    "Pets & Animals", "Sports", "Travel & Events", "Gaming",
    "People & Blogs", "Comedy", "Entertainment", "News & Politics",
    "Howto & Style", "Education", "Science & Technology",
]
PRIVACY_LABELS = {"private": "PRIVATE", "unlisted": "UNLISTED", "public": "PUBLIC"}
PRIVACY_RU = {"public": "Открытый доступ", "unlisted": "По ссылке", "private": "Приватный"}
PRIVACY_RU_INV = {v: k for k, v in PRIVACY_RU.items()}

# Светлая тема
FONT = "Segoe UI"
BG = "#f8fafc"
CARD = "#ffffff"
SIDEBAR = "#ffffff"
ACTIVE_BG = "#eef2ff"
ACCENT = "#4f46e5"
ACCENT_HOVER = "#4338ca"
TEXT = "#0f172a"
MUTED = "#64748b"
FIELD = "#f1f5f9"
EDGE = "#e2e8f0"
SUCCESS = "#10b981"
SOFT = "#6366f1"


def safe_name(name):
    return re.sub(r"[^\w\-.@ ]", "_", name).strip() or "account"


def profile_path(label):
    return PROFILES_DIR / safe_name(label)


def list_accounts():
    if not PROFILES_DIR.exists():
        return []
    return sorted([p.name for p in PROFILES_DIR.iterdir() if p.is_dir()])


BROWSER_MODE_LABELS = {
    "visible": "Видимый — окно показывается",
    "background": "В фоне — окно за экраном (рекомендуется)",
    "hidden": "Скрытый — без окна (headless)",
}
BROWSER_LABEL_TO_MODE = {v: k for k, v in BROWSER_MODE_LABELS.items()}


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_uploads():
    try:
        return json.loads(UPLOADS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_uploads(data):
    try:
        UPLOADS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def append_uploads(label, entries):
    data = load_uploads()
    data.setdefault(label, [])
    data[label].extend(entries)
    save_uploads(data)


def _parse_views(text):
    if not text:
        return None
    t = str(text).lower().replace("\u00a0", " ")
    mult = 1
    if any(x in t for x in ["k", "\u0442\u044b\u0441", "ngh"]):
        mult = 1000
    elif any(x in t for x in ["\u043c\u043b\u043d", "tri", " tr", "m"]):
        mult = 1000000
    elif any(x in t for x in ["\u043c\u043b\u0440\u0434", "b", "t\u1ef7"]):
        mult = 1000000000
    nums = re.findall(r"\d+[.,]?\d*", t.replace(" ", ""))
    if not nums:
        return None
    try:
        val = float(nums[0].replace(",", "."))
    except Exception:
        return None
    return int(val * mult)


class BrowserEngine:
    @staticmethod
    def _launch(p, profile, mode="visible"):
        profile.mkdir(parents=True, exist_ok=True)
        headless = (mode == "hidden")
        args = ["--disable-blink-features=AutomationControlled", "--no-first-run",
                "--no-default-browser-check"]
        if mode == "background":
            # окно создаётся, но уезжает за пределы экрана и не мешает работе
            args += ["--window-position=-32000,-32000", "--window-size=1280,820"]
        else:
            args += ["--start-maximized"]
        return p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=headless,
            args=args,
            no_viewport=True,
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"))

    @staticmethod
    def _first(page, selectors, timeout=15000):
        from playwright.sync_api import TimeoutError as PWTimeout
        per = max(1500, timeout // max(1, len(selectors)))
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                loc.wait_for(state="visible", timeout=per)
                return loc
            except (PWTimeout, Exception):
                continue
        raise RuntimeError("не найден элемент (" + selectors[0] + " и др.)")

    @staticmethod
    def _save_debug(page, log, tag):
        try:
            ERRORS_DIR.mkdir(parents=True, exist_ok=True)
            name = tag + "_" + time.strftime("%Y%m%d_%H%M%S") + ".png"
            page.screenshot(path=str(ERRORS_DIR / name), full_page=True)
            log("    📸 скриншот ошибки: errors/" + name + "  (URL: " + page.url + ")")
        except Exception:
            pass

    @staticmethod
    def login_interactive(profile, wait_event, log):
        with sync_playwright() as p:
            ctx = BrowserEngine._launch(p, profile, "visible")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass
            log("Окно браузера открыто. Войдите в аккаунт любым способом...")
            while not wait_event.is_set():
                page.wait_for_timeout(500)
            try:
                ctx.close()
            except Exception:
                pass
            log("\u0421\u0435\u0441\u0441\u0438\u044f \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0430.")

    @staticmethod
    def _open_content(page, log):
        m = re.search(r"/channel/(UC[\w-]+)", page.url)
        if m:
            cid = m.group(1)
            for tab in ["videos/upload", "videos"]:
                try:
                    page.goto(STUDIO_URL + "/channel/" + cid + "/" + tab, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2500)
                    if page.locator("ytcp-video-row").count() > 0:
                        return True
                except Exception:
                    continue
        try:
            BrowserEngine._first(page, ["#menu-item-1",
                'tp-yt-paper-icon-item:has-text("\u041a\u043e\u043d\u0442\u0435\u043d\u0442")',
                'tp-yt-paper-icon-item:has-text("Content")',
                'tp-yt-paper-icon-item:has-text("N\u1ed9i dung")'], 10000).click()
            page.wait_for_timeout(2500)
            return page.locator("ytcp-video-row").count() > 0
        except Exception:
            return False

    @staticmethod
    def fetch_stats(profile, mode, log, limit=60):
        results = []
        with sync_playwright() as p:
            ctx = BrowserEngine._launch(p, profile, mode)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(45000)
            try:
                page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                if "accounts.google.com" in page.url:
                    raise RuntimeError("\u041d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d \u0432\u0445\u043e\u0434. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 '\u0412\u043e\u0439\u0442\u0438 \u0437\u0430\u043d\u043e\u0432\u043e'.")
                if not BrowserEngine._open_content(page, log):
                    BrowserEngine._save_debug(page, log, "stats")
                    raise RuntimeError("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0440\u0430\u0437\u0434\u0435\u043b '\u041a\u043e\u043d\u0442\u0435\u043d\u0442'.")
                try:
                    page.wait_for_selector("ytcp-video-row", timeout=30000)
                except Exception:
                    BrowserEngine._save_debug(page, log, "stats")
                    raise RuntimeError("\u0421\u043f\u0438\u0441\u043e\u043a \u0432\u0438\u0434\u0435\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.")
                page.wait_for_timeout(1500)
                rows = page.locator("ytcp-video-row")
                count = min(rows.count(), limit)
                for i in range(count):
                    row = rows.nth(i)
                    try:
                        title = row.locator("#video-title").first.inner_text(timeout=2000).strip()
                    except Exception:
                        title = ""
                    vid = ""
                    try:
                        href = row.locator("a#video-title, a#thumbnail-anchor").first.get_attribute("href", timeout=1500) or ""
                        mm = re.search(r"/video/([^/]+)/", href)
                        if mm:
                            vid = mm.group(1)
                    except Exception:
                        pass
                    views = ""
                    for sel in [".tablecell-views #views", "#views", ".tablecell-views"]:
                        try:
                            views = row.locator(sel).first.inner_text(timeout=1200).strip()
                            if views:
                                break
                        except Exception:
                            continue
                    if title or views:
                        results.append({"title": title, "views": views, "id": vid})
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
        return results

    @staticmethod
    def _open_upload_dialog(page, log):
        for attempt in range(1, 4):
            # Способ 1: прямой адрес загрузки (не зависит от языка)
            try:
                page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2800)
            except Exception:
                pass
            try:
                page.wait_for_selector('#select-files-button, ytcp-button#select-files-button, input[type="file"]',
                                       state="attached", timeout=10000)
                return True
            except Exception:
                pass
            # Способ 2: меню "Создать" (по ID кнопки, затем первый пункт)
            try:
                page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            try:
                BrowserEngine._first(page, ["ytcp-button#create-icon", "#create-icon",
                    'ytcp-button[aria-label*="Создать"]', 'ytcp-button[aria-label*="Create"]',
                    'ytcp-button[aria-label*="Tạo"]'], 12000).click()
                page.wait_for_timeout(900)
                BrowserEngine._first(page, ['tp-yt-paper-item#text-item-0', '#text-item-0',
                    'tp-yt-paper-item:has-text("Tải video lên")', 'tp-yt-paper-item:has-text("Tải lên")',
                    'tp-yt-paper-item:has-text("Загрузить видео")', 'tp-yt-paper-item:has-text("Upload videos")',
                    'tp-yt-paper-item:has-text("Upload")'], 8000).click()
            except Exception:
                pass
            # Способ 3: центральная кнопка на главной
            try:
                page.locator('ytcp-button:has-text("Tải video lên"), ytcp-button:has-text("Загрузить видео"), ytcp-button:has-text("Upload videos")').first.click(timeout=4000)
            except Exception:
                pass
            try:
                page.wait_for_selector('#select-files-button, ytcp-button#select-files-button, input[type="file"]',
                                       state="attached", timeout=8000)
                return True
            except Exception:
                log("    диалог загрузки не открылся (попытка " + str(attempt) + "/3), повторяю...")
        return False

    @staticmethod
    def _select_file(page, file_path, log):
        BrowserEngine._open_upload_dialog(page, log)
        try:
            with page.expect_file_chooser(timeout=15000) as fc_info:
                BrowserEngine._first(page, ["#select-files-button", "ytcp-button#select-files-button",
                    'ytcp-button:has-text("CHỌN TỆP")', 'ytcp-button:has-text("Chọn tệp")',
                    'ytcp-button:has-text("Tải video lên")',
                    'ytcp-button:has-text("Выбрать файлы")', 'ytcp-button:has-text("Select files")'], 12000).click()
            fc_info.value.set_files(file_path)
            return
        except Exception as e:
            log("    выбор через кнопку не сработал (" + str(e) + "), пробую напрямую...")
        page.wait_for_selector('input[type="file"]', state="attached", timeout=20000)
        page.locator('input[type="file"]').first.set_input_files(file_path, timeout=60000)

    @staticmethod
    def upload(profile, jobs, privacy, category, mode, log, progress_cb):
        ok_count = fail_count = 0
        uploaded = []
        with sync_playwright() as p:
            log("Режим браузера: " + {"hidden": "скрытый (headless)", "background": "в фоне (за экраном)"}.get(mode, "видимый"))
            ctx = BrowserEngine._launch(p, profile, mode)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(60000)
            try:
                page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                if "accounts.google.com" in page.url:
                    BrowserEngine._save_debug(page, log, "login")
                    raise RuntimeError("Не выполнен вход в этот аккаунт. Нажмите 'Войти заново'.")
                total = len(jobs)
                for i, meta in enumerate(jobs, 1):
                    progress_cb(i - 1, total)
                    log("(" + str(i) + "/" + str(total) + ") Загружаю: " + Path(meta["path"]).name)
                    last_err = None
                    vurl = ""
                    for attempt in range(1, 3):
                        try:
                            vurl = BrowserEngine._upload_single(page, meta, privacy, category, log)
                            last_err = None
                            break
                        except Exception as e:
                            last_err = e
                            log("    попытка " + str(attempt) + " не удалась: " + str(e))
                            BrowserEngine._save_debug(page, log, "upload")
                            try:
                                page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
                                page.wait_for_timeout(1800)
                            except Exception:
                                pass
                    if last_err:
                        fail_count += 1
                        log("    Пропускаю: " + str(last_err))
                    else:
                        ok_count += 1
                        uploaded.append({"title": meta.get("title") or Path(meta["path"]).stem, "url": vurl or "", "date": time.strftime("%Y-%m-%d %H:%M")})
                        log("    Готово: " + Path(meta["path"]).name)
                    progress_cb(i, total)
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
        return ok_count, fail_count, uploaded

    @staticmethod
    def manual_upload(profile, file_path, log):
        with sync_playwright() as p:
            ctx = BrowserEngine._launch(p, profile, "visible")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(60000)
            try:
                page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            try:
                BrowserEngine._select_file(page, file_path, log)
                log("    файл подставлен. Заполните детали и опубликуйте вручную.")
            except Exception as e:
                log("    авто-открытие не удалось (" + str(e) + "). Откройте загрузку вручную в окне.")
            log("🖥 Окно открыто. Доделайте загрузку вручную и закройте окно браузера.")
            while True:
                try:
                    if not ctx.pages or page.is_closed():
                        break
                    page.wait_for_timeout(1000)
                except Exception:
                    break
            try:
                ctx.close()
            except Exception:
                pass
            log("Окно закрыто.")

    @staticmethod
    def _upload_single(page, meta, privacy, category, log):
        BrowserEngine._select_file(page, meta["path"], log)
        log("    файл отправлен, ждём форму деталей...")
        title = meta.get("title") or Path(meta["path"]).stem
        try:
            tbox = BrowserEngine._first(page, ['#title-textarea #textbox',
                'ytcp-social-suggestions-textbox[label*="Название"] #textbox',
                'ytcp-mention-textbox[label*="Название"] #textbox', '#textbox'], 60000)
            tbox.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            tbox.type(title[:99], delay=8)
        except Exception as e:
            log("    не удалось заполнить заголовок: " + str(e))
        desc = meta.get("description") or ""
        if desc:
            try:
                dbox = page.locator('#description-textarea #textbox, #description-container #textbox').first
                dbox.click()
                dbox.type(desc, delay=4)
            except Exception as e:
                log("    не удалось заполнить описание: " + str(e))
        try:
            page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click(timeout=5000)
        except Exception:
            pass
        tags = meta.get("tags") or ""
        if tags:
            try:
                page.locator('#toggle-button, ytcp-button:has-text("Показать больше"), ytcp-button:has-text("Show more"), ytcp-button:has-text("Hiển thêm")').first.click(timeout=4000)
                page.wait_for_timeout(600)
                tag_input = page.locator('#tags-container #text-input, input[aria-label*="тег"]').first
                tag_input.click(timeout=4000)
                tag_input.type(tags, delay=4)
            except Exception:
                pass
        for _ in range(3):
            try:
                BrowserEngine._first(page, ['#next-button', 'ytcp-button:has-text("Далее")', 'ytcp-button:has-text("Next")'], 8000).click()
                page.wait_for_timeout(700)
            except Exception:
                break
        label = PRIVACY_LABELS.get(privacy, "PRIVATE")
        try:
            page.locator('tp-yt-paper-radio-button[name="' + label + '"]').first.click(timeout=8000)
        except Exception as e:
            log("    не удалось выбрать видимость: " + str(e))
        BrowserEngine._wait_processing(page, log)
        video_url = ""
        for sel in ['a[href*="youtu.be"]', '#share-url', '.video-url-fadeable a', 'a.ytcp-video-info']:
            try:
                loc = page.locator(sel).first
                video_url = (loc.get_attribute("href", timeout=1500) or loc.inner_text(timeout=1500) or "").strip()
                if video_url:
                    break
            except Exception:
                continue
        try:
            BrowserEngine._first(page, ['#done-button', 'ytcp-button:has-text("Готово")', 'ytcp-button:has-text("Done")'], 10000).click()
            page.wait_for_timeout(2500)
        except Exception as e:
            log("    кнопка 'Готово' не нажалась: " + str(e))
        try:
            page.locator('ytcp-button:has-text("Закрыть"), ytcp-button:has-text("Close")').first.click(timeout=4000)
        except Exception:
            pass
        return video_url

    @staticmethod
    def _wait_processing(page, log, timeout=1800):
        start = time.time()
        while time.time() - start < timeout:
            try:
                txt = page.locator('.progress-label, ytcp-video-upload-progress').first.inner_text(timeout=2000)
            except Exception:
                txt = ""
            low = (txt or "").lower()
            if any(k in low for k in ["заверш", "обработк", "complete", "processing", "проверк"]):
                return
            try:
                if page.locator('#done-button').first.is_enabled(timeout=1000):
                    return
            except Exception:
                pass
            page.wait_for_timeout(2000)


# ===================== Cloud (Supabase) =====================
SUPABASE_URL = "https://ugiemeikxcmbxhjcuinl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVnaWVtZWlreGNtYnhoamN1aW5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwOTEwODUsImV4cCI6MjA5NTY2NzA4NX0.TSOmH9ddPS15MR2fbg8p9T4dDP2V8kjuRil5UdYoqXE"
SESSION_FILE = BASE_DIR / "session.json"
SESSION = {}


def load_session():
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_session(data):
    try:
        SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def clear_session():
    try:
        SESSION_FILE.unlink()
    except Exception:
        pass


class Cloud:
    @staticmethod
    def _headers(token=None):
        h = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
        if token:
            h["Authorization"] = "Bearer " + token
        return h

    @staticmethod
    def _err(r, default):
        try:
            j = r.json()
            return j.get("msg") or j.get("error_description") or j.get("message") or j.get("error") or default
        except Exception:
            return default

    @staticmethod
    def sign_in(email, password):
        r = requests.post(SUPABASE_URL + "/auth/v1/token?grant_type=password",
                          headers=Cloud._headers(), json={"email": email, "password": password}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(Cloud._err(r, "Не удалось войти. Проверьте email и пароль."))
        return r.json()

    @staticmethod
    def sign_up(email, password):
        r = requests.post(SUPABASE_URL + "/auth/v1/signup",
                          headers=Cloud._headers(), json={"email": email, "password": password}, timeout=30)
        if r.status_code not in (200, 201):
            raise RuntimeError(Cloud._err(r, "Не удалось зарегистрироваться."))
        return r.json()

    @staticmethod
    def refresh(refresh_token):
        r = requests.post(SUPABASE_URL + "/auth/v1/token?grant_type=refresh_token",
                          headers=Cloud._headers(), json={"refresh_token": refresh_token}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError("refresh failed")
        return r.json()

    @staticmethod
    def redeem_license(token, key):
        r = requests.post(SUPABASE_URL + "/rest/v1/rpc/redeem_license",
                          headers=Cloud._headers(token), json={"license_key": key}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(Cloud._err(r, "Не удалось активировать ключ."))
        return r.json()

    @staticmethod
    def has_active_license(token):
        r = requests.post(SUPABASE_URL + "/rest/v1/rpc/has_active_license",
                          headers=Cloud._headers(token), json={}, timeout=30)
        if r.status_code == 401:
            raise RuntimeError("unauthorized")
        if r.status_code != 200:
            return False
        return bool(r.json())

    @staticmethod
    def user_id():
        u = SESSION.get("user") or {}
        return u.get("id")

    @staticmethod
    def _refresh_session():
        rt = SESSION.get("refresh_token")
        if not rt:
            return False
        try:
            ns = Cloud.refresh(rt)
            if ns.get("access_token"):
                ns["email"] = SESSION.get("email")
                SESSION.update(ns)
                save_session(SESSION)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _upsert(path, rows):
        if not REQUESTS_AVAILABLE or not rows:
            return
        def do():
            h = Cloud._headers(SESSION.get("access_token"))
            h["Prefer"] = "resolution=merge-duplicates,return=minimal"
            return requests.post(SUPABASE_URL + path, headers=h, json=rows, timeout=30)
        try:
            r = do()
            if r.status_code == 401 and Cloud._refresh_session():
                r = do()
        except Exception:
            pass

    @staticmethod
    def upsert_account(label):
        uid = Cloud.user_id()
        if not uid:
            return
        Cloud._upsert("/rest/v1/accounts?on_conflict=user_id,label",
                      [{"user_id": uid, "label": label}])

    @staticmethod
    def push_uploaded(label, uploaded):
        uid = Cloud.user_id()
        if not uid or not uploaded:
            return
        rows = [{"user_id": uid, "account_label": label,
                 "title": u.get("title"), "video_url": u.get("url")} for u in uploaded]
        Cloud._upsert("/rest/v1/videos?on_conflict=user_id,account_label,title", rows)

    @staticmethod
    def push_views(label, stats_rows):
        uid = Cloud.user_id()
        if not uid or not stats_rows:
            return
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rows = []
        for r in stats_rows:
            v = _parse_views(r.get("views", "")) or 0
            rows.append({"user_id": uid, "account_label": label,
                         "title": r.get("title"), "views": v, "updated_at": ts})
        Cloud._upsert("/rest/v1/videos?on_conflict=user_id,account_label,title", rows)


class LoginGate(tk.Tk):
    def __init__(self):
        super().__init__()
        self.authorized = False
        self.session = {}
        self._mode = "login"
        self.title("YouTube Auto Uploader " + APP_VERSION + " — Вход")
        self.configure(bg=BG)
        self.geometry("440x580")
        self.resizable(False, False)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Accent.TButton", background=ACCENT, foreground="white", borderwidth=0, focuscolor=ACCENT, padding=(10, 8), font=(FONT, 10, "bold"))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#a5b4fc")])
        style.configure("Ghost.TButton", background=FIELD, foreground=TEXT, borderwidth=0, padding=(10, 8), font=(FONT, 10))
        style.map("Ghost.TButton", background=[("active", EDGE)])
        self._build()

    def _entry(self, parent, show=None):
        e = tk.Entry(parent, bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 11))
        if show:
            e.config(show=show)
        e.pack(fill="x", ipady=6, pady=(2, 12))
        return e

    def _build(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=30, pady=30)
        tk.Label(wrap, text="▶ YT Uploader", bg=BG, fg=ACCENT, font=(FONT, 19, "bold")).pack(anchor="w")
        tk.Label(wrap, text="Войдите и активируйте ключ доступа", bg=BG, fg=MUTED, font=(FONT, 11)).pack(anchor="w", pady=(2, 20))
        card = tk.Frame(wrap, bg=CARD, highlightbackground=EDGE, highlightthickness=1)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=22, pady=22)
        tabs = tk.Frame(inner, bg=CARD)
        tabs.pack(fill="x", pady=(0, 16))
        self.tab_login = ttk.Button(tabs, text="Вход", style="Accent.TButton", command=lambda: self._set_mode("login"))
        self.tab_login.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.tab_signup = ttk.Button(tabs, text="Регистрация", style="Ghost.TButton", command=lambda: self._set_mode("signup"))
        self.tab_signup.pack(side="left", expand=True, fill="x", padx=(4, 0))
        tk.Label(inner, text="Email", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.email_e = self._entry(inner)
        tk.Label(inner, text="Пароль", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.pass_e = self._entry(inner, show="•")
        tk.Label(inner, text="Ключ доступа (при первом входе)", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.key_e = self._entry(inner)
        self.go_btn = ttk.Button(inner, text="Войти", style="Accent.TButton", command=self._submit)
        self.go_btn.pack(fill="x", pady=(6, 0))
        self.status = tk.StringVar(value="")
        tk.Label(inner, textvariable=self.status, bg=CARD, fg=MUTED, wraplength=330, justify="left", font=(FONT, 9)).pack(anchor="w", pady=(12, 0))
        tk.Label(wrap, text="Нет ключа? Обратитесь к администратору за доступом.", bg=BG, fg=MUTED, font=(FONT, 8)).pack(anchor="w", pady=(16, 0))
        self.email_e.focus_set()
        self.bind("<Return>", lambda e: self._submit())

    def _set_mode(self, m):
        self._mode = m
        if m == "login":
            self.tab_login.config(style="Accent.TButton")
            self.tab_signup.config(style="Ghost.TButton")
            self.go_btn.config(text="Войти")
        else:
            self.tab_login.config(style="Ghost.TButton")
            self.tab_signup.config(style="Accent.TButton")
            self.go_btn.config(text="Создать аккаунт")

    def _busy(self, b):
        try:
            self.go_btn.config(state="disabled" if b else "normal")
        except Exception:
            pass

    def _submit(self):
        email = self.email_e.get().strip()
        pw = self.pass_e.get()
        key = self.key_e.get().strip()
        if not email or not pw:
            self.status.set("Введите email и пароль.")
            return
        self._busy(True)
        self.status.set("Подключение...")
        mode = self._mode

        def work():
            try:
                if mode == "signup":
                    Cloud.sign_up(email, pw)
                sess = Cloud.sign_in(email, pw)
                token = sess.get("access_token")
                if not token:
                    raise RuntimeError("Нет токена доступа. Проверьте email/пароль.")
                try:
                    ok = Cloud.has_active_license(token)
                except Exception:
                    ok = False
                if not ok:
                    if not key:
                        raise RuntimeError("Нет активной лицензии. Введите ключ доступа.")
                    Cloud.redeem_license(token, key)
                    ok = Cloud.has_active_license(token)
                    if not ok:
                        raise RuntimeError("Ключ не активировал доступ.")
                sess["email"] = email
                self.after(0, lambda: self._ok(sess))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self._fail(msg))
        threading.Thread(target=work, daemon=True).start()

    def _ok(self, sess):
        self.session = sess
        save_session(sess)
        self.authorized = True
        self.destroy()

    def _fail(self, msg):
        self._busy(False)
        self.status.set("⚠ " + msg)


class UploaderGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Auto Uploader " + APP_VERSION)
        self.geometry("1120x760")
        self.minsize(1000, 700)
        self.configure(bg=BG)
        self.settings = load_settings()
        self.log_queue = queue.Queue()
        self.jobs = []
        self.template_desc = self.settings.get("template_desc", "")
        self.template_tags = self.settings.get("template_tags", "")
        self._login_event = None
        self._busy = False
        self._accounts = []
        self.browser_mode_var = tk.StringVar(value=BROWSER_MODE_LABELS.get(self.settings.get("browser_mode", "background"), BROWSER_MODE_LABELS["background"]))
        self.autorefresh_var = tk.BooleanVar(value=self.settings.get("autorefresh", False))
        self.autorefresh_interval_var = tk.StringVar(value=str(self.settings.get("autorefresh_interval", 10)))
        self.site_url_var = tk.StringVar(value=self.settings.get("site_url", ""))
        self.last_refresh_var = tk.StringVar(value="Последнее обновление: —")
        self._autorefresh_job = None
        self._autorefresh_running = False
        self.privacy_var = tk.StringVar(value=PRIVACY_RU.get(self.settings.get("privacy", "public"), PRIVACY_RU["public"]))
        self.category_var = tk.StringVar(value=self.settings.get("category", CATEGORIES[0]))
        self._setup_style()
        self._build_layout()
        self._refresh_accounts()
        self._show("upload")
        self.after(120, self._drain_log)
        self.after(1500, self._reschedule_autorefresh)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log("YouTube Auto Uploader " + APP_VERSION + " готов к работе.")
        if not PLAYWRIGHT_AVAILABLE:
            self.log("Playwright не установлен. Выполните: pip install playwright и playwright install chromium")

    def _setup_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=BG, foreground=TEXT, fieldbackground=FIELD, font=(FONT, 10))
        st.configure("TFrame", background=BG)
        st.configure("Accent.TButton", background=ACCENT, foreground="white", font=(FONT, 12, "bold"), borderwidth=0, padding=12)
        st.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#a5b4fc")])
        st.configure("Ghost.TButton", background=FIELD, foreground=TEXT, borderwidth=0, padding=8, font=(FONT, 10))
        st.map("Ghost.TButton", background=[("active", "#e2e8f0")])
        st.configure("Manual.TButton", background=SUCCESS, foreground="white", font=(FONT, 11, "bold"), borderwidth=0, padding=10)
        st.map("Manual.TButton", background=[("active", "#0e9f74"), ("disabled", "#9bd9c4")])
        st.configure("TCheckbutton", background=CARD, foreground=TEXT)
        st.map("TCheckbutton", background=[("active", CARD)])
        st.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT, arrowcolor=TEXT, borderwidth=0)
        st.configure("Accent.Horizontal.TProgressbar", background=ACCENT, troughcolor="#e2e8f0", borderwidth=0)
        st.configure("Stats.Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=26, borderwidth=0)
        st.configure("Stats.Treeview.Heading", background=FIELD, foreground=MUTED, font=(FONT, 10, "bold"), borderwidth=0)
        st.map("Stats.Treeview", background=[("selected", "#eef2ff")], foreground=[("selected", TEXT)])

    def _build_layout(self):
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)
        side = tk.Frame(container, bg=SIDEBAR, width=214)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=SIDEBAR)
        brand.pack(fill="x", pady=(22, 18), padx=20)
        tk.Label(brand, text="\u25b6  YT Uploader", bg=SIDEBAR, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(brand, text="без API · много аккаунтов", bg=SIDEBAR, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.nav_buttons = {}
        for key, label in [("upload", "Загрузка"), ("stats", "Статистика"), ("accounts", "Аккаунты"), ("settings", "Настройки")]:
            b = tk.Button(side, text="   " + label, anchor="w", bg=SIDEBAR, fg=TEXT, bd=0, relief="flat",
                          activebackground=ACTIVE_BG, activeforeground=ACCENT, font=(FONT, 11),
                          padx=16, pady=11, cursor="hand2", command=lambda k=key: self._show(k))
            b.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = b
        tk.Label(side, text=APP_VERSION, bg=SIDEBAR, fg=MUTED, font=(FONT, 9)).pack(side="bottom", anchor="w", padx=22, pady=14)
        tk.Frame(container, bg=EDGE, width=1).pack(side="left", fill="y")
        content = tk.Frame(container, bg=BG)
        content.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(content, bg=BG)
        self.body.pack(side="top", fill="both", expand=True)
        logcard = tk.Frame(content, bg=CARD, highlightbackground=EDGE, highlightthickness=1)
        logcard.pack(side="bottom", fill="x", padx=26, pady=(0, 18))
        tk.Label(logcard, text="Журнал", bg=CARD, fg=MUTED, font=(FONT, 9, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        self.log_text = tk.Text(logcard, height=6, bg="#f8fafc", fg="#334155", wrap="word", borderwidth=0, highlightthickness=0, font=("Consolas", 9))
        self.log_text.pack(fill="x", padx=14, pady=(4, 12))
        self.frames = {}
        for key in ("upload", "stats", "accounts", "settings"):
            self.frames[key] = tk.Frame(self.body, bg=BG)
        self._build_upload(self.frames["upload"])
        self._build_stats(self.frames["stats"])
        self._build_accounts(self.frames["accounts"])
        self._build_settings(self.frames["settings"])

    def _show(self, key):
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)
        for k, b in self.nav_buttons.items():
            active = (k == key)
            b.config(bg=ACTIVE_BG if active else SIDEBAR, fg=ACCENT if active else TEXT, font=(FONT, 11, "bold") if active else (FONT, 11))
        if key == "stats":
            try:
                self._load_local_stats()
            except Exception:
                pass

    def _card(self, parent, title=None, fill="x", expand=False, pady=(0, 14)):
        outer = tk.Frame(parent, bg=CARD, highlightbackground=EDGE, highlightthickness=1, bd=0)
        outer.pack(fill=fill, expand=expand, pady=pady)
        if title:
            tk.Label(outer, text=title, bg=CARD, fg=TEXT, font=(FONT, 12, "bold")).pack(anchor="w", padx=16, pady=(13, 0))
        body = tk.Frame(outer, bg=CARD)
        body.pack(fill="both", expand=True, padx=16, pady=13)
        return body

    def _section_header(self, parent, title, subtitle):
        h = tk.Frame(parent, bg=BG)
        h.pack(fill="x", pady=(2, 12))
        tk.Label(h, text=title, bg=BG, fg=TEXT, font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(h, text=subtitle, bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor="w", pady=(2, 0))

    def _build_upload(self, root):
        wrap = tk.Frame(root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=18)
        self._section_header(wrap, "Загрузка видео", "Выберите аккаунты и добавьте ролики — загрузка идёт во все сразу.")
        b1 = self._card(wrap, "Аккаунты для загрузки")
        lw = tk.Frame(b1, bg=CARD)
        lw.pack(fill="x")
        self.up_accounts = tk.Listbox(lw, height=3, selectmode="extended", bg=FIELD, fg=TEXT, selectbackground=ACCENT, selectforeground="white", borderwidth=0, highlightthickness=1, highlightbackground=EDGE, activestyle="none", exportselection=False, font=(FONT, 10))
        self.up_accounts.pack(side="left", fill="x", expand=True)
        sb1 = ttk.Scrollbar(lw, orient="vertical", command=self.up_accounts.yview)
        sb1.pack(side="left", fill="y")
        self.up_accounts.config(yscrollcommand=sb1.set)
        tk.Label(b1, text="Выделите один или несколько (Ctrl/Shift). Управление — во вкладке «Аккаунты».", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))
        b2 = self._card(wrap, "Видео и описания", fill="both", expand=True)
        mid = tk.Frame(b2, bg=CARD)
        mid.pack(fill="both", expand=True)
        left = tk.Frame(mid, bg=CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(left, text="Очередь", bg=CARD, fg=MUTED, font=(FONT, 9, "bold")).pack(anchor="w")
        self.video_list = tk.Listbox(left, height=7, bg=FIELD, fg=TEXT, selectbackground=ACCENT, selectforeground="white", borderwidth=0, highlightthickness=1, highlightbackground=EDGE, activestyle="none", font=(FONT, 10))
        self.video_list.pack(fill="both", expand=True, pady=6)
        self.video_list.bind("<<ListboxSelect>>", self.on_select)
        lb = tk.Frame(left, bg=CARD)
        lb.pack(fill="x")
        ttk.Button(lb, text="Файлы", style="Ghost.TButton", command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(lb, text="Папка", style="Ghost.TButton", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(lb, text="Убрать", style="Ghost.TButton", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(lb, text="Очистить", style="Ghost.TButton", command=self.clear_queue).pack(side="left", padx=6)
        right = tk.Frame(mid, bg=CARD)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Заголовок", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.title_entry = tk.Entry(right, bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 10))
        self.title_entry.pack(fill="x", ipady=5)
        tk.Label(right, text="Описание", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))
        self.desc_text = tk.Text(right, height=4, wrap="word", bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 10))
        self.desc_text.pack(fill="both", expand=True)
        tk.Label(right, text="Теги (через запятую)", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))
        self.tags_entry = tk.Entry(right, bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 10))
        self.tags_entry.pack(fill="x", ipady=5)
        rb = tk.Frame(right, bg=CARD)
        rb.pack(fill="x", pady=(8, 0))
        ttk.Button(rb, text="Сохранить", style="Ghost.TButton", command=self.save_current).pack(side="left", padx=(0, 6))
        ttk.Button(rb, text="Описание ко всем", style="Ghost.TButton", command=self.apply_desc_to_all).pack(side="left", padx=6)
        ttk.Button(rb, text="Теги ко всем", style="Ghost.TButton", command=self.apply_tags_to_all).pack(side="left", padx=6)
        b3 = self._card(wrap, "Параметры")
        orow = tk.Frame(b3, bg=CARD)
        orow.pack(fill="x")
        tk.Label(orow, text="Доступ:", bg=CARD, fg=TEXT).pack(side="left", padx=(0, 4))
        ttk.Combobox(orow, textvariable=self.privacy_var, state="readonly", width=16, values=list(PRIVACY_RU.values())).pack(side="left", padx=(0, 16))
        tk.Label(orow, text="Категория:", bg=CARD, fg=TEXT).pack(side="left", padx=(0, 4))
        ttk.Combobox(orow, textvariable=self.category_var, state="readonly", width=22, values=CATEGORIES).pack(side="left")
        runf = tk.Frame(wrap, bg=BG)
        runf.pack(fill="x", pady=(2, 0))
        self.upload_btn = ttk.Button(runf, text="Загрузить всё на YouTube", style="Accent.TButton", command=self.start_upload)
        self.upload_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.manual_btn = ttk.Button(runf, text="Ручная загрузка", style="Manual.TButton", command=self.manual_upload_selected)
        self.manual_btn.pack(side="left")
        prow = tk.Frame(wrap, bg=BG)
        prow.pack(fill="x", pady=(10, 0))
        self.progress = ttk.Progressbar(prow, mode="determinate", style="Accent.Horizontal.TProgressbar")
        self.progress.pack(side="left", fill="x", expand=True)
        self.status_var = tk.StringVar(value="Готов к работе")
        tk.Label(prow, textvariable=self.status_var, bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=10)

    def _build_stats(self, root):
        wrap = tk.Frame(root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=18)
        self._section_header(wrap, "Статистика просмотров", "Просмотры читаются прямо из YouTube Studio — без API.")
        top = self._card(wrap, "Аккаунты")
        lw = tk.Frame(top, bg=CARD)
        lw.pack(fill="x")
        self.st_accounts = tk.Listbox(lw, height=3, selectmode="extended", bg=FIELD, fg=TEXT, selectbackground=ACCENT, selectforeground="white", borderwidth=0, highlightthickness=1, highlightbackground=EDGE, activestyle="none", exportselection=False, font=(FONT, 10))
        self.st_accounts.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(lw, orient="vertical", command=self.st_accounts.yview)
        sb.pack(side="left", fill="y")
        self.st_accounts.config(yscrollcommand=sb.set)
        actrow = tk.Frame(top, bg=CARD)
        actrow.pack(fill="x", pady=(10, 0))
        self.stats_btn = ttk.Button(actrow, text="Обновить из YouTube", style="Accent.TButton", command=self.refresh_stats)
        self.stats_btn.pack(side="left")
        self.stats_total = tk.StringVar(value="")
        tk.Label(actrow, textvariable=self.stats_total, bg=CARD, fg=ACCENT, font=(FONT, 12, "bold")).pack(side="right")
        tcard = self._card(wrap, None, fill="both", expand=True)
        cols = ("account", "title", "views", "date")
        self.stats_tree = ttk.Treeview(tcard, columns=cols, show="headings", style="Stats.Treeview")
        for c, t, w in [("account", "Аккаунт", 150), ("title", "Видео", 360), ("views", "Просмотры", 110), ("date", "Загружено", 140)]:
            self.stats_tree.heading(c, text=t)
            self.stats_tree.column(c, width=w, anchor="w")
        self.stats_tree.pack(side="left", fill="both", expand=True)
        tsb = ttk.Scrollbar(tcard, orient="vertical", command=self.stats_tree.yview)
        tsb.pack(side="left", fill="y")
        self.stats_tree.configure(yscrollcommand=tsb.set)
        self.stats_status = tk.StringVar(value="Показана локальная история. Нажмите «Обновить» для просмотров из YouTube.")
        tk.Label(wrap, textvariable=self.stats_status, bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))

    def _build_accounts(self, root):
        wrap = tk.Frame(root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=18)
        self._section_header(wrap, "Аккаунты YouTube", "Вход обычным способом в окне браузера — без API и токенов.")
        b = self._card(wrap, "Мои аккаунты", fill="both", expand=True)
        row = tk.Frame(b, bg=CARD)
        row.pack(fill="both", expand=True)
        lw = tk.Frame(row, bg=CARD)
        lw.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.acc_accounts = tk.Listbox(lw, selectmode="extended", bg=FIELD, fg=TEXT, selectbackground=ACCENT, selectforeground="white", borderwidth=0, highlightthickness=1, highlightbackground=EDGE, activestyle="none", exportselection=False, font=(FONT, 10))
        self.acc_accounts.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lw, orient="vertical", command=self.acc_accounts.yview)
        sb.pack(side="left", fill="y")
        self.acc_accounts.config(yscrollcommand=sb.set)
        bcol = tk.Frame(row, bg=CARD)
        bcol.pack(side="left", fill="y")
        ttk.Button(bcol, text="+  Добавить", style="Accent.TButton", command=self.add_account).pack(fill="x", pady=(0, 8))
        ttk.Button(bcol, text="Войти заново", style="Ghost.TButton", command=self.relogin_account).pack(fill="x", pady=4)
        ttk.Button(bcol, text="Удалить", style="Ghost.TButton", command=self.remove_account).pack(fill="x", pady=4)
        tk.Label(b, text="«Войти заново» — для одного выбранного. «Удалить» — для всех выделенных.", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(10, 0))

    def _build_settings(self, root):
        wrap = tk.Frame(root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=18)
        self._section_header(wrap, "Настройки", "Общие параметры приложения.")
        b = self._card(wrap, "Браузер")
        tk.Label(b, text="Как показывать браузер во время загрузки и чтения статистики:", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        ttk.Combobox(b, textvariable=self.browser_mode_var, state="readonly", width=46,
                     values=list(BROWSER_MODE_LABELS.values())).pack(anchor="w", pady=(4, 0))

        ar = self._card(wrap, "Автообновление статистики")
        ttk.Checkbutton(ar, text="Автоматически обновлять просмотры в фоне", variable=self.autorefresh_var, command=self._reschedule_autorefresh).pack(anchor="w")
        arow = tk.Frame(ar, bg=CARD); arow.pack(fill="x", pady=(6, 0))
        tk.Label(arow, text="Каждые:", bg=CARD, fg=TEXT).pack(side="left", padx=(0, 6))
        ic = ttk.Combobox(arow, textvariable=self.autorefresh_interval_var, state="readonly", width=8, values=["5", "10", "15", "30", "60"])
        ic.pack(side="left")
        ic.bind("<<ComboboxSelected>>", lambda e: self._reschedule_autorefresh())
        tk.Label(arow, text="минут", bg=CARD, fg=TEXT).pack(side="left", padx=(6, 0))
        tk.Label(ar, textvariable=self.last_refresh_var, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))
        tk.Label(ar, text="Обновляются все сохранённые аккаунты в скрытом режиме — не мешает работе.", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")

        sc = self._card(wrap, "Мой сайт")
        srow = tk.Frame(sc, bg=CARD); srow.pack(fill="x")
        se = tk.Entry(srow, textvariable=self.site_url_var, bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 10))
        se.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        ttk.Button(srow, text="Открыть сайт", style="Ghost.TButton", command=self._open_site).pack(side="left")
        b2 = self._card(wrap, "Шаблоны по умолчанию")
        tk.Label(b2, text="Описание для новых видео", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.tpl_desc = tk.Text(b2, height=4, wrap="word", bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 10))
        self.tpl_desc.pack(fill="x", pady=(4, 8))
        self.tpl_desc.insert("1.0", self.template_desc)
        tk.Label(b2, text="Теги для новых видео", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.tpl_tags = tk.Entry(b2, bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 10))
        self.tpl_tags.pack(fill="x", ipady=5)
        self.tpl_tags.insert(0, self.template_tags)
        ttk.Button(b2, text="Сохранить шаблоны", style="Ghost.TButton", command=self.save_templates).pack(anchor="w", pady=(10, 0))
        ba = self._card(wrap, "Аккаунт")
        tk.Label(ba, text="Вы вошли: " + str(SESSION.get("email", "—")), bg=CARD, fg=TEXT, font=(FONT, 10)).pack(anchor="w")
        ttk.Button(ba, text="Выйти из аккаунта", style="Ghost.TButton", command=self.logout).pack(anchor="w", pady=(10, 0))
        b3 = self._card(wrap, "О программе")
        tk.Label(b3, text="YouTube Auto Uploader " + APP_VERSION + "\nЗагрузка без API · много аккаунтов · статистика просмотров.", bg=CARD, fg=MUTED, font=(FONT, 10), justify="left").pack(anchor="w")

    def logout(self):
        if not messagebox.askyesno("Выход", "Выйти из аккаунта? При следующем запуске нужно будет войти заново."):
            return
        clear_session()
        messagebox.showinfo("Выход", "Вы вышли из аккаунта. Приложение закроется.")
        try:
            self._persist_settings()
        except Exception:
            pass
        self.destroy()

    def save_templates(self):
        self.template_desc = self.tpl_desc.get("1.0", "end").strip()
        self.template_tags = self.tpl_tags.get().strip()
        self._persist_settings()
        self.log("Шаблоны сохранены.")

    def _selected(self, listbox):
        return [self._accounts[i] for i in listbox.curselection()]

    def _refresh_accounts(self):
        self._accounts = list_accounts()
        for lb in (self.up_accounts, self.st_accounts, self.acc_accounts):
            lb.delete(0, "end")
            for a in self._accounts:
                lb.insert("end", "  " + a)
        last = self.settings.get("last_accounts") or []
        if isinstance(last, str):
            last = [last]
        chosen = [i for i, a in enumerate(self._accounts) if a in last]
        if not chosen and self._accounts:
            chosen = [0]
        for i in chosen:
            self.up_accounts.selection_set(i)

    def add_account(self):
        if self._guard_busy():
            return
        name = self._ask_text("Новый аккаунт", "Название аккаунта (любое, для вас):")
        if not name:
            return
        self._do_login(safe_name(name))

    def relogin_account(self):
        if self._guard_busy():
            return
        sel = self._selected(self.acc_accounts)
        if len(sel) != 1:
            messagebox.showinfo("Аккаунт", "Выберите ровно один аккаунт для повторного входа.")
            return
        self._do_login(sel[0])

    def remove_account(self):
        if self._guard_busy():
            return
        sel = self._selected(self.acc_accounts)
        if not sel:
            messagebox.showinfo("Аккаунт", "Выберите аккаунт(ы) для удаления.")
            return
        if not messagebox.askyesno("Удаление", "Удалить аккаунт(ы): " + ", ".join(sel) + "?"):
            return
        for label in sel:
            try:
                shutil.rmtree(profile_path(label), ignore_errors=True)
            except Exception as e:
                self.log("Не удалось удалить: " + str(e))
        self._refresh_accounts()
        self.log("Удалено аккаунтов: " + str(len(sel)))

    def _do_login(self, label):
        if not PLAYWRIGHT_AVAILABLE:
            messagebox.showerror("Playwright", "Сначала установите Playwright (см. журнал).")
            return
        profile = profile_path(label)
        self._login_event = threading.Event()
        self.log("Открываю браузер для входа в '" + label + "'...")
        dlg = tk.Toplevel(self)
        dlg.title("Вход в аккаунт")
        dlg.geometry("420x180")
        dlg.configure(bg=CARD)
        dlg.transient(self)
        tk.Label(dlg, text="Войдите в аккаунт '" + label + "'\nв открывшемся окне браузера.\nКогда войдёте — нажмите кнопку.", bg=CARD, fg=TEXT, justify="center", font=(FONT, 10)).pack(pady=18, padx=16)

        def done():
            if self._login_event:
                self._login_event.set()
            dlg.destroy()
            self.after(1200, self._refresh_accounts)
            self.log("Аккаунт '" + label + "' сохранён.")
        ttk.Button(dlg, text="Готово, я вошёл", style="Accent.TButton", command=done).pack(pady=6, padx=20, fill="x")

        def worker():
            try:
                BrowserEngine.login_interactive(profile, self._login_event, self.log)
            except Exception as e:
                self.log("Ошибка входа: " + str(e))
        threading.Thread(target=worker, daemon=True).start()

    def refresh_stats(self):
        if self._guard_busy():
            return
        if not PLAYWRIGHT_AVAILABLE:
            messagebox.showerror("Playwright", "Сначала установите Playwright (см. журнал).")
            return
        targets = self._selected(self.st_accounts)
        if not targets:
            messagebox.showinfo("Статистика", "Выберите один или несколько аккаунтов.")
            return
        self._set_busy(True)
        self.stats_status.set("Открываю YouTube Studio и читаю просмотры...")
        mode = self._browser_mode()

        def worker():
            allrows = []
            for label in targets:
                self.log("[" + label + "] читаю статистику...")
                try:
                    rows = BrowserEngine.fetch_stats(profile_path(label), mode, self.log)
                    for r in rows:
                        allrows.append((label, r))
                    try:
                        Cloud.upsert_account(label)
                        Cloud.push_views(label, rows)
                    except Exception:
                        pass
                    self.log("[" + label + "] видео: " + str(len(rows)))
                except Exception as e:
                    self.log("[" + label + "] ошибка: " + str(e))
            self.log_queue.put(("stats", allrows))
            self.log_queue.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def _fill_stats(self, allrows):
        self.stats_tree.delete(*self.stats_tree.get_children())
        total = 0
        hist = load_uploads()
        for label, r in allrows:
            vtxt = r.get("views", "")
            num = _parse_views(vtxt)
            if num is not None:
                total += num
            date = ""
            for e in hist.get(label, []):
                if e.get("title") and e.get("title") == r.get("title"):
                    date = e.get("date", "")
                    break
            self.stats_tree.insert("", "end", values=(label, r.get("title", ""), vtxt or "\u2014", date or ""))
        if allrows:
            self.stats_total.set("Всего: " + format(total, ",").replace(",", " ") + " просмотров")
            self.stats_status.set("Обновлено. Видео: " + str(len(allrows)))
        else:
            self.stats_status.set("Не удалось получить данные. Проверьте вход и журнал.")

    def _load_local_stats(self):
        self.stats_tree.delete(*self.stats_tree.get_children())
        data = load_uploads()
        targets = self._selected(self.st_accounts) or list(data.keys())
        cnt = 0
        for label in targets:
            for e in data.get(label, []):
                cnt += 1
                self.stats_tree.insert("", "end", values=(label, e.get("title", ""), e.get("views", "\u2014"), e.get("date", "")))
        if cnt == 0:
            self.stats_tree.insert("", "end", values=("\u2014", "Пока нет загрузок через приложение", "\u2014", "\u2014"))
        self.stats_total.set("")

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Выберите видео", filetypes=[("Видео", " ".join("*" + e for e in VIDEO_EXTENSIONS)), ("Все файлы", "*.*")])
        for p in paths:
            self._add_job(p)
        self._refresh_list()

    def add_folder(self):
        d = filedialog.askdirectory(title="Выберите папку")
        if not d:
            return
        for f in sorted(os.listdir(d)):
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS:
                self._add_job(os.path.join(d, f))
        self._refresh_list()

    def _add_job(self, path):
        for j in self.jobs:
            if j["path"] == path:
                return
        title = os.path.splitext(os.path.basename(path))[0]
        self.jobs.append({"path": path, "title": title, "desc": self.template_desc, "tags": self.template_tags})

    def remove_selected(self):
        i = self._sel_index()
        if i is None:
            return
        del self.jobs[i]
        self._refresh_list()

    def clear_queue(self):
        self.jobs = []
        self._refresh_list()

    def _refresh_list(self):
        self.video_list.delete(0, "end")
        for j in self.jobs:
            self.video_list.insert("end", "  " + j["title"])
        self.status_var.set("В очереди: " + str(len(self.jobs)))

    def _sel_index(self):
        sel = self.video_list.curselection()
        return sel[0] if sel else None

    def on_select(self, event=None):
        i = self._sel_index()
        if i is None:
            return
        j = self.jobs[i]
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, j["title"])
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", j.get("desc", ""))
        self.tags_entry.delete(0, "end")
        self.tags_entry.insert(0, j.get("tags", ""))

    def _collect_current(self):
        return (self.title_entry.get().strip(), self.desc_text.get("1.0", "end").strip(), self.tags_entry.get().strip())

    def save_current(self):
        i = self._sel_index()
        if i is None:
            messagebox.showinfo("Сохранение", "Выберите видео в очереди.")
            return
        t, d, g = self._collect_current()
        self.jobs[i]["title"] = t or self.jobs[i]["title"]
        self.jobs[i]["desc"] = d
        self.jobs[i]["tags"] = g
        self._refresh_list()
        self.video_list.selection_set(i)
        self.log("Сохранено: " + self.jobs[i]["title"])

    def apply_desc_to_all(self):
        _, d, _ = self._collect_current()
        for j in self.jobs:
            j["desc"] = d
        self.log("Описание применено ко всем (" + str(len(self.jobs)) + ").")

    def apply_tags_to_all(self):
        _, _, g = self._collect_current()
        for j in self.jobs:
            j["tags"] = g
        self.log("Теги применены ко всем (" + str(len(self.jobs)) + ").")

    def manual_upload_selected(self):
        if self._guard_busy():
            return
        if not PLAYWRIGHT_AVAILABLE:
            messagebox.showerror("Playwright", "Сначала установите Playwright (см. журнал).")
            return
        acc = self._selected(self.up_accounts)
        if not acc:
            messagebox.showinfo("Аккаунт", "Выберите аккаунт для ручной загрузки.")
            return
        label = acc[0]
        i = self._sel_index()
        if i is not None:
            file_path = self.jobs[i]["path"]
        elif self.jobs:
            file_path = self.jobs[0]["path"]
        else:
            file_path = filedialog.askopenfilename(title="Выберите видео для ручной загрузки")
        if not file_path:
            return
        self._set_busy(True)
        self.status_var.set("Открываю браузер для ручной загрузки...")

        def worker():
            try:
                BrowserEngine.manual_upload(profile_path(label), file_path, self.log)
            except Exception as e:
                self.log("Ошибка: " + str(e))
            self.log_queue.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def start_upload(self):
        if self._guard_busy():
            return
        if not PLAYWRIGHT_AVAILABLE:
            messagebox.showerror("Playwright", "Сначала установите Playwright (см. журнал).")
            return
        if not self.jobs:
            messagebox.showinfo("Очередь", "Добавьте хотя бы одно видео.")
            return
        accounts = self._selected(self.up_accounts)
        if not accounts:
            messagebox.showinfo("Аккаунт", "Выберите хотя бы один аккаунт.")
            return
        privacy = PRIVACY_RU_INV.get(self.privacy_var.get(), "public")
        category = self.category_var.get()
        mode = self._browser_mode()
        jobs = [dict(j) for j in self.jobs]
        self._persist_settings()
        self._set_busy(True)
        self.progress["value"] = 0
        self.status_var.set("Загружаю в " + str(len(accounts)) + " аккаунт(ов)...")
        total_units = len(accounts) * len(jobs)
        self._prog_lock = threading.Lock()
        self._acc_prog = 0
        self._threads_remaining = len(accounts)
        self._results = []

        def pcb_factory(label):
            def cb(done, total):
                with self._prog_lock:
                    self._acc_prog += 1
                    pct = int(self._acc_prog * 100 / max(1, total_units))
                self.log_queue.put(("progress", pct))
            return cb

        def worker(label):
            try:
                ok, fail, uploaded = BrowserEngine.upload(profile_path(label), jobs, privacy, category, mode, self.log, pcb_factory(label))
                if uploaded:
                    append_uploads(label, uploaded)
                try:
                    Cloud.upsert_account(label)
                    Cloud.push_uploaded(label, uploaded)
                except Exception:
                    pass
                self._results.append((label, ok, fail))
                self.log("[" + label + "] готово: " + str(ok) + " успешно, " + str(fail) + " с ошибкой.")
            except Exception as e:
                self.log("[" + label + "] ошибка: " + str(e))
            finally:
                with self._prog_lock:
                    self._threads_remaining -= 1
                    rem = self._threads_remaining
                if rem == 0:
                    ok_total = sum(r[1] for r in self._results)
                    fail_total = sum(r[2] for r in self._results)
                    self.log("Готово. Всего загружено: " + str(ok_total) + ", ошибок: " + str(fail_total) + ".")
                    self.log_queue.put(("status", "Готово: " + str(ok_total) + " загружено"))
                    self.log_queue.put(("done", None))
        for label in accounts:
            threading.Thread(target=worker, args=(label,), daemon=True).start()

    def _browser_mode(self):
        return BROWSER_LABEL_TO_MODE.get(self.browser_mode_var.get(), "background")

    def _open_site(self):
        url = self.site_url_var.get().strip()
        if not url:
            messagebox.showinfo("Сайт", "Укажите адрес вашего сайта (например https://ytworker.netlify.app).")
            return
        if not url.startswith("http"):
            url = "https://" + url
        try:
            webbrowser.open(url)
        except Exception as e:
            self.log("Не удалось открыть сайт: " + str(e))

    def _reschedule_autorefresh(self):
        if getattr(self, "_autorefresh_job", None):
            try:
                self.after_cancel(self._autorefresh_job)
            except Exception:
                pass
            self._autorefresh_job = None
        try:
            self._persist_settings()
        except Exception:
            pass
        if self.autorefresh_var.get():
            try:
                mins = max(1, int(self.autorefresh_interval_var.get() or 10))
            except Exception:
                mins = 10
            self._autorefresh_job = self.after(mins * 60 * 1000, self._run_autorefresh)
            self.log("Автообновление включено: каждые " + str(mins) + " мин.")

    def _run_autorefresh(self):
        self._autorefresh_job = None
        if self._busy or getattr(self, "_autorefresh_running", False):
            self._reschedule_autorefresh()
            return
        accounts = list_accounts()
        if not accounts:
            self._reschedule_autorefresh()
            return
        self._autorefresh_running = True
        self.log("⏱ Автообновление статистики (" + str(len(accounts)) + " акк.)...")

        def worker():
            try:
                for label in accounts:
                    try:
                        rows = BrowserEngine.fetch_stats(profile_path(label), "hidden", self.log)
                        Cloud.upsert_account(label)
                        Cloud.push_views(label, rows)
                        self.log("[" + label + "] обновлено: " + str(len(rows)) + " видео.")
                    except Exception as e:
                        self.log("[" + label + "] автообновление: " + str(e))
            finally:
                self._autorefresh_running = False
                self.log_queue.put(("autorefresh_done", time.strftime("%H:%M:%S")))
        threading.Thread(target=worker, daemon=True).start()
        self._reschedule_autorefresh()

    def _persist_settings(self):
        self.settings.update({
            "last_accounts": self._selected(self.up_accounts),
            "privacy": PRIVACY_RU_INV.get(self.privacy_var.get(), "public"),
            "category": self.category_var.get(),
            "browser_mode": self._browser_mode(),
            "autorefresh": bool(self.autorefresh_var.get()),
            "autorefresh_interval": int(self.autorefresh_interval_var.get() or 10),
            "site_url": self.site_url_var.get().strip(),
            "template_desc": self.template_desc,
            "template_tags": self.template_tags,
        })
        try:
            save_settings(self.settings)
        except Exception:
            pass

    def _guard_busy(self):
        if self._busy:
            messagebox.showinfo("Подождите", "Дождитесь завершения текущей операции.")
            return True
        return False

    def _set_busy(self, busy):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for b in (getattr(self, "upload_btn", None), getattr(self, "manual_btn", None), getattr(self, "stats_btn", None)):
            if b is not None:
                try:
                    b.config(state=state)
                except Exception:
                    pass

    def _ask_text(self, title, prompt):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("420x180")
        dlg.configure(bg=CARD)
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text=prompt, bg=CARD, fg=TEXT, font=(FONT, 10)).pack(padx=20, pady=(20, 8), anchor="w")
        var = tk.StringVar()
        ent = tk.Entry(dlg, textvariable=var, bg=FIELD, fg=TEXT, insertbackground=TEXT, borderwidth=0, highlightthickness=1, highlightbackground=EDGE, font=(FONT, 11))
        ent.pack(fill="x", padx=20, ipady=5)
        ent.focus_set()
        res = {"v": None}

        def ok():
            res["v"] = var.get().strip()
            dlg.destroy()
        brow = tk.Frame(dlg, bg=CARD)
        brow.pack(fill="x", padx=20, pady=16)
        ttk.Button(brow, text="OK", style="Accent.TButton", command=ok).pack(side="right")
        ttk.Button(brow, text="Отмена", style="Ghost.TButton", command=dlg.destroy).pack(side="right", padx=8)
        ent.bind("<Return>", lambda e: ok())
        self.wait_window(dlg)
        return res["v"]

    def log(self, msg):
        self.log_queue.put(("log", time.strftime("[%H:%M:%S] ") + str(msg)))

    def _drain_log(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self.log_text.insert("end", payload + "\n")
                    self.log_text.see("end")
                elif kind == "progress":
                    self.progress["value"] = payload
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "stats":
                    self._fill_stats(payload)
                elif kind == "done":
                    self._set_busy(False)
                    self.progress["value"] = 0
                elif kind == "autorefresh_done":
                    self.last_refresh_var.set("Последнее обновление: " + str(payload))
        except queue.Empty:
            pass
        self.after(120, self._drain_log)

    def _on_close(self):
        try:
            self._persist_settings()
        except Exception:
            pass
        self.destroy()


def main():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    if not REQUESTS_AVAILABLE:
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("requests", "Установите библиотеку: pip install requests")
        r.destroy(); return
    global SESSION
    sess = load_session()
    authed = None
    token = sess.get("access_token") if sess else None
    if token:
        try:
            if Cloud.has_active_license(token):
                authed = sess
        except Exception:
            rt = sess.get("refresh_token")
            if rt:
                try:
                    ns = Cloud.refresh(rt)
                    if ns.get("access_token") and Cloud.has_active_license(ns["access_token"]):
                        ns["email"] = sess.get("email")
                        save_session(ns)
                        authed = ns
                except Exception:
                    authed = None
    if authed is None:
        gate = LoginGate()
        gate.mainloop()
        if not gate.authorized:
            return
        authed = gate.session
    SESSION = authed or {}
    app = UploaderGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
