# Alis Build Antigravity Plugin

<p align="center">
  <img src="assets/connectivity.svg" alt="Google Antigravity connected to Alis Build" width="760">
</p>

<p align="center">
  <strong>Connect Google Antigravity to Alis Build.</strong>
</p>

Use this plugin to let Google Antigravity work with Alis Build organisations, products, neurons, builds, and deploys through the `alis` CLI, with workspace-aware context injected before the model runs.

## What You Get

- A workspace-aware Define-Build-Deploy primer: the full guide on the first model invocation inside an `alis.build` workspace, a short refresher on later invocations, and just the refresher outside a workspace when `alis` is installed. No workspace and no CLI means no primer. Override with `ALIS_PRIMER=full|digest|off`.
- Package ids and pointers between a service's protobuf definitions and implementation, including when a mounted workspace is inside `infra/` or `.playground/`; multiple mounted workspaces are supported.
- Quiet, local-first discovery and capture skills: `alis-build-discover` activates on platform-shaped work (never on generic coding just because you are inside a workspace), probes the local catalog in ~40ms, and loads a registry skill only on a distinctive match; `alis-build-capture` turns just-completed work into a reusable team skill; `alis-build-getting-started` walks newcomers through their first Define-Build-Deploy cycle
- A quiet background catalog refresh on the first invocation, explicitly using `alis skills sync --cache-only --harness antigravity` for compatibility with older CLIs. The plugin never installs native user skills; the CLI may clean up retired sync-managed entries.
- A native tool hook that lets plain `alis …` commands run without a confirmation prompt on every call, while `--confirm-production` (the production deploy gate), `--approve`, and `alis blocks uninstall … --yes` always reach you for confirmation.

## Before You Start

You need:

- Google Antigravity installed (from [antigravity.google](https://antigravity.google))
- The [`alis` CLI](https://alis.build) installed, on your `PATH`, and signed in (`alis login`)
- Bash and `jq` on Antigravity's `PATH` (hooks return an empty JSON object if `jq` is missing)
- An Alis Build account with access to the organisations and products you want to use

## Install

Install the plugin:

```sh
agy plugin install https://github.com/alis-build/antigravity-plugin
```

Or copy manually:

```sh
git clone https://github.com/alis-build/antigravity-plugin
mkdir -p ~/.gemini/config/plugins
cp -R antigravity-plugin ~/.gemini/config/plugins/alis-build
```

Restart Antigravity after installing.

## Use It

Ask Antigravity to use Alis Build — just describe what you want:

```text
build it
```

```text
fix it
```

```text
Use Alis Build to list the organisations I can access.
```

```text
Show recent builds for product os in organisation alis.
```

```text
Review the latest deploy logs for this neuron and suggest the next action.
```

Antigravity will ask before running tools that require approval.

The plugin's `PreToolUse` hook auto-approves single, simple `alis ...` commands. Commands with shell expansion, chaining or redirection fall through to Antigravity's normal confirmation flow. Commands carrying `--confirm-production` or `--approve`, and `alis blocks uninstall … --yes`, return `force_ask`, which prompts even when permissions were previously cached. To restrict auto-approval, set `ALIS_ALLOWED_SUBCMDS` to a space-separated list (e.g. `ALIS_ALLOWED_SUBCMDS="define build deploy operations"`); unset means every subcommand.

## Skills

Discovery is skill-native: describe platform-shaped work in your own words and the `alis-build-discover` skill routes it — local catalog probe first, registry skill loaded only on a distinctive match, silence otherwise. Say "capture this as a skill" after solving something new and `alis-build-capture` saves it for your team.

## Hooks and primer sync

`context/dbd-primer.md` and `context/dbd-digest.md` are synced from the Claude Code plugin (`claude-plugin/plugins/alis-build/context/`, v0.21.3), with skill names adapted to `alis-build-discover` / `alis-build-capture`. Sync these files and the Gemini compatibility primer body together on each canonical primer release.

Antigravity uses a root-level `hooks.json` with named hooks, camelCase inputs and JSON outputs. Commands run relative to that file, so workspace detection uses `workspacePaths` from the payload. These contracts are described in the [Antigravity plugin guide](https://antigravity.google/docs/plugins/) and [hook reference](https://antigravity.google/docs/hooks).

| Claude behavior | Antigravity adaptation |
| --- | --- |
| `SessionStart` primer and service context | `PreInvocation` returns `injectSteps` with transient `ephemeralMessage` context. Invocation 0 gets the full workspace primer; later invocations get the digest. |
| Startup catalog refresh | First invocation launches `sync --cache-only --harness antigravity` with all streams detached. Unsupported flags fail quietly, with no fallback to a broader sync. |
| `UserPromptSubmit` skill suggestions | Native discovery/capture skills handle routing. The documented Antigravity payload has no submitted prompt, so the plugin does not parse private transcript formats or register an unsupported event. |
| `PreToolUse` on `Bash` | `PreToolUse` on `run_command` reads `toolCall.args.CommandLine` and returns `allow` or `force_ask`. |

Antigravity exposes invocation counters rather than Claude's startup/resume/compact source field. The primer follows those counters and refreshes transient context on every invocation. `ALIS_PRIMER=off` disables the DBD primer; service pointers and catalog refresh remain independent, as in the Claude plugin. No Claude permission-mode record is written: Antigravity does not supply that grant signal.

`gemini-extension.json`, `GEMINI.md`, and `policies/alis-cli.toml` remain for Gemini CLI compatibility. Gemini extension installs retain the standing full primer and shell policies; native Antigravity plugin installs use the root hook configuration above.

## Validation

```sh
bash tests/validate.sh
```

This checks manifests, shell syntax, primer consistency and native hook behavior with a fake CLI, including workspace gating, service paths, detached catalog refresh and permission boundaries. Tests do not contact Alis Build or modify installed skills.

## Troubleshooting

If the primer or skills do not take effect, confirm the plugin appears in Antigravity's Customizations page and restart it. For a manual global install, check `~/.gemini/config/plugins/alis-build/`. Confirm `jq` and `alis` are on the application's `PATH`, and that `ALIS_PRIMER` is not set to `off`.

If `alis` commands fail with an auth error, run `alis login` (or `alis authorise <org>.<product>` for git/package credentials) and retry.
