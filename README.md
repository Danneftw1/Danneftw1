<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/header-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/header-light.svg">
  <img alt="Daniel Nilsson — LLM engineering, full-stack, Göteborg. A drum waveform crosses a playhead and comes out the other side as discrete token bars." src="assets/header-light.svg" width="100%">
</picture>

I build LLM pipelines and the products around them: prompt design, model orchestration, the
TypeScript and Python services that run them, and the Azure infrastructure underneath. Day job is
innovation developer at **Quokka** in Gothenburg, shipping AI features end to end.

Seventeen years behind a drum kit came first, and it turned out to be the same job. A signal moves
through stages, every stage has gain, and nothing is real until you meter it. Multi-mic drum
recording teaches phase, gain staging and signal flow; LLM work is that same discipline with tokens
where the transients were. That is the picture up there — analog in, tokens out.

## The chain

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/pipeline-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/pipeline-light.svg">
  <img alt="Five stages on a rail with a pulse travelling through them: prompt, orchestrate, serve, ship, observe." src="assets/pipeline-light.svg" width="100%">
</picture>

**Prompt** — multi-stage prompt design, structured output, content-filter and retry handling. Evals
before opinions.

**Orchestrate** — parallel model calls, fan-out and fan-in, and a sane answer when one stage fails.
`Azure OpenAI` · `AI Foundry` · `MCP`

**Serve** — React + Vite frontends, Express APIs, Python/Flask AI services, one pnpm monorepo.
`TypeScript` · `Python` · `React`

**Ship** — infrastructure as code and pipelines that do not need me awake. `Bicep` ·
`App Service` · `Cosmos DB` · `Key Vault` · `Entra External ID` · `GitHub Actions`

**Observe** — traces, evals and prompt iteration, because an LLM feature without a meter is a
rumour. `Langfuse`

## Now

- **Agent tooling I actually live in** — hooks, subagents and slash commands for Claude Code, kept
  under version control instead of hand-edited, with a plain-text ledger that records what each
  session changed.
- **A genealogy site where confidence is drawn, not labelled** — a sourced fact is full ink on a
  solid line, a hypothesis is pencil: thinner, paler, dashed. Nothing moves up a grade without a
  citation.
- **Drum recordings into an event stream** — local-first, multi-mic, still in research. No code
  until the architecture stops moving.
- **Reading up on the layers underneath** — networking, and how the hardware actually answers.

Most of it lives in private repos; it is hobby work, and half of it is my own notes. The public
history below is older, from my AI and machine learning studies at IT-högskolan.

<details>
<summary><b>Older, and public</b> — machine learning and data coursework, 2022–2024</summary>

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
- [**Python-Daniel-Nilsson**](https://github.com/Danneftw1/Python-Daniel-Nilsson) and
  [**C**](https://github.com/Danneftw1/C) — fundamentals, and some very C

</details>

---

<sub>The artwork on this page is generated: <code>tools/build-assets.py</code> draws both themes from
one set of geometry, and <code>tools/check-readme.mjs</code> redraws the page at 390 px to check that
a phone gets the good version too. No badge services, no stats widgets, nothing that phones home.</sub>
