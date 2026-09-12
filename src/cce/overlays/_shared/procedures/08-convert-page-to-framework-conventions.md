---
name: convert-page-to-framework-conventions
title: "Convert a page to framework conventions"
description: "Rewrite a legacy or non-conforming Markdown page so it matches this framework's page conventions: one H1, an anchored table-of-contents list, a Context section with the framework's cross-reference line, inclusive language, relative in-repo links, and clean markdownlint with MD013 and MD033 disabled."
---

Use this procedure when a page in this repository does not look like the rest of the framework and needs to be brought into line without changing what it says. The page conventions are not written down as rules in `CONTRIBUTING.md`; they are observed across the framework's pages, so the exemplars below are the specification. The observed threshold is: an H1 and a Context section always; a table of contents once the page has two or more level-2 headings.

The Context section opens with a cross-reference line that comes in two variants. Most practice and pattern pages use the principles-style cross-reference, as at `practices/testing.md:17`, pointing at `principles.md` by a relative path; a few root pages use the quality-framework-style line instead, as at `tech-debt.md:14`, pointing at `README.md`. Some pages write that line as a plain paragraph rather than a bullet, for example `practices/api-policies.md` and `any-decision-record-template.md`, so match the variant and shape used by the page's neighbours. Compute the relative path from the page's own directory: a page three directories deep needs three `../` segments.

`CONTRIBUTING.md`, `inclusive-language.md` and `scripts/markdown-check-format.sh` carry the rules that are written down: how contributions are made, which terms to avoid, and the exact markdownlint invocation (MD013 and MD033 disabled) the repository's workflow runs. The pages `tech-debt.md`, `patterns/fast-feedback.md`, `practices/api-policies.md` and `any-decision-record-template.md` are exemplars of page shape. `quickstart.md` and `README.md` are counter-examples: they predate the conventions and must not be copied for page shape, even though they are valid pages in their own right.

#### Reference (rules): CONTRIBUTING.md

<!-- cce:include CONTRIBUTING.md -->

#### Reference (rules): inclusive-language.md

<!-- cce:include inclusive-language.md -->

#### Reference (rules): scripts/markdown-check-format.sh

```bash
<!-- cce:include scripts/markdown-check-format.sh -->
```

#### Reference (exemplar): tech-debt.md

<!-- cce:include tech-debt.md -->

#### Reference (exemplar): patterns/fast-feedback.md

<!-- cce:include patterns/fast-feedback.md -->

#### Reference (exemplar): practices/api-policies.md

<!-- cce:include practices/api-policies.md -->

#### Reference (exemplar): any-decision-record-template.md

<!-- cce:include any-decision-record-template.md -->

#### Reference (counter-example): quickstart.md

<!-- cce:include quickstart.md -->

#### Reference (counter-example): README.md

<!-- cce:include README.md -->

When you have used this procedure, end your reply with the line `procedure: convert-page-to-framework-conventions`.
