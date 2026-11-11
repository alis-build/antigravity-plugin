---
trigger: model_decision
description: "Alis Build service infrastructure. Read this before editing Terraform in a service infra/ folder under ~/alis.build, or before deploying a change to it."
---
# Alis Build — service infrastructure

Applies to Terraform under an Alis Build service's `infra/` folder (a path
under `~/alis.build/<org>/build/<product>`). Ignore this rule elsewhere.

- This Terraform is what Deploy applies. A change takes effect through
  `alis build <pkg> --json --deploy -e <env> --async`, or `alis deploy` for a
  version that is already built.
- Build runs from the latest pushed commit, never the working tree. Commit and
  push the change first, or the deploy will not contain it.
- The deployment environment comes from the product context, not a guess:
  `alis environment list <org>.<product> --json` gives the IDs and which ones
  are production.
- A production deploy is gated. Present the exact version and target for the
  user's explicit approval, and only then run it with `--confirm-production`.
- After a deploy, check its operation (`alis operations wait <op> --json`) and
  validate through the service's playground before calling it done.
