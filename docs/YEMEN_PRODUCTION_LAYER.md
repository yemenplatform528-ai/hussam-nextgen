# Yemen Production Layer — Geography Ingestion Lock

## Decision

The Yemen Marketplace must consume the locked Yemen Foundation and Marketplace
layers. It must not embed a guessed or hand-maintained national geography list.

The next engineering unit therefore adds a **reviewed geography ingestion
boundary**. A source dataset is validated first, then imported transactionally
into `market_geographies` for market `YE`.

## Input contract

CSV columns:

`code,level,name,name_ar,parent_code,status,metadata_json`

Allowed levels:

`country → governorate → district → locality`

The importer fails closed when:

- required columns are missing;
- the dataset is empty;
- codes are duplicated;
- more than one country root exists;
- the country root is not Yemen-coded;
- a non-country node has no parent;
- a parent does not exist;
- a parent has the wrong hierarchy level;
- status or metadata JSON is invalid.

## Safety rules

- Default execution is **dry-run**.
- `--apply` is required for database mutation.
- Existing geography rows are matched by `(market_id, code)` and updated rather
  than duplicated.
- No payment, FX, provider credential, logistics, or political/administrative
  assumption is inferred by the importer.
- The exact reviewed artifact must be fingerprinted with SHA-256. The source,
  license, retrieval timestamp, and artifact hash are recorded in `metadata_json`
  before production import.

## Source policy

A national dataset must be externally sourced and reviewed before import. The
platform does not manufacture district/locality names or boundaries. A suitable
candidate source is an authoritative humanitarian/open-data administrative
boundary dataset; source suitability and licensing must be reviewed before the
specific dataset is admitted to production.

## Execution

```text
python scripts/yemen_geography_import.py <reviewed.csv>
python scripts/yemen_geography_import.py <reviewed.csv> --apply --database-url <DATABASE_URL> \
  --source-name "<provider/dataset>" --source-uri "<canonical-source-uri>" \
  --license "<license>" --retrieved-at "<UTC timestamp>" --source-sha256 "<sha256>"
```

The first command is the mandatory validation/dry-run. The second is the
explicit production mutation step.

## Boundary

This lock does not claim that a national Yemen geography dataset has already
been imported. It establishes the safe path for doing so without fabricating
Yemen data.
