---
trigger: model_decision
description: "Alis Build dependency pins. Read this before editing go.mod, go.sum or package.json under ~/alis.build, or when go mod tidy or a package install fails there."
---
# Alis Build — dependency pins

Applies to dependency manifests inside an Alis Build workspace (a path under
`~/alis.build`). Ignore this rule elsewhere.

- Never hand-edit pins for Alis-defined packages, and never assemble `GOPROXY`
  or registry settings by hand. That is the main reason `go mod tidy` and
  `pnpm install` fail here.
- `alis packages install <pkg> --language go --json` (or the relevant language)
  refreshes registry credentials and runs the right package manager.
  `alis packages upgrade` bumps Alis-defined dependencies (`--all` for every
  module, `--to <version>` to pin).
- Installing fetches the service's latest definition; pass
  `--version <version>` to keep a specific one.
- If a download still fails, read the actual error and run `alis doctor --json`.
  Never bypass a TLS failure or edit stored credentials.
