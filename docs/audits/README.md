# Audit evidence

- `local-v1.1-audit.json` and `final-review.fa.md`: the completed 17-group review
  of the original local mixed-source release. These are summary evidence, not
  the excluded historical records or a claim that the public package has 11 layers.
- `public-distribution-verification.json`: independent read-back of the **eight**
  retained public GeoPackage layers, geometry/attribute comparison with the parent,
  absence of historical tables, zero SQLite free pages and unchanged raw PBF.
- `../../data/release.json` identifies the actual public ZIP. Verify its member
  hashes and integrity using `python scripts/verify_dataset.py`.

No simulation results or completed travel-model validation are included.
