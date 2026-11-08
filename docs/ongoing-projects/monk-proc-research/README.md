# Monk glove research evidence

Research date: 2026-11-08. This directory preserves the session's delivered candidate reports and the final valuation data alongside the two main documents.

## Main documents

- [Monk glove catalog](../monk-proc.md): authoritative corrected inventory, all 105 candidates in ascending native ivalue, full item details, acquisition sources, existing procs, and monk weight rules.
- [Monk glove proc plan](../monk-glove-proc-plan.md): proposed opt-in and reuse of the existing weapon-proc dispatcher, with attack coverage, balance considerations, and implementation checks.

## Evidence files

- [Candidate report](monk-glove-candidates.txt): original 105-entry report, grouped by selection evidence rather than ivalue.
- [Candidate metadata](monk-glove-candidates-data.json): machine-readable version of those 105 candidates.
- [Full hand-slot audit](monk-glove-full-audit.txt): original sweep of all 314 hand-slot prototypes, including items outside the selected scope.
- [Native ivalues](monk-glove-ivalues.json): final `itemvalue()` results and raw native callback credits for the 105 selected vnums.
- [Ordered vnums](monk-proc-ordered-vnums.json): those 105 vnums in ascending `(ivalue, vnum)` order, matching the catalog.

## Interpretation and provenance

The original reports describe checkout `5958a80f7`. The valuation catalog records its separate baseline, `77dcd194274eb7fe3737530a308395ee6f804a70`; its method used the runtime valuation functions in an isolated native harness. The framework plan records its own source baseline, `b9bcce5e1c0081d373382c0e9cd3f18d48832b84`. These are source research snapshots, not a live production inventory or proof that the proposed framework is implemented.

The full audit's original EXTRA FLAGS text has a decoder limitation: it collected constants across different flag families, including historical definitions, so some labels can be incorrect. The Markdown catalog corrected this with scoped flag definitions. Consult that catalog and the linked object records for authoritative flags and restrictions. The original audit is retained unchanged as research history, not as a competing corrected specification.

Temporary parsing caches, the superseded preliminary selection, and disposable compiled harnesses are not publication artifacts. The original source records remain in `areas/obj/`; the main catalog links each selected record. No gameplay effects were added by this research.
