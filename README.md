<picture>
  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="assets/header-static-dark.svg">
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/header-static-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/header-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/header-light.svg">
  <img alt="Daniel Nilsson — LLM engineering, full-stack, Göteborg. A custom mechanical keyboard: the name on the letter keys, the role on the modifier keys, and the spacebar held down and lit, reading Innovation developer, Quokka, beside a lit Now key." src="assets/header-light.svg" width="100%">
</picture>

I build LLM pipelines and the products around them: multi-stage prompts, parallel model calls, the
TypeScript and Python services that run them, and the Azure infrastructure underneath. Client work is
private, so the public example of how I build is this page: [one generator](tools/build-assets.py)
draws it, and [one check](tools/check-readme.mjs) gates every change.

## How I build

<picture>
  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="assets/pipeline-static-dark.svg">
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/pipeline-static-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/pipeline-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/pipeline-light.svg">
  <img alt="How a request moves: it enters a multi-stage prompt, fans out to parallel model calls and fans back in, passes a content filter that can send one call back to retry, becomes structured output, is served, and is traced and evaluated before the prompt is iterated. It runs on Azure as infrastructure as code, and ships through a deploy pipeline." src="assets/pipeline-light.svg" width="100%">
</picture>

## Stack

**Model** — Azure OpenAI · AI Foundry · MCP servers · Langfuse

**Serve** — TypeScript · Python · Flask · React + Vite · Express · pnpm monorepo

**Cloud** — App Service · Cosmos DB · Key Vault · Entra External ID (B2C) · Bicep

**Ship** — GitHub Actions · Claude Code · Cursor · AI-assisted code review · PR automation

## Experience

**Innovation developer, Quokka** — consultancy, Göteborg · now. AI-powered products end to end, from
prompt design to infrastructure as code.

## Education

**IT-högskolan** — AI and machine learning, 2022–2024. Coursework, archived:
[Machine-learning](https://github.com/Danneftw1/Machine-learning) ·
[Deep-Learning](https://github.com/Danneftw1/Deep-Learning) ·
[Databehandling](https://github.com/Danneftw1/Databehandling-Daniel-Nilsson) ·
[Data-Engineering](https://github.com/Danneftw1/Data-Engineering-Agila-Metoder) ·
[Statistik](https://github.com/Danneftw1/Statistik) ·
[Linear-Algebra](https://github.com/Danneftw1/Linear-Algebra-Python) ·
[Python](https://github.com/Danneftw1/Python-Daniel-Nilsson)

**C**, 2025 — [exercises](https://github.com/Danneftw1/C), filling gaps in low-level computing.

## Side projects

- **Claude Code setup** — hooks, subagents, slash commands and MCP config, plus a plain-text ledger.
- **Genealogy site** — two family lines; every fact is graded by how well it is sourced, and the grade
  decides how it is drawn.
- **DSP-to-DAW map** — the signal path, from converter to timeline.

## Off the clock

Drums, for seventeen years, playing and recording. Custom mechanical keyboards since 2012, built,
modded and rotated. Both are instruments you hit in time.

---

<sub>Nothing here loads from a third party. Every theme and width is rendered on every pull request
([`check.yml`](.github/workflows/check.yml)).</sub>
