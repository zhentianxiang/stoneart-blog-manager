---
name: stoneart-blog-manager
description: End-to-end management of Stone Art Sculpture blog posts, project-case images, and media-library images. Use this skill whenever the user asks to create, rewrite, SEO-optimize, inspect, draft, publish, or update a blog on stoneartsculpture.com; replace watermarked images used in blogs or projects; understand media-library images; upload or remove media assets; or research and write a new sculpture blog from product, project, or image inspiration. Also use it when the user asks how to use this skill, requests ready-to-copy prompts, or invokes the skill without a concrete task, and for near-miss requests such as "write a new stone carving article", "clean these project photos", "replace this blog's images", or "fix this article's Google SEO", even when the skill is not named.
compatibility: Requires Python 3.10+, network access, requests, Pillow, and dashscope for Wan2.7 image editing.
---

# Stone Art Blog Manager

Manage the Stone Art Sculpture blog and media library through the production admin API. Treat the live site as production: inspect first, preserve evidence, write drafts by default, and verify every published result.

## Configuration

Read credentials from `config.local.env` in this skill directory. Environment variables override that file. Never print passwords, API keys, or authorization tokens in chat or logs.

If `config.local.env` is absent, copy `config.example.env` and fill it. Keep it readable only by the current user:

```bash
chmod 600 config.local.env
```

The default CLI is:

```bash
cd <skill-directory>
python scripts/stoneart_blog.py --help
```

`DEEPSEEK_MODEL=deepseek-flash` maps to the current DeepSeek V4.1 Flash model exposed by the configured API. It supports text and image input.

Feishu blog notifications use:

- `FEISHU_BLOG_WEBHOOK_URL`
- `FEISHU_BLOG_WEBHOOK_SECRET`
- `FEISHU_BLOG_NOTIFY_ENABLED=true`
- `FEISHU_TIMEZONE=Asia/Shanghai`

## Start With a Usage Guide When the Task Is Open-Ended

When the user asks "how do I use this skill", asks for prompt examples, says they do not know where to start, or invokes the skill without a concrete article, image, project, or topic:

1. Read `references/usage-prompts.md`.
2. Show a short workflow menu for existing blogs, new blogs, project images, and batch processing.
3. Provide the exact copyable prompt for each relevant workflow.
4. Ask the user which workflow to start.
5. Do not call the production API or modify content until the user chooses a task.

The usage guide is part of the skill, so the user should not need to remember the prompt wording.

## Required References

Read only the references needed for the task:

- Image inspection, watermark decisions, sensitive-content handling, and image replacement: `references/image-policy.md`.
- Blog research, editing, Google SEO, and structured output: `references/seo-editor.md`.
- New-topic deduplication, image reuse rules, and title hierarchy: `references/content-planning.md`.
- Ready-to-copy prompts and first-use guidance: `references/usage-prompts.md`.
- API fields, endpoints, JSON shapes, and troubleshooting: `references/api.md`.

## Operating Rules

- Do not publish a new or rewritten article unless the user explicitly asks to publish. Create or update as `draft` first.
- Back up the current article JSON to `work/backups/` before any update. The CLI does this automatically for `update-blog`.
- Keep an evidence manifest under `work/<slug>/image-manifest.json` for image work.
- Never delete a media asset unless the user explicitly approved deletion and the asset has zero references. Use `delete-media --confirm`.
- Never silently overwrite an existing article with model-generated text. Show the proposed title, excerpt, SEO fields, image changes, and a concise diff before `--apply`.
- Blog creation, article updates, publication changes, and applied blog image replacements send a signed Feishu card after a successful save.
- A notification failure must never roll back or hide a successful article save. Report notification status separately.
- Preserve factual details such as dimensions, locations, dates, materials, and project history. Mark uncertain claims `[VERIFY]` instead of inventing facts.
- Use English for public website copy unless the user asks for another language.

## CC Switch and DeepSeek Compatibility

DeepSeek Chat rejects history where an assistant `tool_calls` message is not followed immediately by one tool result per `tool_call_id`. Some CC Switch versions mishandle parallel Codex tool calls or interleaved commentary messages, producing HTTP 400 errors such as "insufficient tool messages following tool_calls message".

When using `deepseek-flash` through CC Switch:

- Prefer one bundled Python command over multiple Codex tool calls.
- Inspect multiple images with `vision-batch`, not parallel `view_image` calls.
- Keep a single assistant turn to at most 1-3 tool calls and let all results return before writing commentary.
- Do not put assistant commentary messages between outputs belonging to one parallel tool-call batch.
- For heavy image QA or large batches, prefer the official Codex provider; use DeepSeek for text, SEO, and small image batches.
- If this error already occurred in a thread, start a new conversation. Retrying inside the failed thread keeps the invalid tool-call history and will fail again.

Batch image inspection:

```bash
python scripts/stoneart_blog.py vision-batch \
  --image work/<slug>/images/one.jpg \
  --image work/<slug>/images/two.jpg \
  --image work/<slug>/images/three.jpg \
  --batch-size 3 \
  --output work/<slug>/image-vision.json
```

## Standard Workflow

### 1. Establish the target

For an existing post, find it first:

```bash
python scripts/stoneart_blog.py find-blog --slug "<slug>"
python scripts/stoneart_blog.py get-blog --id <id> --output work/<slug>/before.json
python scripts/stoneart_blog.py article-images --id <id> --download-dir work/<slug>/images --output work/<slug>/images.json
```

For a new post, define a working slug and create its work directory:

```bash
mkdir -p work/<slug>/images
```

For project-case images, find the project first:

```bash
python scripts/stoneart_blog.py list-projects --query "<project title or slug>"
python scripts/stoneart_blog.py get-project --id <project-id> --output work/<project-slug>/before.json
python scripts/stoneart_blog.py article-images --kind project --id <project-id> --download-dir work/<project-slug>/images --output work/<project-slug>/images.json
```

### 2. Inspect every relevant image

Read `references/image-policy.md` before classifying images.

1. Open every downloaded image with Codex's `view_image`.
2. Record subject, scene, visible watermark text/location, and sensitive-content status.
3. Optionally ask DeepSeek for a second structured description:

```bash
python scripts/stoneart_blog.py vision \
  --image work/<slug>/images/example.jpg \
  --output work/<slug>/example-vision.json
```

4. Do not infer a replacement before understanding the sculpture, material, setting, and article context.

### 3. Replace watermarked images

For an image with a visible watermark and no exposed intimate body parts:

```bash
python scripts/stoneart_blog.py clean-image \
  --input work/<slug>/images/source.jpg \
  --output work/<slug>/images/source-clean.jpg
```

Inspect the result with `view_image`. It must keep the same subject, composition, material, lighting, background, and aspect ratio. Retry at most twice if the model adds artifacts, changes the sculpture, or leaves watermark remnants.

If the image contains exposed intimate body parts, do not send it to the image editor. Find a relevant no-watermark replacement from a reputable source such as Wikimedia Commons, museum open-access collections, Unsplash, or the original manufacturer only when reuse is clearly permitted. Record source URL, license, creator, and date in the manifest.

Upload the approved replacement:

```bash
python scripts/stoneart_blog.py upload-media \
  --file work/<slug>/images/source-clean.jpg \
  --name "source-clean-20261018.jpg"
```

Use a unique filename. The CLI prints the new `/uploads/...` URL.

### 4. Update article image references

Preview first:

```bash
python scripts/stoneart_blog.py replace-article-image \
  --kind blog \
  --id <article-id> \
  --old-url "/uploads/old-asset.jpg" \
  --new-url "/uploads/new-asset.jpg"
```

After reviewing the preview, add `--apply`. The command updates matching `body_html` occurrences and `cover_image`. Update image `alt` text in the same content change when it is generic or empty.

Use `--kind project` for project-case pages. The image replacement flow is the same, but the article edit commands remain blog-only unless the user explicitly asks to change project copy.

Check old asset usage:

```bash
python scripts/stoneart_blog.py media-references --id <old-media-id>
```

Do not delete the old asset while references remain. If it is unused and the user approved cleanup, use `delete-media --id <id> --confirm`.

### 5. Research and rewrite content

Read `references/seo-editor.md` and `references/content-planning.md`.

Use local evidence first:

```bash
python scripts/stoneart_blog.py list-media --query "marble fountain" --page-size 50
python scripts/stoneart_blog.py list-blogs --query "marble fountain" --limit 50
```

For a new article, choose one clear search intent. Run the topic duplicate gate before drafting:

```bash
python scripts/stoneart_blog.py content-inventory --output work/content-inventory.json
python scripts/stoneart_blog.py topic-check --title "<candidate title>" --slug "<slug>" --semantic --output work/topic-check.json
```

Do not create the article if deterministic risk is not `low` or semantic duplicate risk is `0.35` or higher. Improve the existing article instead.

Prefer unused media for a new article:

```bash
python scripts/stoneart_blog.py list-media --usage unused --query "<subject>" --page-size 100
python scripts/stoneart_blog.py image-usage --url "/uploads/example.jpg"
```

Do not reuse an image from another blog or project without explicit approval. Gather inspiration from reputable B2B suppliers, museums, historic sources, and relevant Stone Art products/projects, but write original copy. Never copy competitor paragraphs.

Generate a structured SEO proposal without writing to the site:

```bash
python scripts/stoneart_blog.py seo-rewrite \
  --id <article-id-or-omit-for-new> \
  --brief "Target: buyers comparing marble fountains for villas" \
  --output work/<slug>/seo-proposal.json
```

For new content, pass `--input work/<slug>/research.json` instead of `--id`.

Review the proposal yourself. Reject unsupported claims, keyword stuffing, repetitive AI phrasing, fake expertise, and any claim that Stone Art cannot verify.

Use the exact heading hierarchy from `references/content-planning.md`: the saved title is H1; `body_html` starts with an intro and uses H2 for major sections and H3 only for subsections under an H2.

### 6. Save safely

Create a new draft:

```bash
python scripts/stoneart_blog.py create-blog --file work/<slug>/draft.json --dry-run
python scripts/stoneart_blog.py create-blog --file work/<slug>/draft.json
```

Update an existing article:

```bash
python scripts/stoneart_blog.py update-blog --id <id> --file work/<slug>/patch.json --dry-run
python scripts/stoneart_blog.py update-blog --id <id> --file work/<slug>/patch.json
```

The update command fetches the current article, merges only the supplied fields, backs it up, and refuses to overwrite a newer `updated_at` unless `--force` is supplied.

After saving, fetch the article again and verify title, slug, status, author, cover image, body HTML, SEO fields, and public URL.

### 7. Publish only on explicit request

Publish by creating a patch file with `"status": "published"` and running `update-blog`. Then verify the public URL and HTTP 200 response.

## Feishu Notifications

The CLI automatically sends notifications after:

- Creating a new blog draft or publishing a new blog
- Updating an existing blog and changing one or more fields
- Changing a blog from draft to published
- Applying an image URL replacement to a blog

The card includes action, title, status, article ID, author, changed field labels, local time in `FEISHU_TIMEZONE`, and a button to open the public article or admin page.

Test the signed webhook without changing content:

```bash
python scripts/stoneart_blog.py test-feishu
```

Suppress one notification when intentionally performing a silent update:

```bash
python scripts/stoneart_blog.py update-blog ... --no-notify
```

Do not suppress notifications for normal publishing or editorial updates unless the user requested it.

## Image Decision Matrix

| Situation | Action |
|---|---|
| Clear watermark or stock-site overlay | AI clean with Wan2.7, then visual QA |
| No visible watermark | Keep image; do not call paid model |
| Subtle mark uncertain after two views | Use DeepSeek vision second opinion; keep if still uncertain |
| Exposed intimate body parts | Do not send to Wan2.7; source a suitable licensed replacement |
| Minors in a sensitive context | Stop and ask the user; do not generate or source replacement |
| AI output changes subject/composition | Reject, retry once or source a replacement |
| Replacement has unknown license | Do not use |

## Content Quality Checklist

- One clear search intent and one visible H1 from the article title.
- Title generally 45-60 characters; SEO title generally 50-60 characters.
- Meta description generally 140-160 characters.
- Intro answers the query quickly and naturally.
- H2/H3 structure supports scanning and the generated table of contents.
- Specific, verifiable details replace generic claims.
- Include product/project internal links only where useful.
- Add FAQ only when real questions remain.
- Add descriptive image alt text; never keyword-stuff alt text.
- Avoid unsupported superlatives, fake statistics, fake dates, and invented customer stories.
- Check slug, canonical intent, duplicate topics, and cannibalization against existing posts.

## Common Failures

- Calling image editing on every image. This wastes money and can damage acceptable photos.
- Uploading a replacement without inspecting it.
- Replacing the image URL only in `cover_image` while leaving the same asset in `body_html`.
- Deleting an old asset before checking references.
- Publishing generated content without fact-checking.
- Sending a sensitive image to a generative editor.
- Reusing a competitor's title, outline, or paragraphs too closely.
