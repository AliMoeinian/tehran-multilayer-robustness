# Provenance and publication boundary

## What supplied the public records

The **final primary OSM source was one Geofabrik Iran snapshot**. An initial
user-provided BBBike rectangle motivated the work and exposed extraction issues,
but the final context PBF was rebuilt from the national source; different OSM
vintages were not patched together in the final raw PBF.

| Source | Identity | Role |
|---|---|---|
| OpenStreetMap via Geofabrik Iran | Snapshot `2026-10-29T21:21:26Z` | All publicly bundled map records and geometry |
| OSM city relation 6663864 and 22 districts | Same snapshot | Study boundary and district labels; official legal equivalence unverified |
| Project-derived processing | Archived construction logic and documented rules | Building mask, membership/ordering audits, hospital screening and quality registries |

National source URL: https://download.geofabrik.de/asia/iran-latest.osm.pbf
(mutable; today's download is not guaranteed to reproduce the original snapshot).
Archived national source: 229,971,653 bytes; SHA-256
`9cac1960b89a1ac1f464412aa0d6ef6f0c02a1b745cb218ba23d37d8dcbc9f01`.
It was retrieved on 2026-10-30 between 13:17:53 and 13:22:56 UTC and is not bundled.

The extracted context PBF is 23,435,359 bytes; SHA-256
`f49737cb2ba86b783fc2b58ceda1534ae9e19bb24b678426d537dea3f742d7f5`.
This PBF is identical in the local parent and public distribution.

## Auxiliary source examined locally, not republished

Alireza Ahani's [Tehran Public Transport API article](https://alirezaahani.github.io/posts/tehran-public-transport-api.html)
led to a public historical [IranTracking reference](https://www.irantracking.com/ETAAPP/ANDROID/ECF2405141154.sqlite.gz).
It contains 474 route records, 4,759 stations and 9,511 route–station associations,
with an internal date of 2024-05-14. The downloaded gzip was 952,189 bytes, SHA-256
`1c4e34eafea77f90df78196c132c6d48d473a0e39846c34b1fc7800bf6149221`.
Retrieval time: `2026-10-30T13:52:05.338894Z`.

That reference supported local historical comparison and enrichment, not
certification of 2026 service. Public downloadability did not establish a
redistribution license. The SQLite, reference shapes/stops, record-level matching
outputs and historical map panel are therefore not published here. No license
is invented for them. The planned primary study uses only the 2026 OSM subset.

Hospital website checks were also auxiliary; their evidence fields and raw
responses are excluded from the public data. Website tags originally in OSM
remain part of the OSM source. No Google Maps, Neshan, Map.ir or Balad API output
is included. Other reviewed sources are described in the technical report and
must not be mistaken for contributors of bundled records.

## Local parent versus public archive

The technical report documents the **whole local preparation history**. Its
original v1.1 ZIP hash refers to that local mixed-source release, not this
public archive. This repository's `data/release.json` and `data/manifest.json`
are authoritative for the public artifact.

Public transformations are implemented in `scripts/build_public_dataset.py`:
explicit allowlist, three historical GeoPackage layer removals, deletion of
external hospital evidence fields, physical SQLite rebuild, and new manifest.
Only OSM-based records are retained; no gaps or transit links are invented.

## Reproducibility limits

The public archive can be verified and explored without the national snapshot
or historical reference. Selected original scripts are retained as an exact
source-code record in `provenance/source-scripts/`. These scripts used staged
workspace paths and some require local intermediate/historical files that are
not distributed; they are not advertised as a portable one-command rebuild.
Their inventory records hashes. Do not execute historical scripts against the
frozen data directory. See `scripts/README.md` for supported commands.

The screened research model, stop reconstruction, intact-network baseline and
observed single-closure experiments are now implemented. See the
[cumulative methods/results report](../research/reports/research-progress.en.md)
for their scope and remaining work.
File integrity, structural screening and real-world service validity are distinct.
