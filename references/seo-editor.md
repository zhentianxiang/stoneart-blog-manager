# SEO Editor and Content Workflow

## Contents

1. Editorial goal
2. Research
3. Search intent
4. Google SEO rules
5. Article structure
6. Fact checking
7. Structured model output
8. New article workflow
9. Existing article workflow

## 1. Editorial Goal

Write useful, specific, people-first articles that help international buyers evaluate sculpture products and plan projects. The content must demonstrate real product and project knowledge rather than generic marketing language.

The intended reader is usually one of:

- Landscape architect or designer
- Contractor or project buyer
- Villa, hotel, church, park, or commercial-space owner
- Buyer comparing materials, sizes, styles, installation, or maintenance

## 2. Research

Use at least two independent evidence sources when possible:

- Stone Art products, projects, media, and existing posts
- Relevant museum or historical sources
- Reputable B2B suppliers for product terminology and buyer concerns
- Stone Art's own factory and project capabilities

Do not copy competitor structure, wording, examples, or statistics. Extract only the underlying buyer question and improve the answer with original Stone Art evidence.

## 3. Search Intent

Define the page as one of:

- Informational: history, style, material, meaning, care
- Commercial investigation: comparison, buying guide, size, cost factors
- Transactional: custom fountain, statue, project quote
- Inspirational: project ideas, villa garden, church sculpture

Do not mix three intents into one title. If two intents are valuable, make two articles and link them.

## 4. Google SEO Rules

- Write for humans first; no keyword stuffing.
- Use the primary phrase naturally in the title, intro, one H2, image alt, and conclusion.
- Use semantic variants instead of repeating the exact keyword.
- Title: usually 45-60 characters, specific and click-worthy without clickbait.
- SEO title: usually 50-60 characters.
- Meta description: usually 140-160 characters, benefit plus specificity.
- Slug: short, readable, lowercase, hyphenated, no dates unless needed.
- Use one clear article thesis.
- Answer the main question in the first 100-150 words.
- Use H2/H3 headings that reflect real sub-questions.
- Include concrete details: material, finish, size logic, setting, installation, maintenance, process, or project constraints.
- Use tables for real comparisons, not decoration.
- Include FAQ only for genuine remaining questions.
- Add descriptive internal links to relevant products, categories, projects, or articles.
- Add descriptive external citations only when they improve trust.
- When changing a published slug, preserve the old URL with a permanent `301` and update every internal link to the new URL.
- Confirm the new URL is in the sitemap and request Search Console reindexing for important pages.
- Avoid false urgency, fabricated statistics, fake testimonials, and invented expertise.
- Avoid repetitive AI phrases such as "in today's fast-paced world", "comprehensive guide" used without substance, and "beyond aesthetics".
- Use inclusive, plain English. Explain industry terms when first used.

## 5. Article Structure

Recommended default:

- H1 comes from the article title in the site template; do not include another H1 in `body_html`.
- Intro: answer the query and state who this helps.
- H2: core decision or historical context
- H2: selection criteria or major categories
- H2: material, size, placement, or installation implications
- H2: Stone Art process or project evidence
- H2: maintenance and common mistakes
- H2: how to request a quote
- FAQ
- Conclusion with one clear next step

Use H3 only under an H2. Keep headings descriptive; avoid empty labels like "Overview" unless the section is actually an overview.

## 6. Fact Checking

- Preserve exact dimensions, dates, locations, and project facts from source material.
- Do not state a price unless Stone Art has approved it.
- Do not claim a material lasts a specific number of years without a source.
- Do not claim museum quality or exact replication unless supported by project evidence.
- Mark unresolved claims as `[VERIFY]` in draft JSON. Never publish a draft containing `[VERIFY]`.
- Do not generate customer names or project stories.

## 7. Structured Model Output

DeepSeek should return one JSON object:

```json
{
  "title": "",
  "slug": "",
  "excerpt": "",
  "seo_title": "",
  "seo_description": "",
  "body_html": "",
  "image_alt_text": [
    {"url": "/uploads/example.jpg", "alt": ""}
  ],
  "internal_links": [
    {"anchor": "", "url": ""}
  ],
  "faq": [
    {"question": "", "answer": ""}
  ],
  "editorial_notes": [],
  "claims_to_verify": []
}
```

The model must not claim to have browsed unless research material is supplied. The parent agent verifies all claims.

## 8. New Article Workflow

1. Inspect available images before choosing a narrow topic.
2. Choose one product/project angle with clear search intent.
3. Research existing Stone Art posts to avoid overlap.
4. Research two relevant external sources if historical or technical claims are made.
5. Draft with DeepSeek using `seo-rewrite --input`.
6. Verify claims and rewrite generic sections.
7. Save as draft.
8. Preview on the public site after saving.
9. Publish only when the user explicitly asks.

## 9. Existing Article Workflow

1. Fetch current article and images.
2. Identify why the article underperforms: intent mismatch, thin sections, weak title, outdated facts, poor images, missing links, or weak CTA.
3. Preserve useful original text instead of replacing everything.
4. Improve title, excerpt, SEO fields, headings, examples, comparison structure, and conclusion.
5. Keep factual project details.
6. Update image URLs and alt text only when needed.
7. Back up and save.
8. Compare before/after and verify the live page.
