# Stone Art Blog Manager

Codex skill for managing Stone Art Sculpture blogs, project images, media-library assets, watermarked images, and Google SEO content.

## Features

- Inspect and edit existing Stone Art blogs
- Create SEO-focused blog drafts
- Prevent duplicate topics with deterministic and DeepSeek semantic checks
- Prefer unused media and detect repeated images across blogs/projects
- Download and inspect article images locally
- Detect watermarks with Codex and optional DeepSeek vision
- Clean watermarked images with Alibaba Wan2.7
- Replace sensitive images with licensed no-watermark sources
- Upload replacements to the Stone Art media library
- Update cover, body image URLs, and alt text
- Back up articles before updates
- Keep all new content as drafts by default
- Send signed Feishu cards for blog creation, publication, updates, and image replacements
- Format Feishu notification times in configurable local time rather than UTC
- Include clickable public article and admin edit links in Feishu cards
- Add a DeepSeek-generated Simplified Chinese title line for English blog titles

## Install

Copy this folder into a Codex skill directory:

```text
~/.agents/skills/stoneart-blog-manager/
```

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Create local configuration:

```bash
cp config.example.env config.local.env
chmod 600 config.local.env
```

Fill in the site credentials and model API keys. Never commit `config.local.env`.

## Quick Start

Open a new Codex conversation and ask:

```text
使用 $stoneart-blog-manager，告诉我应该怎么用。
```

The skill will show the recommended workflows and ready-to-copy prompts before changing production content.

## CLI

```bash
python scripts/stoneart_blog.py --help
python scripts/stoneart_blog.py check
python scripts/stoneart_blog.py content-inventory --output work/content-inventory.json
python scripts/stoneart_blog.py topic-check --title "Example title" --slug example-title --semantic
```

See `SKILL.md` and `references/` for the full workflow.

## Security

- `config.local.env` is ignored by Git.
- Admin credentials and model API keys must never be committed.
- Destructive media deletion requires explicit confirmation.
- Blog updates create local backups under `work/backups/`.
- Publishing requires an explicit user request.
