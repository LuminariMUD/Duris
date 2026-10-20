# Design

## Context

See proposal.md for motivation and the continuation plan for traced source facts.
Sorted room/prototype arrays and zone bounds already support bounded lookup.
Normal loaders and cleanup already own shared `index_data.desc2` strings.

## Goals / Non-Goals

Use existing ownership, paging, and ANSI formatting. Avoid a full prototype cache,
new index, general listing service, migrations, or global parser/pager changes.

## Decisions

- Read keywords with `skip_fread`, then the short description with `fread_string`
  during index generation. Preserve `pos`; stop before the sentinel. Existing
  loaders consume the same fields and reuse the pointer; empty strings stay null.
- Use a local scope/parser shared by three handlers. Public zone lookup is guarded
  against an empty table; decimal parsing rejects signs and overflow.
- Intersect room real bounds with VNUM lower bounds. Prototype zone bounds use
  the previous zone's top plus one through the selected zone's top.
- Probe only the 501st match, then print the remaining inclusive VNUM range using
  that match as its lower bound. For duplicate room VNUMs, add a checked
  `offset <count>` measured from that VNUM's lower bound within the selected
  room bounds. Track the group start during normal traversal and skip by direct
  pointer movement, including groups larger than 500. No saved continuation state,
  group scan or total count pass.
- Reuse ANSI formatting after bounding and flattening source text. Bound raw bytes
  as well as visible width so repeated color codes cannot exhaust the pager.

## Risks / Trade-offs

- Extra boot name memory/time -> measure on generated full and mini data; no extra
  per-instance ownership or command I/O.
- Binary lookup assumes sorted data -> verify actual generated indices/world and
  fixtures, matching existing runtime lookup requirements.
- Runtime world changes naturally affect populations -> prove inert handlers with
  executable fixtures and use existing diagnostics in an isolated local journey.

## Migration Plan

Two review chunks: boot names, then commands depending on it. Controlled restart
is needed when eventually deploying; deployment is outside this task. Leave the
change active until review/merge, and keep all acceptance evidence in the plan.
