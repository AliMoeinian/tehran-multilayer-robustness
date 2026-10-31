# Original construction sources

These 13 files preserve selected original implementation bytes; hashes are in
`inventory.json`. They contain the actual extraction, backward/upward reference
completion, boundary assembly, road/building derivation, restriction audit,
route ordering, freezing and local v1.1 enrichment logic.

They are archival code, not a supported CLI. Paths refer to the original staged
`work/` and `outputs/` layout; some inputs are not distributed. In particular,
`build_candidate.py` uses earlier audit JSONs as selection/comparison context,
and `review_and_repair_transit.py`, `enrich_v11.py` and `finalize_v11.py` also use
the excluded historical reference or local evidence. Running them blindly may
overwrite stage outputs. The full pipeline is not claimed to rebuild from this
repository alone. Keep original byte-level code separate from future refactors.

The supported public-artifact commands are documented in `scripts/README.md`.
Local downloads, vendor libraries, browser/API probes, copied papers, unrelated
scratch scripts and redundant intermediate packagers are intentionally omitted.
