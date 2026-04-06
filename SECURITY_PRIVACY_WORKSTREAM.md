# Security / Privacy Workstream

## Scope
This document captures security and privacy hardening opportunities identified in the `cdflow-cli` codebase, with emphasis on OAuth flow design, token handling, callback listener exposure, logging, and network hygiene.

## Current Assessment
The CLI OAuth implementation is workable for a trusted operator environment, but it carries several avoidable risks and some non-best-practice patterns. The most important issues are:

1. the local OAuth callback listener binds to all interfaces instead of localhost
2. tokens are stored in process-global class variables for backward compatibility
3. access and refresh token suffixes are logged in several places
4. redirect URI generation is topology-coupled and defaults to insecure HTTP callback URLs
5. outbound API/token requests do not set explicit network timeouts

I do not see a fundamentally broken OAuth state check. State generation and validation exist and are materially better than having no CSRF protection. The sharper problems are exposure surface and token hygiene.

## Findings

### 1. High: OAuth callback listener binds to `0.0.0.0`
Relevant code:
- `cdflow_cli/adapters/nationbuilder/oauth.py:229`

Current behavior:
- `HTTPServer(("0.0.0.0", self.callback_port), CallbackHandler)` listens on all network interfaces.

Why this matters:
- for a CLI OAuth callback, the normal expectation is a loopback-only listener
- binding on all interfaces means other hosts on the LAN can reach the callback port while the auth window is open
- state validation reduces exploitability, but the exposed listener is still unnecessary attack surface

Recommended direction:
- bind to `127.0.0.1` by default for CLI callback handling
- only allow non-loopback bind as an explicit, opt-in advanced mode if there is a real operational reason

### 2. High: Tokens stored in process-global class variables
Relevant code:
- `cdflow_cli/adapters/nationbuilder/oauth.py:145-150`
- `cdflow_cli/adapters/nationbuilder/oauth.py:324-328`
- `cdflow_cli/adapters/nationbuilder/oauth.py:391-395`
- `cdflow_cli/adapters/nationbuilder/oauth.py:518-527`
- `cdflow_cli/services/auth_service.py:235-239`

Current behavior:
- `NationBuilderOAuth.nb_jwt_token`, `nb_refresh_token`, `nb_token_created_at`, and `nb_token_expires_in` are maintained as class variables for backward compatibility.
- API clients can fall back to these globals when no bound OAuth instance exists.

Why this matters:
- token state becomes shared process-wide rather than instance-scoped
- multiple auth contexts in one process can bleed into each other
- test and runtime isolation are weaker than they should be
- accidental use of stale or wrong tokens becomes easier

Recommended direction:
- remove class-variable token storage as the primary mechanism
- require instance-owned OAuth/token state everywhere
- keep any backward-compatibility shim short-lived and tightly isolated

### 3. Medium-High: Sensitive token material is partially logged
Relevant code:
- `cdflow_cli/adapters/nationbuilder/oauth.py:240`
- `cdflow_cli/adapters/nationbuilder/oauth.py:330-334`
- `cdflow_cli/adapters/nationbuilder/oauth.py:397-403`
- `cdflow_cli/adapters/nationbuilder/client.py:59-68`
- `cdflow_cli/services/import_service.py:152-155`
- `cdflow_cli/cli/commands_import.py:253-255`

Current behavior:
- logs include token suffixes and token lifetime metadata
- state prefix is also logged during OAuth initiation

Why this matters:
- suffix-only logging is better than full token logging, but it is still unnecessary token disclosure
- in aggregate, logs become more sensitive than they need to be
- log copies, crash bundles, and support artifacts inherit that sensitivity

Recommended direction:
- stop logging access-token and refresh-token suffixes entirely
- stop logging state fragments
- keep high-level auth lifecycle messages without embedding token-derived values

### 4. Medium: Redirect URI generation is topology-coupled and defaults to insecure HTTP
Relevant code:
- `cdflow_cli/utils/config.py:717-726`
- `cdflow_cli/services/rollback_service.py:60-77`
- `cdflow_cli/cli/commands_import.py:209-226`

Current behavior:
- if not explicitly provided, redirect URIs are synthesized as `http://{deployment.hostname}:{deployment.api_port}/callback`
- rollback and import commands also synthesize the same pattern when filling missing fields

Why this matters:
- the CLI callback model is being coupled to broader deployment topology
- it encourages non-loopback callback URIs when the CLI normally wants local loopback behavior
- it bakes in insecure HTTP by default
- it is easy to end up with misleading or over-broad callback exposure

Recommended direction:
- separate CLI callback configuration from application deployment topology
- default CLI callback URI to loopback-only, e.g. `http://127.0.0.1:<port>/callback`
- treat non-loopback callback hostnames as explicit operator overrides, not defaults

### 5. Medium: Outbound requests do not use explicit timeouts
Relevant code:
- `cdflow_cli/adapters/nationbuilder/oauth.py:313`
- `cdflow_cli/adapters/nationbuilder/oauth.py:380`
- representative API calls:
  - `cdflow_cli/adapters/nationbuilder/people_api.py:33`
  - `cdflow_cli/adapters/nationbuilder/donation_api.py:38`
  - `cdflow_cli/adapters/nationbuilder/signups_api.py:46`

Current behavior:
- `requests` calls do not specify `timeout=`

Why this matters:
- network hangs can block the CLI indefinitely
- auth and rollback/import workflows become harder to recover operationally
- in practice this is both reliability and security hygiene: hanging network calls reduce control over failure modes

Recommended direction:
- add explicit connect/read timeouts to all NationBuilder HTTP requests
- centralize timeout policy if possible

### 6. Medium: Callback parameter parsing is manual and brittle
Relevant code:
- `cdflow_cli/adapters/nationbuilder/oauth.py:118-127`

Current behavior:
- callback `code` and `state` are extracted via string splitting on `self.path`

Why this matters:
- works for the happy path, but is brittle compared with standard URL parsing
- easier to mis-handle encoding or unusual query-string shapes

Recommended direction:
- use `urllib.parse.urlparse` and `parse_qs`
- keep validation explicit and structured

### 7. Medium-Low: Callback listener returns success page before validating callback contents
Relevant code:
- `cdflow_cli/adapters/nationbuilder/oauth.py:111-116`
- `cdflow_cli/adapters/nationbuilder/oauth.py:265-268`

Current behavior:
- the callback handler immediately responds with a success page, then later the server-side flow validates `state`

Why this matters:
- user-facing behavior can say “Authentication Complete” even for invalid callback content
- this is mostly UX correctness, but it can mislead troubleshooting and incident response

Recommended direction:
- return a neutral processing page first, or tailor the response based on callback validity

## What Looks Acceptable
- secure random OAuth state generation exists: `cdflow_cli/adapters/nationbuilder/oauth.py:207-216`
- callback state validation exists: `cdflow_cli/adapters/nationbuilder/oauth.py:265-268`
- token state is held in memory rather than obviously persisted to disk in the inspected auth path
- CLI OAuth design is simpler than the app-side browser token handoff model, which avoids some web-specific token leakage issues

## Recommended Remediation Order

### Phase 1: Reduce exposure surface
1. Bind CLI callback listener to `127.0.0.1` by default
2. Decouple CLI callback host generation from deployment hostname
3. Remove token suffix and state-fragment logging

### Phase 2: Fix token-state architecture
1. Remove process-global class-variable token storage
2. Require instance-scoped OAuth state throughout API client usage
3. Eliminate class-token fallback in decorators and client setup

### Phase 3: Improve network and parsing hygiene
1. Add explicit `requests` timeouts everywhere
2. Replace manual callback query parsing with standard URL parsing
3. Improve callback success/error page behavior

## Target End State
The target CLI auth posture should be:
- loopback-only OAuth callback listener by default
- instance-scoped token ownership only
- no token-derived values in logs
- explicit, deterministic callback configuration for CLI use
- time-bounded outbound HTTP requests
- structured callback parsing and clearer auth UX
