# Content Planning, Deduplication, and Article Structure

## Contents

1. Non-duplicate topic gate
2. Image reuse gate
3. Title hierarchy
4. Article blueprint
5. How to write each section
6. Image-to-topic workflow
7. Final approval checklist

## 1. Non-duplicate Topic Gate

Every new blog must pass two checks before drafting:

```bash
python scripts/stoneart_blog.py content-inventory \
  --output work/content-inventory.json

python scripts/stoneart_blog.py topic-check \
  --title "Candidate SEO title" \
  --slug "candidate-slug" \
  --semantic \
  --output work/topic-check.json
```

Pass conditions:

- `deterministic_risk` is `low`.
- Semantic `duplicate_risk` is below `0.35`.
- No existing article owns the same search intent.
- The new article adds distinct evidence, images, examples, or a different buyer stage.

Do not create a new article when the topic is only a reworded version of an existing page. Improve the existing article instead.

Similarity is judged at the level of search intent, not only title wording. For example:

- "Marble Fountain Size Guide" and "How to Choose a Fountain Size" are duplicates.
- "Marble Fountain Size Guide" and "Marble Fountain Installation Checklist" can coexist.
- "Famous Greek Statues" and "Famous Greek Sculptures" are duplicates.

## 2. Image Reuse Gate

New articles should prefer media-library assets with `usage=unused`:

```bash
python scripts/stoneart_blog.py list-media \
  --usage unused \
  --query "marble fountain" \
  --page-size 100
```

Before using any image from an existing article or project:

```bash
python scripts/stoneart_blog.py image-usage \
  --url "/uploads/example.jpg" \
  --output work/example-image-usage.json
```

Rules:

- Default rule: do not reuse an image already used by another blog or project.
- A reused image must be explicitly approved by the user.
- Reuse is more defensible for a product image used across a product page and one relevant buying guide than for two competing blog posts.
- Never reuse the same hero image for two articles targeting the same keyword.
- The media server deduplicates exact file content by SHA256, but a crop or renamed copy still counts as duplicate content for editorial purposes.
- Inspect each selected image visually and write unique, descriptive alt text.

## 3. Title Hierarchy

The website template renders the saved article title as the page H1. Do not put another H1 in `body_html`.

Use this hierarchy:

```text
H1  Saved article title
    Intro paragraph
    H2  Major buyer question or theme
        H3  Specific sub-question
        H3  Specific sub-question
    H2  Next major buyer question or theme
    H2  Comparison or selection framework
    H2  Stone Art project/process evidence
    H2  FAQ
        H3  Individual question
    H2  Conclusion and next step
```

Rules:

- H1: one per page, supplied by the article title field.
- H2: 4-8 major sections that summarize the page.
- H3: only for subpoints that genuinely sit under an H2.
- Do not skip from H2 to H4.
- Do not use headings as decorative labels.
- The table of contents is generated from H2 headings, so each H2 must describe a meaningful section.

## 4. Article Blueprint

Default new-blog blueprint:

1. Title field: primary search intent plus a specific qualifier.
2. Intro: 100-150 words, answer the main question immediately.
3. H2: decision criteria or historical context.
4. H2: major categories, materials, or styles.
5. H2: size, placement, installation, or maintenance.
6. H2: project evidence from Stone Art.
7. H2: comparison table if there is a real decision to compare.
8. H2: how to request a quote.
9. H2: FAQ with H3 questions.
10. H2: concise conclusion and one next step.

Use 1 hero image and 2-5 body images when they add new evidence. Do not pad the article with repetitive images.

## 5. How to Write Each Section

### Title

Use one of these patterns:

- `[Primary topic]: [buyer outcome]`
- `How to [choose/plan/install] [specific object] for [specific setting]`
- `[Material/style] [object] Guide for [audience]`
- `[Project type] Case Study: [specific result or location]`

Examples:

- `Marble Fountain Size Guide for Villa Gardens`
- `How to Plan a Marble Fountain Installation`
- `Stainless Steel Sculpture for Public Parks: Buyer Guide`

Avoid:

- Vague titles such as `Everything You Need to Know`
- Year stuffing unless the article is genuinely annual
- Promises such as `Best Price Guaranteed` without evidence

### Intro

Answer the query, name the audience, and explain what decision the article helps them make. Use the primary keyword once if natural. Do not start with "In today's world".

### H2 Sections

Each H2 should contain:

- A direct answer or claim.
- A concrete explanation.
- One example, specification, or project detail.
- A natural transition to the next decision.

### H3 Subsections

Use H3 for options inside one H2, such as:

- Fountain types
- Stone materials
- Installation constraints
- Maintenance tasks

### FAQ

Use real buyer questions. Keep answers 40-90 words. Do not repeat whole sections.

### Conclusion

Summarize the decision in 2-3 sentences and add one specific next step, such as requesting a custom quote or reviewing a related project.

## 6. Image-to-Topic Workflow

1. Download candidate images.
2. Inspect them locally with `view_image`.
3. Group images by subject, material, setting, and buyer problem.
4. Choose a topic where the images provide real evidence.
5. Confirm the topic is not already covered.
6. Only then ask DeepSeek for the SEO proposal.

Do not choose a topic first and then force unrelated images into it. The images should reveal the article's angle.

## 7. Final Approval Checklist

- Topic checker passed.
- Semantic duplicate risk is below `0.35`.
- All images are visually relevant and pass the reuse gate.
- No watermark errors or sensitive-image violations.
- H1/H2/H3 hierarchy is valid.
- DeepSeek output was fact-checked and edited.
- No `[VERIFY]` remains.
- SEO title and meta description meet length targets.
- Internal links point to relevant pages, not the homepage by default.
- Any changed published slug has a verified permanent redirect from the old URL.
- Draft is saved before publishing.
