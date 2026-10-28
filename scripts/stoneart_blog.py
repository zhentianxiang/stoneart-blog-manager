#!/usr/bin/env python3
"""Manage Stone Art Sculpture blog posts, media, images, and SEO drafts."""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import hmac
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

# Windows consoles can default to GBK/CP936. Keep CLI JSON output UTF-8 so
# subprocess-based automation can decode it reliably.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_DIR / "config.local.env"
SEO_REFERENCE = SKILL_DIR / "references" / "seo-editor.md"

ARTICLE_FIELDS = [
    "title",
    "slug",
    "excerpt",
    "body_html",
    "cover_image",
    "published_at",
    "seo_title",
    "seo_description",
    "status",
    "sort_order",
    "author_name",
    "author_role",
    "author_bio",
    "author_avatar",
    "show_toc",
    "ai_rewritten_at",
    "ai_rewrite_count",
]

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "best",
    "complete",
    "for",
    "from",
    "guide",
    "how",
    "in",
    "of",
    "on",
    "the",
    "to",
    "what",
    "with",
    "your",
}

DEFAULT_IMAGE_PROMPT = (
    "Only remove visible third-party watermarks, stock-site logos, URLs, usernames, "
    "product codes, and overlaid text. Preserve the sculpture subject, material, "
    "texture, color, lighting, background, composition, and perspective. Keep the "
    "complete sculpture undistorted and inside the requested final canvas. Do not "
    "add objects, people, text, or decoration. Do not redesign or beautify the "
    "sculpture. Repair only the marked area so it blends naturally with the "
    "surrounding texture and light."
)

DEFAULT_IMAGE_EDIT_WIDTH = 1024
DEFAULT_IMAGE_EDIT_HEIGHT = 1024


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, str]:
    values = load_env(path)
    for key in values:
        if key in os.environ:
            values[key] = os.environ[key]
    for key, value in os.environ.items():
        if key.startswith(
            (
                "STONEART_",
                "ALIYUN_",
                "DEEPSEEK_",
                "WAN_",
                "LOCAL_IMAGE_",
                "LOCAL_VISION_",
                "FEISHU_",
                "DEFAULT_AUTHOR_",
                "IMAGE_EDIT_",
            )
        ):
            values[key] = value
    return values


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class StoneArtClient:
    def __init__(self, config: dict[str, str]):
        self.base_url = config["STONEART_BASE_URL"].rstrip("/")
        self.username = config["STONEART_ADMIN_USER"]
        self.password = config["STONEART_ADMIN_PASSWORD"]
        self.session = requests.Session()
        self.token = ""

    def login(self) -> None:
        payload = {"username": self.username, "password": self.password}
        challenge = self._fetch_captcha()
        if challenge.get("enabled"):
            self._apply_captcha(payload, challenge)
        response = self.session.post(
            f"{self.base_url}/api/admin/session", json=payload, timeout=30
        )
        body = safe_json(response)
        if response.status_code == 401 and body.get("error") == "invalid captcha":
            challenge = self._fetch_captcha()
            if challenge.get("enabled"):
                self._apply_captcha(payload, challenge)
            response = self.session.post(
                f"{self.base_url}/api/admin/session", json=payload, timeout=30
            )
            body = safe_json(response)
        if response.status_code >= 400 or not body.get("token"):
            raise ApiError(response.status_code, body.get("error", "login failed"), body)
        self.token = body["token"]

    def _fetch_captcha(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/api/admin/captcha", timeout=30
        )
        body = safe_json(response)
        if response.status_code >= 400:
            raise ApiError(
                response.status_code,
                body.get("error", "captcha fetch failed"),
                body,
            )
        return body

    def _apply_captcha(
        self, payload: dict[str, Any], challenge: dict[str, Any]
    ) -> None:
        match = re.search(r"(\d+)\s*\+\s*(\d+)", challenge.get("question", ""))
        if not match:
            raise ApiError(401, "captcha required but could not be parsed", challenge)
        payload["captcha_answer"] = str(int(match.group(1)) + int(match.group(2)))
        payload["captcha_token"] = challenge.get("token", "")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        files: dict[str, Any] | None = None,
        timeout: int = 90,
    ) -> Any:
        if not self.token:
            self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}{path}"
        for attempt in range(2):
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                files=files,
                headers=headers,
                timeout=timeout,
            )
            body = safe_json(response)
            if response.status_code == 401 and attempt == 0:
                self.login()
                headers["Authorization"] = f"Bearer {self.token}"
                continue
            if response.status_code >= 400:
                raise ApiError(
                    response.status_code,
                    body.get("error", f"request failed ({response.status_code})"),
                    body,
                )
            return body
        raise ApiError(401, "authentication failed")

    @staticmethod
    def article_endpoint(kind: str) -> str:
        if kind == "blog":
            return "/api/admin/blog-posts"
        if kind == "project":
            return "/api/admin/projects"
        raise ValueError("kind must be blog or project")

    def list_articles(
        self,
        kind: str,
        query: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if query:
            params["q"] = query
        if status:
            params["status"] = status
        return self.request("GET", self.article_endpoint(kind), params=params)

    def find_article(
        self,
        kind: str,
        *,
        article_id: int | None = None,
        slug: str = "",
    ) -> dict[str, Any]:
        for page in range(1, 100):
            data = self.list_articles(kind, query=slug, page=page, page_size=100)
            for item in data.get("items", []):
                if article_id and int(item.get("id", 0)) == article_id:
                    return item
                if slug and item.get("slug") == slug:
                    return item
            if page >= int(data.get("total_pages", 0)):
                break
        raise ApiError(404, f"{kind} not found")

    def find_blog(
        self, *, article_id: int | None = None, slug: str = ""
    ) -> dict[str, Any]:
        return self.find_article("blog", article_id=article_id, slug=slug)

    def all_articles(self, kind: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, 100):
            data = self.list_articles(kind, page=page, page_size=100)
            items.extend(data.get("items", []))
            if page >= int(data.get("total_pages", 0)):
                break
        return items

    def save_article(
        self, kind: str, payload: dict[str, Any], article_id: int | None = None
    ) -> Any:
        path = self.article_endpoint(kind)
        method = "POST"
        if article_id:
            path = f"{path}/{article_id}"
            method = "PUT"
        return self.request(method, path, json_body=payload)

    def save_blog(self, payload: dict[str, Any], article_id: int | None = None) -> Any:
        return self.save_article("blog", payload, article_id)

    def list_media(
        self,
        query: str = "",
        usage: str = "",
        ref: str = "",
        task: str = "",
        page: int = 1,
        page_size: int = 40,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        for key, value in {"q": query, "usage": usage, "ref": ref, "task": task}.items():
            if value:
                params[key] = value
        return self.request("GET", "/api/admin/media", params=params)

    def upload_media(self, file_path: Path, filename: str = "") -> Any:
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        content_type = (
            mimetypes.guess_type(filename or file_path.name)[0] or "application/octet-stream"
        )
        with file_path.open("rb") as handle:
            return self.request(
                "POST",
                "/api/admin/media",
                files={"file": (filename or file_path.name, handle, content_type)},
                timeout=180,
            )

    def media_references(self, media_id: int) -> Any:
        return self.request("GET", f"/api/admin/media/{media_id}/references")

    def delete_media(self, media_id: int) -> Any:
        return self.request("DELETE", f"/api/admin/media/{media_id}")


class ImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        self.images.append({"src": values.get("src", ""), "alt": values.get("alt", "")})


def safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def output_json(payload: Any, path: str = "") -> None:
    if path:
        write_json(Path(path).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def feishu_signature(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def blog_admin_url(config: dict[str, str]) -> str:
    return config["STONEART_BASE_URL"].rstrip("/") + "/admin/#blog"


def blog_public_url(config: dict[str, str], slug: str) -> str:
    return config["STONEART_BASE_URL"].rstrip("/") + f"/blog/{slug}/"


def redirect_targets_match(location: str, expected_url: str) -> bool:
    actual = urlsplit(location)
    expected = urlsplit(expected_url)
    return (
        actual.scheme in {"http", "https"}
        and actual.netloc == expected.netloc
        and actual.path.rstrip("/") == expected.path.rstrip("/")
        and actual.query == expected.query
    )


def check_redirect(
    config: dict[str, str], old_url: str, new_url: str
) -> dict[str, Any]:
    site = config["STONEART_BASE_URL"].rstrip("/") + "/"
    old_absolute = urljoin(site, old_url)
    new_absolute = urljoin(site, new_url)
    response = requests.get(old_absolute, allow_redirects=False, timeout=30)
    location = response.headers.get("Location", "")
    resolved_location = urljoin(old_absolute, location) if location else ""
    new_response = requests.get(new_absolute, allow_redirects=True, timeout=30)
    permanent = response.status_code in {301, 308}
    matches = bool(
        resolved_location
        and redirect_targets_match(resolved_location, new_absolute)
    )
    destination_ok = new_response.status_code < 400
    return {
        "ok": permanent and matches and destination_ok,
        "old_url": old_absolute,
        "old_status": response.status_code,
        "location": resolved_location,
        "expected_location": new_absolute,
        "permanent_redirect": permanent,
        "location_matches": matches,
        "new_url": new_absolute,
        "new_status": new_response.status_code,
        "new_final_url": new_response.url,
        "destination_ok": destination_ok,
    }


def notification_time(config: dict[str, str]) -> str:
    timezone_name = config.get("FEISHU_TIMEZONE", "Asia/Shanghai").strip()
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone_name = "Asia/Shanghai"
        zone = ZoneInfo(timezone_name)
    return datetime.now(zone).strftime("%Y-%m-%d %H:%M %Z")


def is_chinese_title(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    chinese = [
        char for char in letters if "\u4e00" <= char <= "\u9fff"
    ]
    if not chinese:
        return False
    return len(chinese) >= max(1, round(len(letters) * 0.3))


def translate_blog_title_zh(config: dict[str, str], title: str) -> str:
    title = title.strip()
    if not title or is_chinese_title(title):
        return title
    try:
        raw = call_deepseek(
            config,
            [
                {
                    "role": "system",
                    "content": (
                        "Translate Stone Art Sculpture blog titles into natural "
                        "Simplified Chinese. Return only the translated title, "
                        "without quotes, labels, explanations, or extra lines."
                    ),
                },
                {"role": "user", "content": title},
            ],
            temperature=0.1,
            max_tokens=200,
        )
    except Exception:
        return ""

    translated = raw.strip().strip("`").strip()
    first_line = next(
        (line.strip() for line in translated.splitlines() if line.strip()), ""
    )
    first_line = re.sub(
        r"^(?:中文标题|简体中文标题|标题)\s*[：:]\s*", "", first_line
    )
    first_line = first_line.strip().strip("\"'“”‘’").strip()
    if not first_line or first_line == title or not is_chinese_title(first_line):
        return ""
    return first_line


def notify_feishu_blog(
    config: dict[str, str],
    *,
    event: str,
    article: dict[str, Any],
    changes: dict[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    if config.get("FEISHU_BLOG_NOTIFY_ENABLED", "true").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return {"enabled": False, "ok": True, "skipped": "disabled"}

    webhook = config.get("FEISHU_BLOG_WEBHOOK_URL", "").strip()
    secret = config.get("FEISHU_BLOG_WEBHOOK_SECRET", "").strip()
    if not webhook or not secret:
        return {
            "enabled": False,
            "ok": True,
            "skipped": "webhook configuration missing",
        }

    action_labels = {
        "created": "新建博客",
        "published": "发布新博客",
        "updated": "修改博客",
        "image_updated": "替换博客图片",
        "test": "飞书通知测试",
    }
    action = action_labels.get(event, event)
    status = str(article.get("status") or "draft")
    status_label = "已发布" if status == "published" else "草稿"
    slug = str(article.get("slug") or "")
    title = str(article.get("title") or f"博客 {article.get('id', '')}").strip()
    public_url = blog_public_url(config, slug) if slug else ""
    admin_url = blog_admin_url(config)

    field_labels = {
        "title": "标题",
        "slug": "Slug",
        "excerpt": "摘要",
        "body_html": "正文",
        "cover_image": "封面图片",
        "published_at": "发布日期",
        "seo_title": "SEO 标题",
        "seo_description": "SEO 描述",
        "status": "发布状态",
        "sort_order": "排序",
        "author_name": "作者",
        "author_role": "职位",
        "author_bio": "作者简介",
        "author_avatar": "作者头像",
        "show_toc": "自动目录",
    }
    changed_labels = [
        field_labels.get(key, key)
        for key in (changes or {})
        if key in field_labels
    ]
    detail_lines = [
        f"**操作：** {action}",
        f"**标题：** {title}",
    ]
    translated_title = translate_blog_title_zh(config, title)
    if translated_title and translated_title != title:
        detail_lines.append(f"**中文标题：** {translated_title}")
    detail_lines.append(f"**状态：** {status_label}")
    if article.get("id"):
        detail_lines.append(f"**文章 ID：** {article['id']}")
    if article.get("author_name"):
        detail_lines.append(f"**作者：** {article['author_name']}")
    if changed_labels:
        detail_lines.append(f"**修改字段：** {', '.join(changed_labels)}")
    if note:
        detail_lines.append(f"**说明：** {note}")
    if status == "published" and public_url:
        detail_lines.append(f"**文章链接：** [查看博客]({public_url})")
    detail_lines.append(f"**后台编辑：** [打开后台]({admin_url})")
    detail_lines.append(f"**时间：** {notification_time(config)}")

    actions = []
    if status == "published" and public_url:
        actions.append(
            {
                "tag": "button",
                "type": "primary",
                "text": {"tag": "plain_text", "content": "查看博客"},
                "url": public_url,
            }
        )
    actions.append(
        {
            "tag": "button",
            "type": "default",
            "text": {"tag": "plain_text", "content": "后台编辑"},
            "url": admin_url,
        }
    )

    template = {
        "published": "green",
        "created": "blue",
        "updated": "orange",
        "image_updated": "orange",
        "test": "wathet",
    }.get(event, "blue")
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": template,
                "title": {"tag": "plain_text", "content": f"Stone Art 博客通知 · {action}"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "\n".join(detail_lines)},
                },
                {
                    "tag": "action",
                    "actions": actions,
                },
            ],
        },
    }
    timestamp = str(int(time.time()))
    payload["timestamp"] = timestamp
    payload["sign"] = feishu_signature(secret, timestamp)
    response = requests.post(webhook, json=payload, timeout=30)
    body = safe_json(response)
    if response.status_code >= 400:
        raise ApiError(response.status_code, "Feishu webhook request failed", body)
    if body.get("StatusCode", body.get("code", 0)) not in {0, "0"}:
        raise ApiError(
            response.status_code,
            body.get("StatusMessage") or body.get("msg") or "Feishu webhook rejected",
            body,
        )
    return {"enabled": True, "ok": True, "response": body}


def safe_notify_feishu_blog(
    config: dict[str, str],
    *,
    event: str,
    article: dict[str, Any],
    changes: dict[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    try:
        return notify_feishu_blog(
            config,
            event=event,
            article=article,
            changes=changes,
            note=note,
        )
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc)}


def writable_article(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in ARTICLE_FIELDS}


def merge_article_defaults(
    payload: dict[str, Any], config: dict[str, str], *, new: bool
) -> dict[str, Any]:
    result = dict(payload)
    result.pop("body_markdown", None)
    if new:
        result.setdefault("status", "draft")
        result.setdefault("sort_order", 0)
        result.setdefault("show_toc", True)
        result.setdefault("author_name", config.get("DEFAULT_AUTHOR_NAME", ""))
        result.setdefault("author_role", config.get("DEFAULT_AUTHOR_ROLE", ""))
        result.setdefault("author_bio", config.get("DEFAULT_AUTHOR_BIO", ""))
        result.setdefault("author_avatar", config.get("DEFAULT_AUTHOR_AVATAR", ""))
    for key in ("title", "slug"):
        if not str(result.get(key, "")).strip():
            raise ValueError(f"{key} is required")
    if result.get("status", "draft") not in {"draft", "published"}:
        raise ValueError("status must be draft or published")
    return result


def backup_article(article: dict[str, Any]) -> Path:
    created = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path.cwd() / "work" / "backups" / f"{created}-blog-{article['id']}.json"
    write_json(path, article)
    return path


def public_url(base_url: str, value: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", value.lstrip("/"))


def extract_article_images(article: dict[str, Any]) -> list[dict[str, str]]:
    parser = ImageParser()
    parser.feed(article.get("body_html") or "")
    images: list[dict[str, str]] = []
    seen: set[str] = set()
    cover = article.get("cover_image") or ""
    if cover:
        images.append({"src": cover, "alt": article.get("title", ""), "position": "cover"})
        seen.add(cover)
    for image in parser.images:
        src = image["src"].strip()
        if not src or src in seen:
            continue
        seen.add(src)
        images.append({**image, "position": "body"})
    return images


def normalized_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def title_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def title_similarity(left: str, right: str) -> tuple[float, float, float]:
    left_norm = normalized_title(left)
    right_norm = normalized_title(right)
    sequence = difflib.SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    overlap = (
        len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
        if left_tokens and right_tokens
        else 0.0
    )
    return sequence, jaccard, overlap


def article_inventory(client: StoneArtClient) -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    image_usage: dict[str, list[dict[str, Any]]] = {}
    for kind, endpoint_kind in (("blog", "blog"), ("project", "project")):
        for item in client.all_articles(endpoint_kind):
            record = {
                "kind": kind,
                "id": item.get("id"),
                "title": item.get("title", ""),
                "slug": item.get("slug", ""),
                "status": item.get("status", ""),
                "published_at": item.get("published_at"),
                "images": extract_article_images(item),
            }
            articles.append(record)
            for image in record["images"]:
                image_usage.setdefault(image["src"], []).append(
                    {
                        "kind": kind,
                        "id": item.get("id"),
                        "title": item.get("title", ""),
                        "slug": item.get("slug", ""),
                        "position": image.get("position", ""),
                    }
                )
    repeated_images = {
        url: refs for url, refs in image_usage.items() if len(refs) > 1
    }
    return {
        "article_count": len(articles),
        "articles": articles,
        "image_usage": image_usage,
        "repeated_images": repeated_images,
    }


def topic_check(
    client: StoneArtClient,
    config: dict[str, str],
    title: str,
    slug: str,
    semantic: bool,
) -> dict[str, Any]:
    existing = (
        client.all_articles("blog")
        + client.all_articles("project")
    )
    matches: list[dict[str, Any]] = []
    normalized_slug = normalized_title(slug.replace("-", " ")) if slug else ""
    for item in existing:
        sequence, jaccard, overlap = title_similarity(title, item.get("title", ""))
        slug_similarity = 0.0
        if normalized_slug:
            slug_similarity = difflib.SequenceMatcher(
                None,
                normalized_slug,
                normalized_title(str(item.get("slug", "")).replace("-", " ")),
            ).ratio()
        score = max(sequence, jaccard, overlap, slug_similarity)
        if score >= 0.32:
            matches.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "slug": item.get("slug"),
                    "status": item.get("status"),
                    "score": round(score, 3),
                    "sequence": round(sequence, 3),
                    "token_overlap": round(overlap, 3),
                    "jaccard": round(jaccard, 3),
                    "slug_similarity": round(slug_similarity, 3),
                }
            )
    matches.sort(key=lambda item: item["score"], reverse=True)
    top = matches[:30]
    deterministic_risk = "low"
    if top and top[0]["score"] >= 0.72:
        deterministic_risk = "high"
    elif top and top[0]["score"] >= 0.52:
        deterministic_risk = "medium"

    semantic_result = None
    if semantic:
        prompt = {
            "candidate_title": title,
            "candidate_slug": slug,
            "existing_articles": [
                {
                    "title": item.get("title"),
                    "slug": item.get("slug"),
                    "status": item.get("status"),
                }
                for item in top
            ],
            "task": (
                "Assess SEO cannibalization and topic duplication. Return JSON with "
                "duplicate_risk from 0 to 1, verdict (new/low/medium/high/duplicate), "
                "closest_topics, overlap_reason, recommended_unique_angle, and "
                "suggested_title. Do not approve a near-duplicate merely because wording differs."
            ),
        }
        raw = call_deepseek(
            config,
            [
                {
                    "role": "system",
                    "content": (
                        "You are an SEO content strategist. Prevent keyword cannibalization "
                        "and duplicate articles. Return valid JSON only."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        semantic_result = parse_json_model_output(raw)

    return {
        "title": title,
        "slug": slug,
        "deterministic_risk": deterministic_risk,
        "matches": top,
        "semantic": semantic_result,
        "pass": deterministic_risk == "low"
        and (
            semantic_result is None
            or float(semantic_result.get("duplicate_risk", 1)) < 0.35
        ),
    }


def download_image(base_url: str, url: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    absolute = public_url(base_url, url)
    parsed = urlparse(absolute)
    suffix = Path(parsed.path).suffix or ".jpg"
    digest = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:12]
    name = f"{digest}-{Path(parsed.path).stem[:60]}{suffix}"
    target = directory / name
    response = requests.get(absolute, timeout=90)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def call_deepseek(
    config: dict[str, str],
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, str] | None = None,
    temperature: float = 0.35,
    max_tokens: int = 12000,
    timeout: int = 240,
) -> str:
    base = config["DEEPSEEK_BASE_URL"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {config['DEEPSEEK_API_KEY']}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": config.get("DEEPSEEK_MODEL", "deepseek-flash"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    response = requests.post(
        f"{base}/chat/completions", headers=headers, json=body, timeout=timeout
    )
    payload = safe_json(response)
    if response.status_code >= 400:
        raise ApiError(response.status_code, payload.get("error", "DeepSeek request failed"), payload)
    choices = payload.get("choices") or []
    if not choices:
        raise ApiError(500, "DeepSeek returned no choices", payload)
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        return "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    return str(content)


def local_vision_enabled(config: dict[str, str]) -> bool:
    return str(config.get("LOCAL_VISION_ENABLED", "true")).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def call_local_vision(
    config: dict[str, str],
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, str] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4000,
    timeout: int = 180,
) -> str:
    if not local_vision_enabled(config):
        raise RuntimeError("local Qwen vision is disabled")
    base = (
        config.get("LOCAL_VISION_BASE_URL", "").strip()
        or "http://120.10.255.14:7893/v1"
    ).rstrip("/")
    api_key = config.get("LOCAL_VISION_API_KEY", "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": (
            config.get("LOCAL_VISION_MODEL", "").strip()
            or "Qwen3-VL-30B-A3B-Instruct"
        ),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": int(config.get("LOCAL_VISION_MAX_TOKENS", max_tokens)),
    }
    if response_format:
        body["response_format"] = response_format
    try:
        response = requests.post(
            f"{base}/chat/completions",
            headers=headers,
            json=body,
            timeout=float(config.get("LOCAL_VISION_TIMEOUT", timeout)),
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"local Qwen vision request failed: {exc}") from exc
    payload = safe_json(response)
    if response.status_code >= 400:
        raise ApiError(
            response.status_code,
            payload.get("error", "Local Qwen vision request failed"),
            payload,
        )
    choices = payload.get("choices") or []
    if not choices:
        raise ApiError(500, "Local Qwen vision returned no choices", payload)
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    if not str(content).strip():
        raise ApiError(500, "Local Qwen vision returned empty content", payload)
    return str(content)


def call_vision_with_fallback(
    config: dict[str, str],
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, str] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4000,
    timeout: int = 240,
) -> tuple[str, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    if local_vision_enabled(config):
        model = (
            config.get("LOCAL_VISION_MODEL", "").strip()
            or "Qwen3-VL-30B-A3B-Instruct"
        )
        try:
            content = call_local_vision(
                config,
                messages,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            attempts.append(
                {"provider": "local-qwen-vl", "model": model, "status": "succeeded"}
            )
            return content, {
                "provider": "local-qwen-vl",
                "model": model,
                "attempts": attempts,
            }
        except Exception as exc:
            attempts.append(
                {
                    "provider": "local-qwen-vl",
                    "model": model,
                    "status": "failed",
                    "error": str(exc),
                }
            )
    deepseek_model = config.get("DEEPSEEK_MODEL", "deepseek-flash")
    try:
        content = call_deepseek(
            config,
            messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except Exception as exc:
        attempts.append(
            {
                "provider": "deepseek",
                "model": deepseek_model,
                "status": "failed",
                "error": str(exc),
            }
        )
        details = "; ".join(
            f"{item['provider']}: {item.get('error', 'failed')}" for item in attempts
        )
        raise RuntimeError(f"all vision providers failed: {details}") from exc
    attempts.append(
        {"provider": "deepseek", "model": deepseek_model, "status": "succeeded"}
    )
    return content, {
        "provider": "deepseek",
        "model": deepseek_model,
        "attempts": attempts,
    }


def parse_json_model_output(value: str) -> Any:
    if value is None:
        raise RuntimeError("model returned empty content")
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            value = value.decode("gb18030", errors="replace")
    cleaned = str(value).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def vision_batch(
    config: dict[str, str],
    paths: list[Path],
    batch_size: int,
    prompt: str,
) -> dict[str, Any]:
    # The local Qwen3-VL deployment accepts one image per request. Keep the
    # vision-batch interface while processing images one at a time.
    batch_size = 1 if local_vision_enabled(config) else max(1, min(batch_size, 6))
    results: list[dict[str, Any]] = []
    vision_runs: list[dict[str, Any]] = []
    for start in range(0, len(paths), batch_size):
        chunk = paths[start : start + batch_size]
        content: list[dict[str, Any]] = []
        for offset, path in enumerate(chunk, start=start + 1):
            content.append(
                {
                    "type": "text",
                    "text": f"Image {offset}: {path.name}",
                }
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url(path)},
                }
            )
        content.append(
            {
                "type": "text",
                "text": prompt
                + " Return JSON with an images array. Each item must include index, "
                "filename, subject, material, scene, has_watermark, watermark_type, "
                "watermark_notes, sensitive_content, suggested_alt_text, and replacement_risks.",
            }
        )
        raw, vision_info = call_vision_with_fallback(
            config,
            [
                {
                    "role": "system",
                    "content": (
                        "You are a precise visual inspector for a sculpture website. "
                        "Analyze each supplied image independently. Return valid JSON only."
                    ),
                },
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
        )
        vision_runs.append(vision_info)
        parsed = parse_json_model_output(raw)
        batch_results = parsed.get("images") if isinstance(parsed, dict) else None
        if isinstance(batch_results, list):
            for index, item in enumerate(batch_results):
                if isinstance(item, dict):
                    item["index"] = start + index + 1
                    if index < len(chunk):
                        item.setdefault("local_path", str(chunk[index].resolve()))
                    results.append(item)
        else:
            results.append({"raw": parsed})
    return {
        "image_count": len(paths),
        "images": results,
        "vision_provider": vision_runs[-1]["provider"] if vision_runs else None,
        "vision_model": vision_runs[-1]["model"] if vision_runs else None,
        "vision_attempts": [
            attempt for run in vision_runs for attempt in run.get("attempts", [])
        ],
    }


def get_wan_result_urls(response: Any) -> list[str]:
    output = getattr(response, "output", None)
    if not output:
        return []
    urls: list[str] = []
    for item in getattr(output, "results", None) or []:
        url = getattr(item, "url", None)
        if url:
            urls.append(url)
    for choice in getattr(output, "choices", None) or []:
        content = getattr(getattr(choice, "message", None), "content", None)
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("image"):
                urls.append(item["image"])
    return urls


def collect_image_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            urls.append(value)
    elif isinstance(value, list):
        for item in value:
            urls.extend(collect_image_urls(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"url", "image", "image_url"} and isinstance(item, str):
                urls.extend(collect_image_urls(item))
            elif isinstance(item, (dict, list)):
                urls.extend(collect_image_urls(item))
    return urls


LOCAL_SIZE_RE = re.compile(r"^\d{3,4}x\d{3,4}$")


def image_edit_output_size(config: dict[str, str]) -> tuple[int, int]:
    values: list[int] = []
    for key, default in (
        ("IMAGE_EDIT_OUTPUT_WIDTH", DEFAULT_IMAGE_EDIT_WIDTH),
        ("IMAGE_EDIT_OUTPUT_HEIGHT", DEFAULT_IMAGE_EDIT_HEIGHT),
    ):
        raw = str(config.get(key, default)).strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer, got {raw!r}") from exc
        if value < 64 or value > 8192:
            raise ValueError(f"{key} must be between 64 and 8192, got {value}")
        values.append(value)
    return values[0], values[1]


def image_edit_fit(config: dict[str, str]) -> str:
    fit = str(config.get("IMAGE_EDIT_FIT", "cover")).strip().lower()
    if fit not in {"cover", "contain"}:
        raise ValueError("IMAGE_EDIT_FIT must be 'cover' or 'contain'")
    return fit


def image_edit_prompt(prompt: str, config: dict[str, str]) -> str:
    width, height = image_edit_output_size(config)
    fit = image_edit_fit(config)
    framing = (
        f"Final file requirement: the finished image will be normalized to exactly "
        f"{width} x {height} pixels ({'square' if width == height else 'fixed'}). "
        "Compose a single edited image for that final canvas. "
        "Keep the sculpture complete, undistorted, and inside the frame with safe "
        "margins. Do not stretch the subject or change its proportions. "
        if fit == "cover"
        else f"Final file requirement: the finished image will be normalized to "
        f"{width} x {height} pixels. Compose the complete sculpture for that canvas. "
        "Preserve its proportions, add no invented details, and leave neutral space "
        "only where needed. "
    )
    return f"{prompt.strip()}\n\n{framing}".strip()


def normalize_edited_image(path: Path, config: dict[str, str]) -> dict[str, Any]:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required; install requirements.txt") from exc

    target_size = image_edit_output_size(config)
    fit = image_edit_fit(config)
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        original_size = image.size
        if original_size == target_size:
            return {
                "original_size": list(original_size),
                "output_size": list(original_size),
                "target_size": list(target_size),
                "adjusted": False,
                "fit": fit,
            }
        if fit == "cover":
            normalized = ImageOps.fit(
                image,
                target_size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        else:
            normalized = ImageOps.pad(
                image,
                target_size,
                method=Image.Resampling.LANCZOS,
                color=(245, 245, 245),
                centering=(0.5, 0.5),
            )
    save_format = "PNG" if path.suffix.lower() == ".png" else "JPEG"
    save_options: dict[str, Any] = {"optimize": True}
    if save_format == "JPEG":
        save_options.update(quality=95, progressive=True)
    normalized.save(path, format=save_format, **save_options)
    return {
        "original_size": list(original_size),
        "output_size": list(target_size),
        "target_size": list(target_size),
        "adjusted": True,
        "fit": fit,
    }


def local_image_enabled(config: dict[str, str]) -> bool:
    return str(config.get("LOCAL_IMAGE_ENABLED", "true")).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def local_image_base_url(config: dict[str, str]) -> str:
    base = config.get("LOCAL_IMAGE_BASE_URL", "").strip()
    return (base or "http://120.10.255.14:7890/v1").rstrip("/")


def local_image_headers(config: dict[str, str]) -> dict[str, str]:
    api_key = config.get("LOCAL_IMAGE_API_KEY", "").strip()
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def local_edit_size(input_path: Path, requested_size: str) -> str:
    requested_size = requested_size.strip()
    if LOCAL_SIZE_RE.fullmatch(requested_size):
        return requested_size
    try:
        from PIL import Image

        with Image.open(input_path) as image:
            width, height = image.size
    except Exception:
        return "auto"
    if min(width, height) < 256:
        return "auto"
    scale = min(1.0, 2048 / max(width, height))
    width = max(256, int(width * scale + 8) // 16 * 16)
    height = max(256, int(height * scale + 8) // 16 * 16)
    return f"{width}x{height}"


def check_local_image_health(config: dict[str, str]) -> None:
    base = local_image_base_url(config)
    health_url = config.get("LOCAL_IMAGE_HEALTH_URL", "").strip()
    if not health_url:
        root = base[:-3] if base.endswith("/v1") else base
        health_url = f"{root}/health"
    timeout = float(config.get("LOCAL_IMAGE_HEALTH_TIMEOUT", "5"))
    try:
        response = requests.get(
            health_url, headers=local_image_headers(config), timeout=timeout
        )
        if response.status_code == 404:
            # Some OpenAI-compatible servers expose only /v1/models.
            response = requests.get(
                f"{base}/models",
                headers=local_image_headers(config),
                timeout=timeout,
            )
    except requests.RequestException as exc:
        raise RuntimeError(f"local image health check failed: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(
            f"local image health check returned HTTP {response.status_code}"
        )
    body = safe_json(response)
    online = body.get("workers_online")
    if online is not None:
        try:
            online_count = int(online)
        except (TypeError, ValueError):
            online_count = 0
        if online_count < 1:
            raise RuntimeError("local image server has no online workers")
    status = str(body.get("status", "ok")).strip().lower()
    if status not in {"ok", "healthy", "ready"}:
        raise RuntimeError(f"local image server is not ready: {status}")


def call_local_image_edit(
    config: dict[str, str], input_path: Path, prompt: str, size: str
) -> str:
    if not local_image_enabled(config):
        raise RuntimeError("local image editing is disabled")
    base = local_image_base_url(config)
    check_local_image_health(config)
    model = config.get("LOCAL_IMAGE_MODEL", "").strip() or "qwen-image-2.1"
    local_size = local_edit_size(input_path, size)
    data = {
        "model": model,
        "prompt": prompt,
        "n": "1",
        "size": local_size,
        "quality": config.get("LOCAL_IMAGE_QUALITY", "auto"),
        "response_format": "url",
        "output_format": "jpeg",
    }
    steps = config.get("LOCAL_IMAGE_STEPS", "").strip()
    if steps:
        data["steps"] = steps
    mime = mimetypes.guess_type(input_path.name)[0] or "image/jpeg"
    timeout = float(config.get("LOCAL_IMAGE_TIMEOUT", "960"))
    try:
        with input_path.open("rb") as handle:
            response = requests.post(
                f"{base}/images/edits",
                headers=local_image_headers(config),
                data=data,
                files={"image": (input_path.name, handle, mime)},
                timeout=timeout,
            )
    except requests.RequestException as exc:
        raise RuntimeError(f"local image edit request failed: {exc}") from exc
    body = safe_json(response)
    if response.status_code >= 400:
        message = body.get("error") or body.get("detail") or "Local Qwen image edit failed"
        if isinstance(message, dict):
            message = message.get("message") or json.dumps(message, ensure_ascii=False)
        raise ApiError(response.status_code, str(message), body)
    urls = collect_image_urls(body)
    if not urls:
        raise ApiError(500, "Local Qwen response contained no image URL", body)
    return urls[0]


def call_wan_compatible(
    config: dict[str, str], input_path: Path, prompt: str, size: str
) -> str:
    base = config.get("ALIYUN_WAN_COMPATIBLE_BASE_URL", "").rstrip("/")
    api_key = config.get("ALIYUN_DASHSCOPE_API_KEY", "")
    if not base or not api_key:
        raise RuntimeError("Aliyun Wan compatible endpoint or API key is missing")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.get("WAN_IMAGE_MODEL", "wan2.7-image"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_data_url(input_path)},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "n": 1,
        "size": size,
    }
    response = requests.post(
        f"{base}/chat/completions", headers=headers, json=payload, timeout=300
    )
    body = safe_json(response)
    if response.status_code >= 400:
        raise ApiError(
            response.status_code,
            body.get("error", "Wan2.7 compatible request failed"),
            body,
        )
    urls = collect_image_urls(body)
    if not urls:
        raise ApiError(500, "Wan2.7 compatible response contained no image URL", body)
    return urls[0]


def call_wan_edit(
    config: dict[str, str], input_path: Path, prompt: str, size: str
) -> tuple[str, str]:
    try:
        return call_wan_compatible(config, input_path, prompt, size), "wan-compatible"
    except Exception as compatible_error:
        try:
            import dashscope
            from dashscope.aigc.image_generation import ImageGeneration
            from dashscope.api_entities.dashscope_response import Message
        except ImportError:
            raise compatible_error
        base_url = config.get("ALIYUN_WAN_DASHSCOPE_BASE_URL", "").rstrip("/")
        if not base_url:
            raise compatible_error
        dashscope.base_http_api_url = base_url
        response = ImageGeneration.call(
            model=config.get("WAN_IMAGE_MODEL", "wan2.7-image"),
            api_key=config.get("ALIYUN_DASHSCOPE_API_KEY", ""),
            messages=[
                Message(
                    role="user",
                    content=[{"image": image_data_url(input_path)}, {"text": prompt}],
                )
            ],
            n=1,
            size=size,
        )
        if getattr(response, "status_code", 500) != 200:
            raise RuntimeError(
                f"Wan2.7 failed: status={getattr(response, 'status_code', '')} "
                f"code={getattr(response, 'code', '')} message={getattr(response, 'message', '')}"
            )
        urls = get_wan_result_urls(response)
        if not urls:
            raise RuntimeError("Wan2.7 returned no image URL")
        return urls[0], "wan-dashscope"


def edit_image_with_fallback(
    config: dict[str, str], input_path: Path, prompt: str, size: str
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    if local_image_enabled(config):
        local_model = config.get("LOCAL_IMAGE_MODEL", "").strip() or "qwen-image-2.1"
        try:
            remote_url = call_local_image_edit(config, input_path, prompt, size)
            attempts.append(
                {
                    "provider": "local-qwen",
                    "model": local_model,
                    "status": "succeeded",
                }
            )
            return {
                "remote_url": remote_url,
                "provider": "local-qwen",
                "model": local_model,
                "engine": "local-qwen",
                "attempts": attempts,
            }
        except Exception as exc:
            attempts.append(
                {
                    "provider": "local-qwen",
                    "model": local_model,
                    "status": "failed",
                    "error": str(exc),
                }
            )
    wan_model = config.get("WAN_IMAGE_MODEL", "wan2.7-image")
    try:
        remote_url, engine = call_wan_edit(config, input_path, prompt, size)
    except Exception as exc:
        attempts.append(
            {
                "provider": "wan2.7",
                "model": wan_model,
                "status": "failed",
                "error": str(exc),
            }
        )
        details = "; ".join(
            f"{item['provider']}: {item.get('error', 'failed')}" for item in attempts
        )
        raise RuntimeError(f"all image edit providers failed: {details}") from exc
    attempts.append(
        {
            "provider": "wan2.7",
            "model": wan_model,
            "status": "succeeded",
            "engine": engine,
        }
    )
    return {
        "remote_url": remote_url,
        "provider": "wan2.7",
        "model": wan_model,
        "engine": engine,
        "attempts": attempts,
    }


def clean_image(
    config: dict[str, str],
    input_path: Path,
    output_path: Path,
    prompt: str,
    size: str,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("clean-image requires Pillow; install requirements.txt") from exc

    with Image.open(input_path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
        original_size = original.size
    prompt = image_edit_prompt(prompt, config)
    edit = edit_image_with_fallback(config, input_path, prompt, size)
    remote_url = edit["remote_url"]
    remote = requests.get(remote_url, timeout=180)
    remote.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(remote.content)
    image_transform = normalize_edited_image(output_path, config)
    return {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "remote_url": remote_url,
        "size": image_transform["output_size"],
        "input_size": list(original_size),
        "image_transform": image_transform,
        "prompt": prompt,
        "model": edit["model"],
        "engine": edit["engine"],
        "provider": edit["provider"],
        "attempts": edit["attempts"],
    }


def build_client(config: dict[str, str]) -> StoneArtClient:
    missing = [
        key
        for key in ("STONEART_BASE_URL", "STONEART_ADMIN_USER", "STONEART_ADMIN_PASSWORD")
        if not config.get(key)
    ]
    if missing:
        raise RuntimeError(f"missing config: {', '.join(missing)}")
    client = StoneArtClient(config)
    client.login()
    return client


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = root.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Validate login, blog access, and media access")

    redirect = sub.add_parser(
        "check-redirect",
        help="Verify a permanent old-to-new content URL redirect",
    )
    redirect.add_argument("--old-url", required=True)
    redirect.add_argument("--new-url", required=True)
    redirect.add_argument("--output", default="")

    list_blogs = sub.add_parser("list-blogs")
    list_blogs.add_argument("--query", default="")
    list_blogs.add_argument("--status", choices=["", "draft", "published"], default="")
    list_blogs.add_argument("--page", type=int, default=1)
    list_blogs.add_argument("--page-size", type=int, default=100)
    list_blogs.add_argument("--limit", type=int, default=0)
    list_blogs.add_argument("--full", action="store_true")

    find = sub.add_parser("find-blog")
    find.add_argument("--id", type=int)
    find.add_argument("--slug", default="")

    get_blog = sub.add_parser("get-blog")
    get_blog.add_argument("--id", type=int)
    get_blog.add_argument("--slug", default="")
    get_blog.add_argument("--output", default="")

    list_projects = sub.add_parser("list-projects")
    list_projects.add_argument("--query", default="")
    list_projects.add_argument("--status", choices=["", "draft", "published"], default="")
    list_projects.add_argument("--page", type=int, default=1)
    list_projects.add_argument("--page-size", type=int, default=100)
    list_projects.add_argument("--limit", type=int, default=0)
    list_projects.add_argument("--full", action="store_true")

    find_project = sub.add_parser("find-project")
    find_project.add_argument("--id", type=int)
    find_project.add_argument("--slug", default="")

    get_project = sub.add_parser("get-project")
    get_project.add_argument("--id", type=int)
    get_project.add_argument("--slug", default="")
    get_project.add_argument("--output", default="")

    inventory = sub.add_parser("content-inventory")
    inventory.add_argument("--output", required=True)

    topic = sub.add_parser("topic-check")
    topic.add_argument("--title", required=True)
    topic.add_argument("--slug", default="")
    topic.add_argument("--semantic", action="store_true")
    topic.add_argument("--output", default="")

    image_usage = sub.add_parser("image-usage")
    image_usage.add_argument("--url", required=True)
    image_usage.add_argument("--output", default="")

    article_images = sub.add_parser("article-images")
    article_images.add_argument("--kind", choices=["blog", "project"], default="blog")
    article_images.add_argument("--id", type=int)
    article_images.add_argument("--slug", default="")
    article_images.add_argument("--download-dir", default="")
    article_images.add_argument("--output", default="")

    create = sub.add_parser("create-blog")
    create.add_argument("--file", required=True)
    create.add_argument("--dry-run", action="store_true")
    create.add_argument("--no-notify", action="store_true")

    update = sub.add_parser("update-blog")
    update.add_argument("--id", type=int, required=True)
    update.add_argument("--file", required=True)
    update.add_argument("--force", action="store_true")
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--no-notify", action="store_true")

    list_media = sub.add_parser("list-media")
    list_media.add_argument("--query", default="")
    list_media.add_argument("--usage", choices=["", "used", "unused"], default="")
    list_media.add_argument("--ref", default="")
    list_media.add_argument("--task", default="")
    list_media.add_argument("--page", type=int, default=1)
    list_media.add_argument("--page-size", type=int, default=40)

    upload = sub.add_parser("upload-media")
    upload.add_argument("--file", required=True)
    upload.add_argument("--name", default="")

    refs = sub.add_parser("media-references")
    refs.add_argument("--id", type=int, required=True)

    delete = sub.add_parser("delete-media")
    delete.add_argument("--id", type=int, required=True)
    delete.add_argument("--confirm", action="store_true")

    replace = sub.add_parser("replace-article-image")
    replace.add_argument("--kind", choices=["blog", "project"], default="blog")
    replace.add_argument("--id", type=int, required=True)
    replace.add_argument("--old-url", required=True)
    replace.add_argument("--new-url", required=True)
    replace.add_argument("--skip-cover", action="store_true")
    replace.add_argument("--apply", action="store_true")
    replace.add_argument("--no-notify", action="store_true")

    download = sub.add_parser("download-url")
    download.add_argument("--url", required=True)
    download.add_argument("--output", required=True)

    vision = sub.add_parser("vision")
    vision.add_argument("--image", required=True)
    vision.add_argument("--prompt", default="")
    vision.add_argument("--output", default="")

    vision_batch_parser = sub.add_parser("vision-batch")
    vision_batch_parser.add_argument("--image", action="append", required=True)
    vision_batch_parser.add_argument("--batch-size", type=int, default=3)
    vision_batch_parser.add_argument("--prompt", default="")
    vision_batch_parser.add_argument("--output", default="")

    clean = sub.add_parser("clean-image")
    clean.add_argument("--input", required=True)
    clean.add_argument("--output", required=True)
    clean.add_argument("--prompt", default=DEFAULT_IMAGE_PROMPT)
    clean.add_argument("--size", default="2K")

    seo = sub.add_parser("seo-rewrite")
    seo.add_argument("--id", type=int)
    seo.add_argument("--input", default="")
    seo.add_argument("--brief", default="")
    seo.add_argument("--output", required=True)

    test_feishu = sub.add_parser(
        "test-feishu", help="Send a signed Feishu webhook test card"
    )
    test_feishu.add_argument("--title", default="Stone Art 博客通知测试")
    test_feishu.add_argument("--slug", default="")
    test_feishu.add_argument(
        "--status", choices=["draft", "published"], default="draft"
    )

    return root


def main() -> int:
    args = parser().parse_args()
    config = load_config(Path(args.config).expanduser())
    try:
        if args.command == "check":
            client = build_client(config)
            blogs = client.list_articles("blog", page_size=1)
            media = client.list_media(page_size=1)
            output_json(
                {
                    "ok": True,
                    "site": config["STONEART_BASE_URL"],
                    "admin_user": config["STONEART_ADMIN_USER"],
                    "blogs": blogs.get("total"),
                    "media": media.get("total"),
                    "deepseek_model": config.get("DEEPSEEK_MODEL"),
                    "local_vision_enabled": local_vision_enabled(config),
                    "local_vision_model": config.get(
                        "LOCAL_VISION_MODEL", "Qwen3-VL-30B-A3B-Instruct"
                    ),
                    "wan_model": config.get("WAN_IMAGE_MODEL"),
                }
            )
            return 0

        if args.command == "check-redirect":
            result = check_redirect(config, args.old_url, args.new_url)
            output_json(result, args.output)
            return 0 if result["ok"] else 2

        if args.command == "vision":
            image = Path(args.image).expanduser()
            prompt = args.prompt or (
                "Inspect this blog image. Return JSON with: subject, material, scene, "
                "has_watermark, watermark_type (none/foreign/stoneart/uncertain), "
                "watermark_notes, sensitive_content, suggested_alt_text, and replacement_risks. "
                "Do not guess beyond the image."
            )
            raw, vision_info = call_vision_with_fallback(
                config,
                [
                    {
                        "role": "system",
                        "content": "You are a precise visual inspector for a sculpture website. Return valid JSON only.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_data_url(image)}},
                            {"type": "text", "text": prompt},
                        ],
                    },
                ],
                response_format={"type": "json_object"},
            )
            result = parse_json_model_output(raw)
            if isinstance(result, dict):
                result.setdefault("vision_provider", vision_info["provider"])
                result.setdefault("vision_model", vision_info["model"])
                result.setdefault("vision_attempts", vision_info["attempts"])
            output_json(result, args.output)
            return 0

        if args.command == "vision-batch":
            prompt = args.prompt or (
                "Inspect these blog images for editorial use. Identify the sculpture, "
                "material, scene, watermark, and sensitive-content risks."
            )
            result = vision_batch(
                config,
                [Path(value).expanduser() for value in args.image],
                args.batch_size,
                prompt,
            )
            output_json(result, args.output)
            return 0

        if args.command == "clean-image":
            result = clean_image(
                config,
                Path(args.input).expanduser(),
                Path(args.output).expanduser(),
                args.prompt,
                args.size,
            )
            output_json(result)
            return 0

        if args.command == "download-url":
            target = Path(args.output).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            response = requests.get(
                public_url(config["STONEART_BASE_URL"], args.url), timeout=120
            )
            response.raise_for_status()
            target.write_bytes(response.content)
            output_json(
                {"url": args.url, "output": str(target.resolve()), "bytes": target.stat().st_size}
            )
            return 0

        if args.command == "seo-rewrite":
            if args.id:
                client = build_client(config)
                article = client.find_blog(article_id=args.id)
            elif args.input:
                article = read_json(Path(args.input).expanduser())
            else:
                raise ValueError("seo-rewrite requires --id or --input")
            system = SEO_REFERENCE.read_text(encoding="utf-8")
            prompt = {
                "task": "Rewrite or create the article for Google SEO and buyer usefulness.",
                "brief": args.brief,
                "article_context": article,
                "requirements": (
                    "Return one JSON object only. Do not include markdown fences. "
                    "Preserve verified facts. Put uncertain claims in claims_to_verify. "
                    "Do not include an H1 in body_html because the site template renders it."
                ),
            }
            raw = call_deepseek(
                config,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
            )
            result = parse_json_model_output(raw)
            write_json(Path(args.output).expanduser(), result)
            output_json(result)
            return 0

        if args.command == "test-feishu":
            result = notify_feishu_blog(
                config,
                event="test",
                article={
                    "id": 0,
                    "title": args.title,
                    "slug": args.slug,
                    "status": args.status,
                    "author_name": config.get("DEFAULT_AUTHOR_NAME", ""),
                },
                note="飞书 Webhook、签名和卡片发送验证成功。",
            )
            output_json(result)
            return 0

        client = build_client(config)

        if args.command == "list-blogs":
            data = client.list_articles(
                "blog", args.query, args.status, args.page, args.page_size
            )
            items = data.get("items", [])
            if args.limit:
                items = items[: args.limit]
            if not args.full:
                items = [
                    {
                        key: item.get(key)
                        for key in (
                            "id",
                            "title",
                            "slug",
                            "status",
                            "published_at",
                            "updated_at",
                            "author_name",
                            "cover_image",
                        )
                    }
                    for item in items
                ]
            output_json({**data, "items": items})
            return 0

        if args.command == "find-blog":
            if not args.id and not args.slug:
                raise ValueError("find-blog requires --id or --slug")
            output_json(client.find_blog(article_id=args.id, slug=args.slug))
            return 0

        if args.command == "get-blog":
            if not args.id and not args.slug:
                raise ValueError("get-blog requires --id or --slug")
            output_json(
                client.find_blog(article_id=args.id, slug=args.slug), args.output
            )
            return 0

        if args.command == "list-projects":
            data = client.list_articles(
                "project", args.query, args.status, args.page, args.page_size
            )
            items = data.get("items", [])
            if args.limit:
                items = items[: args.limit]
            if not args.full:
                items = [
                    {
                        key: item.get(key)
                        for key in (
                            "id",
                            "title",
                            "slug",
                            "status",
                            "published_at",
                            "updated_at",
                            "cover_image",
                        )
                    }
                    for item in items
                ]
            output_json({**data, "items": items})
            return 0

        if args.command in {"find-project", "get-project"}:
            if not args.id and not args.slug:
                raise ValueError(f"{args.command} requires --id or --slug")
            article = client.find_article(
                "project", article_id=args.id, slug=args.slug
            )
            output_json(article, getattr(args, "output", ""))
            return 0

        if args.command == "content-inventory":
            inventory = article_inventory(client)
            write_json(Path(args.output).expanduser(), inventory)
            output_json(
                {
                    "ok": True,
                    "article_count": inventory["article_count"],
                    "repeated_image_count": len(inventory["repeated_images"]),
                    "output": str(Path(args.output).expanduser().resolve()),
                }
            )
            return 0

        if args.command == "topic-check":
            result = topic_check(
                client, config, args.title, args.slug, args.semantic
            )
            output_json(result, args.output)
            return 0 if result["pass"] else 2

        if args.command == "image-usage":
            inventory = article_inventory(client)
            refs = inventory["image_usage"].get(args.url, [])
            output_json(
                {
                    "url": args.url,
                    "usage_count": len(refs),
                    "references": refs,
                },
                args.output,
            )
            return 0

        if args.command == "article-images":
            if not args.id and not args.slug:
                raise ValueError("article-images requires --id or --slug")
            article = client.find_article(
                args.kind, article_id=args.id, slug=args.slug
            )
            images = extract_article_images(article)
            if args.download_dir:
                directory = Path(args.download_dir).expanduser()
                for item in images:
                    local = download_image(config["STONEART_BASE_URL"], item["src"], directory)
                    item["local_path"] = str(local.resolve())
            output_json(
                {
                    "article": {
                        key: article.get(key)
                        for key in ("id", "title", "slug", "status", "author_name")
                    },
                    "images": images,
                },
                args.output,
            )
            return 0

        if args.command == "create-blog":
            payload = merge_article_defaults(
                read_json(Path(args.file).expanduser()), config, new=True
            )
            if args.dry_run:
                output_json({"ok": True, "dry_run": True, "payload": payload})
                return 0
            result = client.save_blog(payload)
            notification = (
                {"enabled": False, "ok": True, "skipped": "disabled by --no-notify"}
                if args.no_notify
                else safe_notify_feishu_blog(
                    config,
                    event="published" if payload.get("status") == "published" else "created",
                    article={**payload, "id": result.get("id")},
                )
            )
            output_json(
                {
                    "ok": True,
                    "id": result.get("id"),
                    "public_url": f"/blog/{payload['slug']}/",
                    "status": payload.get("status", "draft"),
                    "notification": notification,
                }
            )
            return 0

        if args.command == "update-blog":
            current = client.find_blog(article_id=args.id)
            patch = read_json(Path(args.file).expanduser())
            latest = client.find_blog(article_id=args.id)
            if (
                not args.force
                and current.get("updated_at")
                and latest.get("updated_at") != current.get("updated_at")
            ):
                raise RuntimeError(
                    "article changed after backup; inspect latest version or use --force"
                )
            merged = writable_article(current)
            merged.update({key: value for key, value in patch.items() if key in ARTICLE_FIELDS})
            merged = merge_article_defaults(merged, config, new=False)
            changed = {
                key: {"before": current.get(key), "after": merged.get(key)}
                for key in ARTICLE_FIELDS
                if current.get(key) != merged.get(key)
            }
            if args.dry_run:
                output_json(
                    {
                        "ok": True,
                        "dry_run": True,
                        "article_id": args.id,
                        "changed_fields": changed,
                        "merged": merged,
                    }
                )
                return 0
            backup = backup_article(current)
            result = client.save_blog(merged, args.id)
            notification = (
                {"enabled": False, "ok": True, "skipped": "disabled by --no-notify"}
                if args.no_notify or not changed
                else safe_notify_feishu_blog(
                    config,
                    event=(
                        "published"
                        if merged.get("status") == "published"
                        and current.get("status") != "published"
                        else "updated"
                    ),
                    article={**merged, "id": result.get("id", args.id)},
                    changes=changed,
                )
            )
            output_json(
                {
                    "ok": True,
                    "id": result.get("id", args.id),
                    "backup": str(backup.resolve()),
                    "public_url": f"/blog/{merged['slug']}/",
                    "status": merged.get("status"),
                    "notification": notification,
                }
            )
            return 0

        if args.command == "list-media":
            output_json(
                client.list_media(
                    args.query,
                    args.usage,
                    args.ref,
                    args.task,
                    args.page,
                    args.page_size,
                )
            )
            return 0

        if args.command == "upload-media":
            result = client.upload_media(
                Path(args.file).expanduser(), args.name.strip()
            )
            output_json(result)
            return 0

        if args.command == "media-references":
            output_json(client.media_references(args.id))
            return 0

        if args.command == "delete-media":
            if not args.confirm:
                raise RuntimeError("delete-media requires --confirm")
            output_json(client.delete_media(args.id))
            return 0

        if args.command == "replace-article-image":
            article = client.find_article(args.kind, article_id=args.id)
            body = article.get("body_html") or ""
            count = body.count(args.old_url)
            cover = article.get("cover_image") or ""
            updates_cover = not args.skip_cover and cover == args.old_url
            preview = {
                "article_id": args.id,
                "kind": args.kind,
                "title": article.get("title"),
                "old_url": args.old_url,
                "new_url": args.new_url,
                "body_replacements": count,
                "cover_replacement": updates_cover,
                "apply": args.apply,
            }
            if not args.apply:
                output_json(preview)
                return 0
            if count == 0 and not updates_cover:
                raise RuntimeError("old URL was not found in the article")
            patch = {"body_html": body.replace(args.old_url, args.new_url)}
            if updates_cover:
                patch["cover_image"] = args.new_url
            image_changes: dict[str, Any] = {}
            if count:
                image_changes["body_html"] = patch["body_html"]
            if updates_cover:
                image_changes["cover_image"] = args.new_url
            backup = backup_article(article)
            merged = writable_article(article)
            merged.update(patch)
            client.save_article(args.kind, merged, args.id)
            notification = (
                {"enabled": False, "ok": True, "skipped": "disabled by --no-notify"}
                if args.no_notify or args.kind != "blog"
                else safe_notify_feishu_blog(
                    config,
                    event="image_updated",
                    article={**merged, "id": args.id},
                    changes=image_changes,
                    note=f"替换图片 {args.old_url} → {args.new_url}",
                )
            )
            output_json(
                {
                    **preview,
                    "ok": True,
                    "backup": str(backup.resolve()),
                    "notification": notification,
                }
            )
            return 0

        raise ValueError(f"unsupported command: {args.command}")
    except ApiError as exc:
        print(
            json.dumps(
                {"error": str(exc), "status": exc.status, "payload": exc.payload},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
