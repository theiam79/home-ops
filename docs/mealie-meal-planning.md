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
  Bootstrapped with `initdb` on first deploy; flipped to `recovery` after the
  first backup landed (#379, same convention as the other clusters).
- Auth: OIDC against Authelia. `OIDC_ADMIN_GROUP: admins` → LLDAP admins land as
  Mealie admins. `OIDC_AUTO_REDIRECT: false` keeps the local login form as
  break-glass. Optional: create an LLDAP group `mealie` and set
  `OIDC_USER_GROUP: mealie` to gate access.
- AI: `OPENAI_*` env vars point at Gemini's OpenAI-compat endpoint. Since
  Mealie v3.19 AI providers are managed **per group** in the UI (Group
  Settings → AI Providers — there is no admin site-settings page for this;
  upstream PR mealie-recipes/mealie#7650). The env vars are a deprecated
  import-only seed applied on upgrade — on a fresh install, configure the
  provider in the group settings: base URL
  `https://generativelanguage.googleapis.com/v1beta/openai/`, the Gemini API
  key, model `gemini-flash-latest`.

## Bitwarden entries (Step 0)

| Entry | Consumer |
|---|---|
| `MEALIE_CLIENT_SECRET_DIGEST` (pbkdf2 from `authelia crypto hash generate`) | Authelia config |
| `MEALIE_OIDC_CLIENT_SECRET` (plaintext of the same secret) | Mealie `mealie-secret` |
| `GEMINI_API_KEY` | Mealie AI provider; later HA Google Generative AI |

## Post-deploy manual steps (Mealie UI)

1. Log in at `https://recipes.${SECRET_DOMAIN}` via Authelia (admins-group user
   lands as admin).
2. Group Settings → AI Providers: configure/confirm the Gemini provider (see
   above); test with an AI recipe URL or image import.
3. Generate an API token for HA (Profile → Manage → API Tokens). A dedicated
   `homeassistant` user is optional — everything the integration touches is
   household-scoped, so a token from your own account sees the same data; a
   separate user only buys independent revocation and audit clarity.
4. Create one shopping list per store — `Costco`, `Hy-Vee`, `Target` — plus a
   `Weekly` catch-all. Each list surfaces in HA as its own `todo.*` entity and
   the planner routes items to the matching store list (no labels needed).
5. Recipe curation (drives planner quality): tag recipes with effort level
   (`weeknight`/`weekend`), `kid-friendly`, season; fill prep/total times.

## Home Assistant wiring (planner package)

Manual integrations (HA UI):

1. **Mealie**: URL `http://mealie.default.svc.cluster.local:9000` + the API
   token from above. Exposes meal-plan calendars (`calendar.mealie_dinner`…),
   shopping lists as `todo.*`, and `mealie.*` services.
2. **Google Calendar**: Google Cloud OAuth client (Calendar API enabled),
   device-auth flow per HA docs. Exposes family `calendar.*` entities.
3. **Google Generative AI**: same Gemini key; creates the `ai_task` entity —
   set it as preferred AI Task entity in Settings.

**UI-native build (no /config package).** The runtime lives in HA's UI
editors + helpers (scripts.yaml / automations.yaml, Kopia-backed), not a
package file. Deliberate choice: package-defined scripts are read-only in the
UI editors (no visual editing, awkward trace-driven tuning), HA's direction
has been UI-first for years, and the surrounding integrations are config-flow
only anyway — so `/config` + `.storage` backups, not git, are the durability
story here. Consequence: **the deployed copy in HA is the source of truth**;
[`mealie_meal_planner.yaml`](mealie_meal_planner.yaml) is the bootstrap
reference you paste in, and it will drift once you tune in the UI. Steps:

1. **Helpers** (Settings → Devices & Services → Helpers → Create Helper):
   - Number `Meal plan household size` → `input_number.meal_plan_household_size`
   - Text `Meal plan notes` → `input_text.meal_plan_notes` (free-text AI steering)
   - Text `Meal plan store preferences` → `input_text.meal_plan_store_prefs`
2. **The script** (Settings → Automations & Scenes → Scripts → Add → ⋮ → Edit
   in YAML): paste BLOCK 1, fill the `REPLACE_*` markers (including
   `REPLACE_ROSTER` — which calendar belongs to whom), save. Note its
   `entity_id`.
3. **The trigger** (optional): paste BLOCK 2 into a new Automation (Edit in
   YAML) for the Friday 16:00 run, or just add a dashboard button that calls
   the script.

What the single script does: gathers family calendars, weather, the Mealie
recipe catalog, and the last 14 days of plans (slimmed to the fields the model
needs) → `ai_task.generate_data` → normalizes Gemini's output and **validates
it, failing with a "planner failed" notification instead of a blank proposal**
(the v1 failure mode) → resolves each slug to a Mealie `recipe_id` → sends an
actionable notification showing per-day meals and inferred occupancy → **waits
in-script (`wait_for_trigger`)** for Approve/Redo so no template sensor is
needed → on Approve writes each day via `mealie.set_mealplan` and routes each
shopping item to its store's `todo.*` list; **Redo is a notification reply** —
the typed text ("no pasta twice") re-runs the script as steering feedback
alongside the rejected meals; a 4h timeout expires the proposal with a notice.
All notifications share `tag: meal_plan`, so each one replaces the last on the
phone — no stale Approve buttons. Trade-off of the in-script wait: a pending
approval is in-memory, so an HA restart during the 4h window drops it (the
recovery is just re-running the script).

Occupancy is read from the **primary calendars by event location + time**: an
event whose location is outside Kansas overlapping the 17:00–19:30 dinner window
means that person is away that night (multi-day out-of-state events span every
dinner); a local dinner-time event means home-but-busy → a quick meal. The
`meal_plan_notes` helper overrides it (e.g. *"Tyler away Wed–Sat"*). No
dedicated travel calendar needed.

Other prompt rules: catalog-only recipe selection (no invented meals, empty slug
only for leftovers / no-dinner); cook-once-eat-twice pairs; weather-aware; store
tagging from the prefs helper; no repeats from the last two weeks.

Where to find each `REPLACE_*` value (after the integrations exist):

| Marker | Where to find it |
|---|---|
| `REPLACE_MEALIE_CONFIG_ENTRY` | Settings → Devices & Services → Mealie → the `config_entry` ID in the page URL (or Download diagnostics → `entry_id`) |
| `REPLACE_CALENDAR_ENTITIES` | Developer Tools → States, filter `calendar.` — YAML list of the family calendars |
| `REPLACE_ROSTER` | one line mapping each calendar to a person, e.g. `calendar.tyler = Tyler; calendar.sarah = Sarah; kids always home` |
| `REPLACE_WEATHER_ENTITY` | Developer Tools → States, filter `weather.` (e.g. `weather.forecast_home`) |
| `REPLACE_AI_TASK_ENTITY` | Developer Tools → States, filter `ai_task.` (from Google Generative AI) |
| `REPLACE_TODO_COSTCO` / `_HYVEE` / `_TARGET` / `_DEFAULT` | Developer Tools → States, filter `todo.` — one entity per Mealie shopping list; `_DEFAULT` is the catch-all (Weekly) list |
| `REPLACE_NOTIFY_SERVICE` | Developer Tools → Actions, search `notify.mobile_app` |

Current live values (as of 2026-07, from the deployed v1):
`config_entry_id: 01KTT92DMS57Y883VF6RRNFJG7`;
calendars `[calendar.tyler, calendar.lauren, calendar.miles]`;
`weather.forecast_home`; `ai_task.google_ai_task`;
`todo.kitchen_mealie_costco` / `todo.kitchen_mealie_hy_vee` /
`todo.kitchen_mealie_target` / `todo.kitchen_mealie_weekly` (default);
`notify.mobile_app_pixel_10_pro_fold`.

**Migrating off v1**: the old package build is live at
`/config/packages/mealie_meal_planner.yaml` (blank-notification bug — Gemini's
JSON-wrapped output was never normalized, and it passed `recipe_slug` as
`recipe_id`). After the v2 script works, delete that file and restart HA;
that removes `sensor.proposed_meal_plan` and the three old
`meal_plan_*` automations with it.

## Verification

1. `flux get ks mealie-pg mealie -n default` Ready; `kubectl get cluster
   mealie-pg -n default` healthy; first `Backup` completes → raise the
   initdb→recovery PR.
2. ExternalSecrets `mealie`, `mealie-cnpg` (+ volsync) synced;
   `kubectl get replicationsource mealie -n default` syncing.
3. Gatus `recipes` green; Authelia SSO round-trip works; admin role applied.
4. AI recipe import works (exercises the Gemini path).
5. Before the first full run: call `mealie.get_recipes` in Developer Tools →
   Actions and confirm the recipe-id key is `recipe_id` (the script's slug
   resolution assumes it — v1 died on exactly this class of assumption).
6. Full planner run: run the script → notification lists 7 days each with
   meal + who's-home → tap Approve → plan visible in the Mealie calendar +
   items split across the per-store lists. Redo with a reply ("no pasta")
   produces a meaningfully different plan; an out-of-state calendar event over
   dinner correctly drops that person from that night's portions; and a forced
   failure (e.g. temporarily bad AI entity) produces a "planner failed"
   notification, not silence.

## Known risks

- Mealie image historically used root entrypoint + PUID/PGID; manifest runs it
  as `runAsNonRoot: 1000`. If it crash-loops on permissions, drop
  `runAsNonRoot` and set `PUID`/`PGID: "1000"` instead.
- Google deprecates models on the OpenAI-compat endpoint periodically
  (`gemini-2.5-flash` retires 2026-06-17). Use the `gemini-flash-latest`
  rolling alias — it tracks the newest stable Flash release (currently
  3.5) — both in the env seed and the in-app provider, which is the
  authoritative setting.

## Future phases (tracking issues)

- Self-hosted calendar layer (Davis + vdirsyncer CronJob) — aggregate family
  Google calendars locally; HA consumes via CalDAV.
- Rating feedback loop — post-dinner 👍/👎 notification → Mealie recipe rating →
  planner prompt learns tastes.
- Kitchen wall dashboard — meal-plan week view + family calendar + per-store
  lists.
- LiteLLM gateway — one OpenAI-compat endpoint fronting Gemini with Ollama
  (elli) fallback + spend tracking, once multiple apps consume LLMs.
