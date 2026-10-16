# Creative and tests

## Review order: spend first

Run `scripts/decisions.py` first. Deep-review only ads marked `creative_review: deep` (spend at or above the client's floor), highest spend first. For `skip_low_spend` ads give one line at most; their numbers cannot support a creative read. Join each reviewed ad to its inspected media, full copy and destination; current media can differ from the reporting period.

## Per-creative checklist

Fill one row per reviewed ad. Observable facts only; mark anything inferred.

| Field | What to record |
|---|---|
| First frame / hook | What is seen and read in the first second (static: first thing noticed) |
| Format | static / video / carousel; native or designed; aspect ratio |
| Angle | The reason to buy it argues (use the ad-name angle when it follows `CLIENT_concept_angle_hook_vN`) |
| Offer | Price, discount, bundle, guarantee; visible or only in copy |
| Text overlay | Main on-image text, legible at phone size? |
| Product visibility | Seen clearly, when, and how it is used |
| CTA | On creative and button; matches the landing page? |
| Numbers | verdict + reason, spend, purchases, CPA, CTR; video hook and hold rate |

Then one sentence linking the weakest number to the visual cause, and the fix from the table below. Keep visual judgment separate from measured result; whole-ad success does not prove one element caused it.

## Numbers to fix

| Signal (vs. the ad-set median) | Reason code | Make next |
|---|---|---|
| Weak hook rate (3s views / impressions) or low CTR | `hook` | New first frame / hook; keep the angle |
| Good hook, weak hold (thruplays / 3s views) | `hold` | New body or angle; keep the hook |
| Good CTR, weak conversion | `post_click` | Fix landing page or offer congruence, not the ad |
| Healthy funnel, CPA still above target | `offer` | Test offer, price framing or bundle |
| Fatigue flag (frequency up, CTR down 20%+, CPA up) | — | Keep the angle, refresh execution |

For video use only hook and hold rate. For carousel, review every card in order. Opening-only or thumbnail-only inspection supports only that scope.

## Build the next test

Read the client's `tests.csv` first (template: `templates/tests.csv`) and do not repeat a dead idea. Test one level at a time: concept > angle > hook > execution. Winners (`scale`) get hook and format variants; good-hook losers get a new body; killed concepts stay killed.

Each proposal is one `tests.csv` row: date, ad_ids, angle, variable, hypothesis, kill/keep rule, result, learning. Propose rows; the user pastes them in. Never write the file automatically.

A brief states: the source ads and counts, the buying question, what the viewer must see or hear, the single changed variable and fixed controls, and the kill/keep rule (normally the verdict rules on the client config). A price overlay, new crop or old-ad retest is an execution variant, not a new concept. Generate assets only when requested.

Track concept, version and launched ad IDs separately; changed media never inherits the source ad's result. Record recurring production defects and their working fix in the existing feedback record.
