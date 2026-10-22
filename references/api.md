# Stone Art Admin API Reference

## Authentication

Base URL comes from `STONEART_BASE_URL`.

`POST /api/admin/session`

```json
{
  "username": "admin",
  "password": "***"
}
```

The response contains a bearer `token`. If a captcha is required:

1. `GET /api/admin/captcha`
2. Read the arithmetic question and token.
3. Retry `POST /api/admin/session` with `captcha_answer` and `captcha_token`.

Send protected requests with:

```text
Authorization: Bearer <token>
```

## Blog Endpoints

- `GET /api/admin/blog-posts?page=1&page_size=30&q=&status=`
- `POST /api/admin/blog-posts`
- `PUT /api/admin/blog-posts/{id}`
- `DELETE /api/admin/blog-posts/{id}`
- `PATCH /api/admin/blog-posts/status`

The list endpoint returns full article objects, including `body_html`, so a detail request can be implemented by finding the ID in paginated results.

Article writable fields:

```text
title, slug, excerpt, body_html, body_markdown, cover_image, published_at,
seo_title, seo_description, status, sort_order, author_name, author_role,
author_bio, author_avatar, show_toc, ai_rewritten_at, ai_rewrite_count
```

`title` and `slug` are required. `status` is `draft` or `published`. If `body_markdown` is sent, the server converts it and overwrites `body_html`; send only `body_html` when preserving existing HTML.

## Project Endpoints

- `GET /api/admin/projects?page=1&page_size=30&q=&status=`
- `POST /api/admin/projects`
- `PUT /api/admin/projects/{id}`
- `DELETE /api/admin/projects/{id}`
- `PATCH /api/admin/projects/status`

Projects use the same article JSON fields as blog posts. The skill focuses on project image replacement through the same media workflow.

## Media Endpoints

- `GET /api/admin/media?page=1&page_size=40&q=&usage=&task=&ref=`
- `POST /api/admin/media` with multipart field `file`
- `GET /api/admin/media/{id}/references`
- `DELETE /api/admin/media/{id}`
- `POST /api/admin/media/delete-selected`

Upload response:

- New upload: media asset object
- Deduplicated content: `{"deduplicated": true, "asset": {...}}`
- Duplicate filename: HTTP 409 with existing `asset`

The upload API does not overwrite files. Upload a new asset, update article references, then delete the old asset only after checking references.

## Public URLs

Relative media URLs such as `/uploads/file.jpg` resolve against the site base URL.

Blog public URL:

```text
/blog/{slug}/
```

## API Troubleshooting

- `401 invalid credentials`: check username/password.
- `401 invalid captcha`: fetch a fresh captcha and retry.
- `409 filename already exists`: choose a unique filename.
- `media is still in use`: update all article references before deleting.
- `title and slug are required`: fill required fields.
- `status must be draft or published`: use a supported status.

## CLI

Use the bundled CLI for deterministic operations:

```bash
python scripts/stoneart_blog.py check
python scripts/stoneart_blog.py check-redirect --old-url /blog/old-slug/ --new-url /blog/new-slug/
python scripts/stoneart_blog.py content-inventory --output work/content-inventory.json
python scripts/stoneart_blog.py topic-check --title "Marble Fountain Size Guide" --slug marble-fountain-size-guide --semantic
python scripts/stoneart_blog.py find-blog --slug example
python scripts/stoneart_blog.py get-blog --id 123 --output work/example/before.json
python scripts/stoneart_blog.py list-media --query fountain
python scripts/stoneart_blog.py list-projects --query fountain
python scripts/stoneart_blog.py article-images --kind project --id 123
python scripts/stoneart_blog.py image-usage --url /uploads/example.jpg
python scripts/stoneart_blog.py upload-media --file image.jpg
python scripts/stoneart_blog.py create-blog --file draft.json
python scripts/stoneart_blog.py update-blog --id 123 --file patch.json
python scripts/stoneart_blog.py test-feishu
```

Add `--dry-run` to `create-blog` or `update-blog` to inspect the exact payload and changed fields without writing. Use `--help` on any command for the full argument list.

`check-redirect` requires a permanent `301` or `308`, verifies the destination path and query string, and confirms the new URL is reachable.

## Feishu Blog Notifications

The CLI signs Feishu custom-bot requests with the current Unix timestamp and `FEISHU_BLOG_WEBHOOK_SECRET`. It sends interactive cards after successful create, update, publish, and applied image-replacement operations. Display time uses `FEISHU_TIMEZONE` and defaults to `Asia/Shanghai`.

Published cards include both the public article URL and admin edit URL. Draft cards include the admin edit URL. English titles are translated to Simplified Chinese with DeepSeek; translation failures silently omit the extra title line and never affect article saving. Notification failures are returned under `"notification"` but do not undo the saved article. Use `--no-notify` only for intentional silent operations.
