# Image Policy and Replacement Workflow

## Contents

1. Purpose
2. Image inspection
3. Watermark classifications
4. Sensitive-content rule
5. Local Qwen / Wan2.7 cleaning
6. Web replacement sourcing
7. Upload and article update
8. Visual QA
9. Manifest format

## 1. Purpose

Blog images must be relevant to the article, accurately show the subject, contain no foreign watermark, and have usable alt text. Image work starts from understanding the image, not from running an edit model.

## 2. Image Inspection

Use `article-images` to collect URLs. Download them before inspection:

```bash
python scripts/stoneart_blog.py article-images \
  --id <article-id> \
  --download-dir work/<slug>/images \
  --output work/<slug>/images.json
```

Use `--kind project` to inspect images attached to a project case instead of a blog.

Inspect every image with Codex's `view_image`. Record:

- Main subject and material
- Scene and use case
- Whether the image matches the surrounding paragraph
- Watermark text, logo, URL, number, or repeated overlay
- Watermark location and severity
- Exposed intimate body parts or other sensitive content
- Existing alt text quality

When running through CC Switch with `deepseek-flash`, use `vision-batch` for 3 images at a time instead of parallel `view_image` calls. This avoids a known DeepSeek tool-call history error.

Optionally run DeepSeek vision for a structured second opinion:

```bash
python scripts/stoneart_blog.py vision \
  --image work/<slug>/images/source.jpg \
  --output work/<slug>/source-vision.json
```

Codex vision remains the final visual decision-maker. DeepSeek output is evidence, not permission to skip inspection.

## 3. Watermark Classifications

Use these labels in the manifest:

- `none`: no visible watermark; keep image.
- `foreign`: visible third-party logo, URL, stock watermark, username, or overlay.
- `stoneart`: only a current Stone Art watermark; usually keep unless the user explicitly requests removal.
- `uncertain`: possible mark; inspect at full resolution or ask DeepSeek for a second view.

Replace only `foreign` and confirmed unwanted `uncertain` watermarks. Do not run paid image editing for `none`.

## 4. Sensitive-Content Rule

Do not send images containing exposed intimate body parts to the local Qwen editor, Wan2.7, or another generative editor. This includes explicit nudity or close-ups of genitalia, buttocks, or breasts.

For classical sculpture:

- Prefer museum, Wikimedia Commons, or open-access images with clear reuse rights.
- Choose a full-object view rather than an explicit close-up.
- Record the source page, creator, license, and retrieval date.
- Do not use random search thumbnails or images with unclear ownership.
- If minors are involved in a sensitive context, stop and ask the user.

## 5. Local Qwen-Image-2.1 Cleaning with Wan2.7 Fallback

Use the default preservation prompt:

```bash
python scripts/stoneart_blog.py clean-image \
  --input work/<slug>/images/source.jpg \
  --output work/<slug>/images/source-clean.jpg
```

The prompt should remove only watermark/logo/text overlays. It should preserve the sculpture, background, lighting, colors, perspective, crop, and aspect ratio. Do not ask the model to redesign the scene unless the user explicitly requests that.

`clean-image` calls `LOCAL_IMAGE_BASE_URL` first. If the health check fails, the request times out, or the local model returns no image, it retries the same edit through the configured Wan2.7 compatible endpoint and then the DashScope SDK. Inspect the returned `provider` and `attempts` fields when a run is slower than expected.

If the result has any of these defects, reject it:

- Sculpture shape or facial features changed
- Material or color changed materially
- New objects, people, or text added
- Watermark still visible
- Background or crop changed unexpectedly
- Blurry repair, warped texture, or obvious repeated patterns

Retry at most twice. If it still fails, use a licensed no-watermark source image.

## 6. Web Replacement Sourcing

When a web replacement is required:

1. Search the exact sculpture, material, and scene rather than a generic category.
2. Prefer Wikimedia Commons, museum open-access collections, official manufacturer media, or Unsplash.
3. Verify the actual image resolves and inspect it locally.
4. Confirm reuse rights from the source page, not a search snippet.
5. Download the highest useful resolution without upscaling later.
6. Record attribution requirements in the manifest.

Do not copy a competitor's watermarked image and ask a model to clean it. That does not resolve ownership.

## 7. Upload and Article Update

Upload approved output:

```bash
python scripts/stoneart_blog.py upload-media \
  --file work/<slug>/images/source-clean.jpg \
  --name "source-clean-20261018.jpg"
```

Preview a replacement:

```bash
python scripts/stoneart_blog.py replace-article-image \
  --id <article-id> \
  --old-url "/uploads/old.jpg" \
  --new-url "/uploads/new.jpg"
```

Review the preview, then rerun with `--apply`.

Update every intended reference:

- `body_html`
- `cover_image`
- Image `alt` text
- Related product/project references only if the user requested them

Check old media references before cleanup:

```bash
python scripts/stoneart_blog.py media-references --id <old-media-id>
```

## 8. Visual QA

After replacement:

- Open the new image locally.
- Open the public article URL.
- Check the cover and in-body image at desktop width.
- Check mobile width for crops or overflow.
- Confirm the image still matches the adjacent paragraph and article thesis.
- Confirm no broken URL or old watermark remains.

## 9. Manifest Format

Save one JSON object per image in `work/<slug>/image-manifest.json`:

```json
{
  "article_id": 123,
  "slug": "example-slug",
  "old_url": "/uploads/old.jpg",
  "local_path": "work/example-slug/images/old.jpg",
  "subject": "Marble fountain in a formal garden",
  "has_watermark": true,
  "watermark_type": "foreign",
  "watermark_notes": "Stock URL in lower-right corner",
  "sensitive_content": false,
  "action": "wan_clean",
  "cleaned_path": "work/example-slug/images/old-clean.jpg",
  "new_url": "/uploads/new.jpg",
  "source_page": "",
  "license": "",
  "creator": "",
  "qa_status": "approved",
  "notes": ""
}
```
