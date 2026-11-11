---
trigger: model_decision
description: "Alis Build playground. Read this before running, editing or searching for a service .playground/ folder under ~/alis.build."
---
# Alis Build — playground

Applies to a service's `.playground/` folder in an Alis Build workspace.

- The playground is the end-to-end check for a service after Deploy, usually
  `<service>/.playground/main_test.go`.
- `.playground` is hidden and git-ignored. `rg` and `git grep` skip it by
  default; a repo-wide search needs `rg --hidden --no-ignore` to include it.
- Because it is git-ignored, nothing here reaches a build: Build runs from a
  pushed commit.
