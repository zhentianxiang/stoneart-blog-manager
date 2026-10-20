# Usage Guide and Ready-to-Copy Prompts

## Contents

1. When to show this guide
2. Recommended rollout order
3. Existing article prompts
4. Batch image-audit prompts
5. New-blog prompts
6. Project-image prompt
7. Short everyday prompts
8. DeepSeek and CC Switch safety prompt

## 1. When to Show This Guide

Show this guide when the user asks:

- "这个 skill 怎么用？"
- "给我一些提示词"
- "我应该先做什么？"
- "帮我开始"
- Invokes the skill without a specific article, image, project, or topic.

Present the workflows briefly, include the relevant copyable prompts, and ask which workflow the user wants. Do not start with a paid image edit, production write, upload, or publish.

## 2. Recommended Rollout Order

For a large existing content library:

1. Audit one article as a sample.
2. Inventory all articles and images without writing.
3. Review the audit.
4. Replace watermarked images in batches of 10-20 articles.
5. Optimize SEO in the same batches after image approval.
6. Run topic deduplication for new content.
7. Mine unused media for new topics.
8. Create drafts.
9. Publish only after explicit approval.

Avoid one prompt that asks the model to process all 196 articles at once. Large batches make cost, mistakes, and review difficult.

## 3. Existing Article Prompts

### Single article audit

```text
使用 $stoneart-blog-manager 检查这篇博客：
<博客URL>

先不要修改线上内容。读取文章和全部图片，下载后逐张识图，告诉我：
1. 哪些图片有水印，水印类型和位置
2. 图片中的雕塑主体、材质、场景和文章关联
3. 是否有暴露隐私部位
4. 哪些图片建议保留、去水印或从授权网站换图
5. 每张图片在封面或正文中的使用位置
6. 建议的 SEO 标题、描述和正文优化方向

先输出报告和 dry-run，等我确认。
```

### Apply one article

```text
使用 $stoneart-blog-manager 按刚才确认的方案处理这篇文章。

要求：
- 只处理确认有水印的图片
- 无水印图片不调用本地 Qwen 或 Wan2.7
- 有敏感内容的图片不发给生成模型
- 新图片先上传素材库
- 替换正文和封面 URL，并优化图片 alt
- 修改前备份，先 dry-run
- 保持原发布状态
- 完成后验证公开页面
```

## 4. Batch Image-Audit Prompts

### Inventory only

```text
使用 $stoneart-blog-manager 扫描全部已发布博客。

第一阶段只做盘点，不修改、不上传、不发布：
- 下载每篇博客的封面和正文图片
- 逐张识图
- 用 image-usage 检查图片是否已被其他博客或项目使用
- 记录文章 ID、标题、URL、图片 URL、水印情况、敏感内容、建议动作
- 输出 work/all-blogs-image-audit.json

不要对无水印图片调用图像编辑模型，也不要做全量去水印。先给我盘点报告。
```

### Process one batch

```text
使用 $stoneart-blog-manager 执行 work/all-blogs-image-audit.json 中的第 1-20 篇。

规则：
- 只处理 foreign watermark
- 没有水印的图片不要调用模型
- 有暴露隐私部位的图片，改用 Wikimedia、博物馆开放资源或其他有明确授权的图片
- 新图片不能与其他博客或项目重复
- 上传新素材，不覆盖旧素材
- 替换正文和封面 URL
- 修改前 dry-run，确认后 apply
- 保留原发布状态
- 每篇输出备份、旧图、新图和结果
- 这一批完成后停下来汇总
```

### SEO pass for the same batch

```text
使用 $stoneart-blog-manager 对刚处理完的同一批博客做 Google SEO 优化。

要求：
- 保留真实项目、尺寸、地点、材料和日期
- 不编造价格、客户评价、统计数据
- 后台 title 作为 H1，正文不要再写 H1
- H2 用于主要章节，H3 只用于 H2 下面的子问题
- FAQ 使用一个 H2，每个问题用 H3
- 优化标题、SEO 标题、meta description、摘要、内部链接和 FAQ
- 先 dry-run 并显示字段变化
- 确认后再保存
```

## 5. New-Blog Prompts

### Topic discovery from unused images

```text
使用 $stoneart-blog-manager 为我规划 5 篇新的博客选题。

从以下信息中寻找机会：
- 素材库中 usage=unused 的图片
- 现有 196 篇博客
- 现有项目案例
- 网站销售的产品

每个选题先按图片内容识别主体、材质、场景和买家问题，再执行：
- content-inventory
- topic-check --semantic
- image-usage

每篇输出：
1. 建议标题
2. 目标关键词和搜索意图
3. 为什么与现有文章不重复
4. 计划使用的图片 ID 和 URL
5. H1/H2/H3 大纲
6. 计划引用的产品、项目或内部链接

不要创建博客，不要保存正文。
```

### Write one selected topic

```text
使用 $stoneart-blog-manager 写第 2 个选题。

要求：
- 重新执行本地和 DeepSeek 语义查重，重复风险必须低于 0.35
- 默认只使用未使用过的图片
- 根据图片实际内容写文章，不要先写内容再硬配图
- 研究现有博客、项目和同行 B2B 内容，但不能复制
- 标题由后台 title 字段作为 H1
- 正文不要包含 H1
- 使用 4-8 个 H2
- H3 只能放在 H2 下面
- FAQ 使用一个 H2，每个问题用 H3
- 正文 HTML 中包含具体事实、比较表、内部链接和清晰的下一步
- 输出 SEO 标题、meta description、摘要、正文和图片 alt
- 先给我 dry-run，不保存
```

### Save as draft

```text
使用 $stoneart-blog-manager 把刚才确认的方案保存为草稿。

- 作者：Tian Xiang
- 职位：General Manager
- 使用默认头像和简介
- status=draft
- 自动目录开启
- 保存后读取一次文章，检查标题、Slug、图片、H2/H3、SEO 字段和正文
- 给我后台编辑链接和公开预览 URL
```

### Publish

```text
使用 $stoneart-blog-manager 检查这篇草稿的标题、meta description、H2/H3、图片 alt、内部链接和移动端显示。确认无误后发布，并验证公开 URL 和 HTTP 状态。
```

## 6. Project-Image Prompt

```text
使用 $stoneart-blog-manager 检查这个项目案例的图片：
<项目标题或URL>

先 list-projects 找到项目 ID，再下载图片并逐张识图。检查水印、敏感内容、图片重复使用情况和文章关联。

只输出替换方案，不修改项目。确认后再：
- 使用本地 Qwen-Image-2.1（失败回退 Wan2.7）或授权图片替换
- 上传新素材
- 使用 replace-article-image --kind project 预览
- 确认后 apply
- 检查旧图引用
```

## 7. Short Everyday Prompts

```text
使用 $stoneart-blog-manager 检查这篇博客，先 dry-run，不要修改：
<URL>
```

```text
使用 $stoneart-blog-manager 扫描现有博客中有水印的图片，只出报告。
```

```text
使用 $stoneart-blog-manager 从没用过的素材图中找 3 个不与现有博客重复的新选题。
```

```text
使用 $stoneart-blog-manager 给我看这个 skill 的推荐使用流程和提示词，先不要执行任务。
```

## 8. DeepSeek and CC Switch Safety Prompt

```text
使用 $stoneart-blog-manager，当前 Codex 通过 CC Switch 使用 deepseek-flash。

请避免并行工具调用和工具结果之间插入普通助手消息。批量检查图片时使用：
python scripts/stoneart_blog.py vision-batch --image ... --image ... --batch-size 3

如果这轮已经出现 tool_calls/tool_call_id 400 错误，不要继续当前会话，提醒我新建对话后重新开始。
```
