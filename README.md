# Meta Ads Analysis

An agent skill for reviewing Meta Ads results, investigating performance changes, inspecting creative and choosing useful next tests.

It works with an existing authorized connector or a supplied export. The included Python tools calculate and validate normalized data locally. They do not connect to Meta, inspect images, change campaigns or choose winners automatically.

## What it covers

- Account, campaign, ad-set and ad analysis, with an optional hard boundary around the entity requested.
- Native totals, parent/child reconciliation, weighted ratios and distinct missing/zero/suppressed states.
- Attribution, reporting dates, conversion maturity, delivery constraints and alternative explanations.
- Exact creative/copy/destination inspection, concept versus execution analysis and feasible tests.
- Optional lossless compact output, explicit field projections and arithmetic change decomposition.
- Reuse of dated sources and unchanged media, with further reads chosen by the decision they could change.

The entrypoint loads only the references needed for the current question. A metric lookup need not become a full audit or generated report.

## Install as a skill

Clone this public repository into your agent's skill directory. For a Codex setup that discovers user skills under `~/.agents/skills`:

```sh
git clone https://github.com/fortun8te/meta-ads-analysis.git ~/.agents/skills/meta-ads-analysis
```

If that destination already exists, inspect it before updating; do not overwrite a different skill. Restart or reload the agent if required by your client. Other clients can use the same `SKILL.md` and references in their supported skill directory. See the [Codex skill documentation](https://developers.openai.com/codex/skills) for discovery details.

Example requests:

- `Use $meta-ads-analysis to compare this campaign's last two complete weeks. What changed and what should we investigate next?`
- `Review these exact ads and results. Give me three distinct concepts to test, with a comparator and what each would teach us.`

No account connection, brand knowledge or credentials are included. Supply your own authorized data and project context. Creative review also needs actual accessible media, full copy and destination evidence.

## Local analysis tools

Requires Python 3.10 or newer; no third-party packages. Run from the repository root, or use absolute script/input paths from another directory:

```sh
python3 scripts/analyze_meta.py examples/campaign.json --mode metrics
python3 scripts/analysis_views.py examples/campaign.json --view compact
python3 scripts/analysis_views.py examples/campaign.json --view focus --fields metrics.spend,metrics.purchases,derived_metrics.purchase_roas
python3 scripts/analysis_views.py examples/change-drivers.json --view drivers
```

Every bundled example is synthetic. `campaign.json` demonstrates a requested campaign boundary, native/child reconciliation and missing purchase values. `change-drivers.json` demonstrates continuing ads, entering/exiting delivery and provisional CPM decomposition. These are independent fixtures for different synthetic campaign IDs; do not join them into one campaign trend. The examples are not benchmarks or advertising recommendations.

The input is a **normalized JSON packet**, not an arbitrary CSV or raw API response. Map source columns explicitly, preserve raw evidence separately, keep IDs as strings and supply source units/definitions. Coverage and finality flags are evidence assertions the tool cannot verify for you. See [input, outputs and guards](references/analysis-tool.md).

Tools print JSON. Optional analyzer `--out <new-directory>` writes `analysis.json`; existing outputs require explicit `--force` and path-safety checks. Output can retain input provenance and private fields: keep real input/results outside this repository. `scripts/review_pack.py` is a compatibility alias for the analyzer.

## Validate changes

```sh
python3 -m unittest discover -s tests -t . -v
```

Tests cover arithmetic, unavailable metrics, source compatibility, scope rejection before calculations, reconciliation, comparison/driver withholding, compact round trips, projections and file/CLI safety. GitHub Actions runs the same suite and bundled examples on supported Python versions.

[Behavioral evaluation cases](references/evaluation-cases.json) cover interpretation and research decisions. They are review prompts with rubrics, **not an automatically executed agent benchmark**. To evaluate an instruction change, run the skill on held-out prompts, retain actual answers/tool use and score against the rubric. Do not count unit tests or matching arithmetic as proof of better recommendations, reliable auto-invocation or improved live ROAS.

## Scope and limits

This is analysis and planning guidance. Publishing, budget changes, pausing, paid tools and external messages require the corresponding authorization. Observational results do not establish creative-feature effects, marginal scaling returns or incrementality. Meta-attributed value is not profit, unique store orders or new-customer revenue.

No private datasets, client assets, paid course transcripts or local account configuration are distributed. [Primary sources](references/sources.md) explain the methodological basis. Project knowledge stays in your existing private knowledge bank.

## Contributing

Keep changes focused. Use synthetic reproduction cases, preserve raw inputs and unknown states, update the relevant reference when behavior changes, and run the tests/examples. Do not submit access tokens, signed media links, account exports or customer data. Avoid dependencies or account-write capabilities unless a separately scoped feature actually needs them.

MIT licensed. No affiliation with or endorsement by Meta.
