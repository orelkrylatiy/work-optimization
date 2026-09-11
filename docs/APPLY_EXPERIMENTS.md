# A/B testing for HH applications

This project can run deterministic experiments for two independent parts of an HH application:

1. **cover letter** — for example AI-generated vs ordinary template;
2. **resume** — which published HH resume is attached to the application.

When both are enabled, the result is a factorial experiment (for two variants in each dimension: `2 x 2`). The runtime stores assignment facts in the local profile SQLite database and publishes only aggregate metrics to `ops/experiments.json`.

## Why assignment is deterministic

The experiment hashes:

```text
experiment name + seed + profile + dimension + vacancy id [+ resume id]
```

The same vacancy therefore receives the same variant on retries. Resume assignment is done **per vacancy**, so one experiment cannot intentionally send two resume variants to the same vacancy.

Never change weights, resume IDs or the meaning of an existing variant under the same experiment name. Start a new experiment name instead, for example `frontend_oct_v2`. Existing assignment conflicts fail closed.

## Configuration

Experiments are configured independently in every profile `config.json` under `apply_experiments`.

Example 50/50 cover-letter test plus 50/50 resume test:

```json
{
  "apply_experiments": {
    "enabled": true,
    "name": "frontend_sep_v1",
    "seed": "frontend-sep-v1",
    "cover_letters": {
      "variants": [
        {
          "id": "ai",
          "mode": "ai",
          "weight": 50
        },
        {
          "id": "plain",
          "mode": "template",
          "weight": 50
        }
      ]
    },
    "resumes": {
      "variants": [
        {
          "id": "resume_a",
          "resume_id": "PUT_HH_RESUME_ID_A_HERE",
          "weight": 50
        },
        {
          "id": "resume_b",
          "resume_id": "PUT_HH_RESUME_ID_B_HERE",
          "weight": 50
        }
      ]
    }
  }
}
```

Both resume IDs must refer to currently published resumes. Resume experiments are accepted only when `--search` is used. `similar_vacancies` is intentionally rejected because each resume would otherwise receive a different vacancy universe and the comparison would be confounded.

### Cover-letter variants

`mode` is either:

- `ai` — generate a contextual letter through `openai_cover_letter`;
- `template` — use the ordinary randomized cover-letter template without an LLM request.

An AI variant may optionally override its prompts:

```json
{
  "id": "ai_short",
  "mode": "ai",
  "weight": 50,
  "system_prompt": "@prompts/cover_letter_frontend.txt",
  "message_prompt": "Напиши очень короткое сопроводительное письмо"
}
```

A template variant may optionally provide its own spin-template:

```json
{
  "id": "plain_short",
  "mode": "template",
  "weight": 50,
  "template": "{Здравствуйте|Добрый день}. Прошу рассмотреть мое резюме на вакансию %(vacancy_name)s."
}
```

If no custom template is supplied, the operation uses the existing ordinary cover-letter template.

## LLM fallback

Cover-letter generation is fail-open by design. There are two protected failure points:

- if the AI provider is missing/misconfigured before the batch starts, `scripts/apply.sh` logs the failed preflight and continues;
- if the provider times out, rate-limits, returns an invalid response or otherwise raises an AI error for a particular vacancy, that vacancy receives the ordinary template instead.

For analysis we keep **intention-to-treat** assignment:

```text
assigned cover variant = ai
actual cover mode      = fallback_template
fallback_used          = true
```

The application stays in the `ai` experimental group. Moving it to the template group after a provider failure would bias the experiment. `actual_cover_modes` is reported separately so provider reliability can still be measured.

## Resume quotas

The legacy apply flow processes resumes sequentially and has one global `APPLY_LIMIT`. That would let the first resume consume the whole batch and invalidate the experiment.

The experiment-aware operation therefore splits `APPLY_LIMIT` across resume variants in proportion to configured weights. With a limit of 100 and two `50/50` variants, each resume gets a maximum of 50 successful applications in that run. Vacancies inside each quota are still selected by deterministic assignment.

If one resume cannot fill its quota, the unused quota is **not** automatically transferred to another variant. Preserving treatment weights is more important than maximizing the number of applications.

## What is persisted locally

The profile SQLite DB gets `apply_experiment_assignments`. It stores only experiment mechanics needed to reconnect an application to its later HH state:

- experiment name;
- vacancy ID;
- resume ID;
- resume variant;
- assigned cover-letter variant/mode;
- actual cover mode;
- whether fallback was used;
- send status and timestamps.

It does **not** store generated cover-letter text.

Later runs synchronize HH negotiations with `status=all`, allowing the assignment to be joined to the current negotiation state.

## Aggregate report

Run manually:

```bash
python3 scripts/ops/experiment_report.py
```

The cumulative report is written to:

```text
ops/experiments.json
```

It contains no vacancy IDs, resume IDs, employer names, vacancy titles or letter text. The report has four views for each experiment:

- `cover_letters` — intention-to-treat cover variants;
- `resumes` — resume variants;
- `cells` — factorial combinations such as `resume_a|ai`;
- `actual_cover_modes` — `ai`, `template`, `fallback_template`, etc.

For every group it records:

- assigned;
- successfully sent;
- send failures;
- fallback count;
- current `response` / `invitation` / `discard` / `hidden` counts;
- `invitation_rate = invitation / sent`;
- `decision_rate = (invitation + discard) / sent`;
- `invitation_given_decision = invitation / (invitation + discard)`.

`invitation_rate` is the primary simple business KPI. `invitation_given_decision` is useful as a secondary metric because many applications remain undecided for a long time.

The report is regenerated by the repository pre-commit hook, by the nightly container collector, and by `scripts/ops/daily_publish.sh`. Git history therefore gives snapshots of how results evolve over time.

## Recommended experiment discipline

Keep everything except the tested treatment as stable as practical: search query, exclusion filter, geography, seniority, send time and account/profile. Do not edit a running variant in-place; create a new experiment name.

A reasonable rollout is:

1. run dry-run first to validate configuration and assignment;
2. start live with a small quota and inspect `ops/experiments.json` plus fallback/error counters;
3. then keep the same experiment unchanged long enough to accumulate a meaningful number of outcomes.

Do not declare a winner from a handful of invitations. For early stages, inspect effect direction and operational failures; once sample sizes grow, calculate uncertainty/significance before making the winning variant the default.
