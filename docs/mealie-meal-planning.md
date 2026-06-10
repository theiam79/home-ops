# Mealie + AI meal planning — runbook

Goal: Mealie (recipe manager) in-cluster with Authelia SSO, AI recipe import via
Gemini, and a Home Assistant weekly-planner automation (`ai_task.generate_data`)
that considers who's home (Google Calendars), weather, and available time, then
writes the plan and a store-labeled shopping list back into Mealie.

Shopping happens at Costco / Hy-Vee / Target — none expose APIs, so lists live in
Mealie (PWA at the store). Costco is treated as a standing staples list;
meal-driven items go to Hy-Vee/Target.

## What this adds (PR 1)

| Change | File |
|---|---|
| Mealie (app-template, CNPG postgres, VolSync `/app/data`, external route) | `kubernetes/apps/default/mealie/` |
| Registered in namespace kustomization | `kubernetes/apps/default/kustomization.yaml` |
| Authelia OIDC client `mealie` (native OIDC, not forward-auth) | `kubernetes/apps/auth/authelia/app/resources/configuration.yml` |
| `MEALIE_CLIENT_SECRET_DIGEST` wired into authelia-secret | `kubernetes/apps/auth/authelia/app/externalsecret.yaml` |

- URL: `https://recipes.${SECRET_DOMAIN}` (envoy-external)
- DB: CNPG `mealie-pg` (2 instances, barman → `s3://cnpg/mealie/` on Garage).
  First deploy bootstraps with `initdb`; a follow-up PR flips to `recovery`
  after the first backup lands (same convention as the other clusters).
- Auth: OIDC against Authelia. `OIDC_ADMIN_GROUP: admins` → LLDAP admins land as
  Mealie admins. `OIDC_AUTO_REDIRECT: false` keeps the local login form as
  break-glass. Optional: create an LLDAP group `mealie` and set
  `OIDC_USER_GROUP: mealie` to gate access.
- AI: `OPENAI_*` env vars point at Gemini's OpenAI-compat endpoint. Since
  Mealie v3.19 these only **seed** the provider — manage/verify it afterwards in
  Admin → Settings → AI Providers.

## Bitwarden entries (Step 0)

| Entry | Consumer |
|---|---|
| `MEALIE_CLIENT_SECRET_DIGEST` (pbkdf2 from `authelia crypto hash generate`) | Authelia config |
| `MEALIE_OIDC_CLIENT_SECRET` (plaintext of the same secret) | Mealie `mealie-secret` |
| `GEMINI_API_KEY` | Mealie AI provider; later HA Google Generative AI |

## Post-deploy manual steps (Mealie UI)

1. Log in at `https://recipes.${SECRET_DOMAIN}` via Authelia (admins-group user
   lands as admin).
2. Admin → AI Providers: confirm the seeded Gemini provider; test with an AI
   recipe URL import.
3. Create a `homeassistant` user; generate an API token (profile → API tokens).
4. Create shopping list(s) and labels `Costco`, `Hy-Vee`, `Target`.
5. Recipe curation (drives planner quality): tag recipes with effort level
   (`weeknight`/`weekend`), `kid-friendly`, season; fill prep/total times.

## Home Assistant wiring (PR 3 — planner package)

Manual integrations (HA UI):

1. **Mealie**: URL `http://mealie.default.svc.cluster.local:9000` + the API
   token from above. Exposes meal-plan calendars (`calendar.mealie_dinner`…),
   shopping lists as `todo.*`, and `mealie.*` services.
2. **Google Calendar**: Google Cloud OAuth client (Calendar API enabled),
   device-auth flow per HA docs. Exposes family `calendar.*` entities.
3. **Google Generative AI**: same Gemini key; creates the `ai_task` entity —
   set it as preferred AI Task entity in Settings.

Planner package (`/config/packages/mealie_meal_planner.yaml`, via code-server —
prereq `homeassistant: packages: !include_dir_named packages`):

- `script.generate_weekly_meal_plan` — gathers calendar events (next 8 days),
  weather forecast, Mealie recipes (dinner-tagged), recent plans →
  `ai_task.generate_data` with a JSON schema
  `{days: [{date, meal, recipe_slug, note}], shopping_list: [{item, store}]}`.
  Prompt rules: busy evenings (events 17:00–20:00) get quick/slow-cooker/
  leftover meals; plan cook-once-eat-twice pairs; tag items by store.
- `sensor.proposed_meal_plan` — trigger-based template sensor holding the
  proposal for the approval flow.
- Approval automation — Friday 16:00: generate → actionable phone notification
  (Approve / Regenerate) → on approve, `mealie.set_mealplan` per day and
  `todo.add_item` per shopping item.

**→ Full package YAML lands with PR 3** (entity IDs and the Mealie
`config_entry_id` get filled in after the integrations above exist).

## Verification

1. `flux get ks mealie-pg mealie -n default` Ready; `kubectl get cluster
   mealie-pg -n default` healthy; first `Backup` completes → raise the
   initdb→recovery PR.
2. ExternalSecrets `mealie`, `mealie-cnpg` (+ volsync) synced;
   `kubectl get replicationsource mealie -n default` syncing.
3. Gatus `recipes` green; Authelia SSO round-trip works; admin role applied.
4. AI recipe import works (exercises the Gemini path).
5. (PR 3) `ai_task.generate_data` returns structured data; full planner run:
   script → phone approval → plan visible in Mealie calendar + items on list.

## Known risks

- Mealie image historically used root entrypoint + PUID/PGID; manifest runs it
  as `runAsNonRoot: 1000`. If it crash-loops on permissions, drop
  `runAsNonRoot` and set `PUID`/`PGID: "1000"` instead.
- `OPENAI_MODEL: gemini-2.5-flash` — Google deprecates models on the
  OpenAI-compat endpoint periodically; the in-app AI provider setting is
  authoritative after first boot.

## Future phases (tracking issues)

- Self-hosted calendar layer (Davis + vdirsyncer CronJob) — aggregate family
  Google calendars locally; HA consumes via CalDAV.
- Rating feedback loop — post-dinner 👍/👎 notification → Mealie recipe rating →
  planner prompt learns tastes.
- Kitchen wall dashboard — meal-plan week view + family calendar + per-store
  lists.
- LiteLLM gateway — one OpenAI-compat endpoint fronting Gemini with Ollama
  (elli) fallback + spend tracking, once multiple apps consume LLMs.
