<picture>
  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="assets/header-static-dark.svg">
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/header-static-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/header-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/header-light.svg">
  <img alt="Daniel Nilsson — LLM engineering, full-stack, Göteborg. A pixel drum waveform crosses a playhead and comes out the other side as discrete token columns." src="assets/header-light.svg" width="100%">
</picture>

I build LLM pipelines and the products around them: prompt design, model orchestration, the
TypeScript and Python services that run them, and the Azure infrastructure underneath. Day job is
innovation developer at **Quokka** in Gothenburg, shipping AI features end to end.

Seventeen years behind a drum kit came first. Multi-mic recording teaches phase, gain staging and
signal flow; LLM work is the same discipline with tokens where the transients were.

## The chain

<picture>
  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="assets/pipeline-static-dark.svg">
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/pipeline-static-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/pipeline-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/pipeline-light.svg">
  <img alt="Five pixel-sprite stages on a dashed rail with a pulse travelling through them: prompt, orchestrate, serve, ship, observe." src="assets/pipeline-light.svg" width="100%">
</picture>

**Prompt** — multi-stage prompt design, structured output, content-filter and retry handling.

**Orchestrate** — parallel model calls, fan-out and fan-in, and a sane answer when one stage fails.
`Azure OpenAI` · `AI Foundry`

**Serve** — React + Vite frontends, Express APIs, Python/Flask AI services, one pnpm monorepo.
`TypeScript` · `Python` · `React`

**Ship** — infrastructure as code and pipelines that do not need me awake. `Bicep` ·
`App Service` · `Cosmos DB` · `Key Vault` · `Entra External ID` · `GitHub Actions`

**Observe** — traces, evals and prompt iteration. `Langfuse`

## Now

- **Agent tooling I actually live in** — hooks, subagents, slash commands and MCP wiring for Claude
  Code, kept under version control instead of hand-edited, with a plain-text ledger that records
  what each session changed. `private`
- **A genealogy site where confidence is drawn, not labelled** — a sourced fact is full ink on a
  solid line, a hypothesis is pencil: thinner, paler, dashed. Nothing moves up a grade without a
  citation. `private`
- **Mapping the DSP-to-DAW pipeline** — the end-to-end signal path from converter to timeline, and
  the vocabulary that goes with it, drawn out properly for once. `private`
- **Drum recordings into an event stream** — local-first, multi-mic. No code until the architecture
  stops moving. `no code yet`
- **Reading up on the layers underneath** — networking and how the hardware actually answers.

Most of it lives in private repos; it is hobby work, and half of it is my own notes. The public
history below is older, from my AI and machine learning studies at IT-högskolan.

<details>
<summary><b>Older, and public</b> — archived coursework in machine learning and data, and some C</summary>

<br>

- [**Machine-learning**](https://github.com/Danneftw1/Machine-learning) — supervised learning, model
  selection, the usual scikit-learn suspects
- [**Deep-Learning**](https://github.com/Danneftw1/Deep-Learning) — neural networks, worked from the
  ground up
- [**Databehandling-Daniel-Nilsson**](https://github.com/Danneftw1/Databehandling-Daniel-Nilsson) —
  data wrangling and visualisation, including an Olympics dashboard
- [**Data-Engineering-Agila-Metoder**](https://github.com/Danneftw1/Data-Engineering-Agila-Metoder)
  — pipelines and Python in a group project
- [**Statistik**](https://github.com/Danneftw1/Statistik) and
  [**Linear-Algebra-Python**](https://github.com/Danneftw1/Linear-Algebra-Python) — the maths, by
  hand, in notebooks
- [**Python-Daniel-Nilsson**](https://github.com/Danneftw1/Python-Daniel-Nilsson) — fundamentals
- [**C**](https://github.com/Danneftw1/C) — a later detour, and some very C

</details>

---

<sub>This page is the demo. The artwork is generated: [`tools/build-assets.py`](tools/build-assets.py)
draws every asset — both themes, with and without motion — from one set of geometry and a palette it
contrast-checks before writing, and [`tools/check-readme.mjs`](tools/check-readme.mjs) renders this
README's own image blocks at 390, 430 and 896 px in both themes, plus the light-on-dark fallback the
mobile apps show, on every pull request ([`check.yml`](.github/workflows/check.yml)). No badge
services, no stats widgets, nothing that phones home.</sub>
