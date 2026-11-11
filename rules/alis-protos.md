---
trigger: model_decision
description: "Alis Build protobuf contracts. Read this before editing or adding a .proto file under ~/alis.build, or before running Define."
---
# Alis Build — protobuf contracts

Applies to `.proto` files of an Alis Build service: those under
`~/alis.build/<org>/define`. Ignore this rule for protos anywhere else.

- The contract is edited in the build environment's `define` repo, not in the
  build repo. Generated code in the build repo is never edited by hand.
- A contract change is not live until Define runs. Commit and push, then
  `alis define <pkg> --json --install --async`. Define pins the contract to that
  exact pushed commit; unpushed edits are invisible to it.
- After Define, update the service's packages with `alis packages` before
  writing code against the change. Types that look stale mean the packages need
  updating. Use the generated stubs and typed APIs, never proto reflection.
- The Go import for package `<org>.<product>.<service>.<vN>` is
  `alis.build/<org>/<product>/<service>/<vN>`. Do not copy an
  `internal.<product>.<org>.services/protobuf/...` import from a neighbouring
  service: that is the deprecated product-level package.
- For anything beyond a small edit (a new service, Spanner or Pub/Sub
  artifacts, a migration), use the `alis-discover` skill first.
