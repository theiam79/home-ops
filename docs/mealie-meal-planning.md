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
4. Create shopping list(s) and labels `Costco`, `Hy-Vee`, `Target`.
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
package file — so it's maintainable directly in the UI with no edit-reload
loop. [`mealie_meal_planner.yaml`](mealie_meal_planner.yaml) is the reference
source you paste in. Steps:

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
recipe catalog, and the last 14 days of plans → `ai_task.generate_data` →
normalizes Gemini's output into clean lists → resolves each slug to a Mealie
`recipe_id` → sends an actionable notification → **waits in-script
(`wait_for_trigger`)** for Approve/Regenerate so no template sensor is needed →
on Approve writes each day via `mealie.set_mealplan` and each item via
`todo.add_item`; Regenerate loops; 12h timeout drops it.

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
| `REPLACE_SHOPPING_TODO` | Developer Tools → States, filter `todo.` — the Mealie shopping list entity |
| `REPLACE_NOTIFY_SERVICE` | Developer Tools → Actions, search `notify.mobile_app` |

## Verification

1. `flux get ks mealie-pg mealie -n default` Ready; `kubectl get cluster
   mealie-pg -n default` healthy; first `Backup` completes → raise the
   initdb→recovery PR.
2. ExternalSecrets `mealie`, `mealie-cnpg` (+ volsync) synced;
   `kubectl get replicationsource mealie -n default` syncing.
3. Gatus `recipes` green; Authelia SSO round-trip works; admin role applied.
4. AI recipe import works (exercises the Gemini path).
5. `ai_task.generate_data` returns structured data; full planner run: run the
   script → actionable notification → tap Approve → plan visible in Mealie
   calendar + items on the shopping list. Regenerate re-runs; an out-of-state
   calendar event over dinner correctly drops that person from that night's
   portions.

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
