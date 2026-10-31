# Contributing

This repository is an early-stage complex-networks research project. Please
open an issue describing a bug, methodological concern or proposed change
before substantial work, and consult [TODO.md](TODO.md).

- Keep the frozen data archive immutable; propose a new version for data changes.
- Preserve OSM IDs, source dates, uncertainty flags and transformation provenance.
- Do not add external data, API responses, secrets, copyrighted PDFs or unlicensed datasets.
- Distinguish recorded geometry, model assumptions and observed operational facts.
- For analysis changes, include the configuration, random seed where applicable,
  a small meaningful validation and the affected research question.
- Avoid committing extracted data, environments, caches or generated experiment runs.

Check the bundled distribution with `python scripts/verify_dataset.py`.
Research experiments have not yet been implemented; do not report planned
tests or findings as completed results.
