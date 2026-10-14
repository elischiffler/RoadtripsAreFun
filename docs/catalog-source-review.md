# Kaggle source assessment — 2026-10-14

No Kaggle archive was downloaded or imported. No new credentials, accounts or terms-acceptance actions were taken. No candidate is yet cleared for production import.

## Access evidence

Unauthenticated Python urllib requests to each URL returned `URLError: Tunnel connection failed: 403 Forbidden` from the environment proxy before reaching the origin:

- https://www.kaggle.com/api/v1/datasets/list?search=us%20museums&pageSize=10
- https://www.kaggle.com/api/v1/datasets/download/imls/museum-directory
- https://www.kaggle.com/api/v1/datasets/download/nationalparkservice/park-biodiversity
- https://www.imls.gov/research-evaluation/data/museum-data-files
- https://catalog.data.gov/api/3/action/package_search?q=Museum%20Universe%20Data%20File&rows=2

The web tool resolves the two Kaggle pages and their titles, but returns no metadata/body. API view/list URLs are also unavailable through web. Therefore exact archive bytes, current version/update time, column names and counts cannot be verified in this environment. This is not evidence that Kaggle itself requires authentication.

## Candidate 1: Biodiversity in National Parks

- Kaggle: https://www.kaggle.com/datasets/nationalparkservice/park-biodiversity
- Confirmed page title: Biodiversity in National Parks.
- Candidate rationale: US NPS-origin parks are a plausible bounded nature supplement. Inspect parks inventory, rather than importing species observations.
- Primary rights evidence: https://www.nps.gov/aboutus/disclaimer.htm (updated March 5, 2025), Ownership section: agency-created material is generally public domain unless otherwise indicated; third-party material and trademarks are excluded. Retain NPS credit and no-claim-to-original-US-government-works notice where applicable. This policy alone does not establish that every field of an unavailable Kaggle archive is agency-created.
- Required before acceptance: acquire archive plus metadata, verify originating NPS dataset/README and factual park-coordinate provenance; inspect actual coordinate column names, finite WGS84 values, source dates, closures and US jurisdictions. Do not import pictures or descriptions with independent rights.
- Size/count/coordinate schema: unverified, since archive and metadata inaccessible. Do not substitute remembered counts for measurements.
- Quality concern: park-level coordinates can be geographic centers with no road access, not entrances/visitor centers. Would need entrance/access-point evidence before use as driving stops. This cannot replace nationwide restaurants/evening venues.

## Candidate 2: Museums, Aquariums, and Zoos

- Kaggle: https://www.kaggle.com/datasets/imls/museum-directory
- Confirmed page title: Museums, Aquariums, and Zoos.
- Upstream: https://www.imls.gov/research-evaluation/data/museum-data-files. Search index identifies Museum Universe Data File releases FY2014 Q1, FY2015 Q1 and FY2015 Q3, with no planned update; actual content fetch blocked.
- Important upstream rights/quality finding: research partner Drexel's own publication https://drexel.edu/news/archive/2016/august/museumstat explicitly says MUDF combines public sources (including IRS) and proprietary location-aggregator data. Do not assume all coordinates are public domain just because a federal agency hosts the dataset. Need the actual IMLS distribution license/readme and contributor restrictions.
- Primary government presentation https://statspolicy.gov/assets/fcsm/files/docs/A-1FrehillFCSM2018toCOPAFS.pdf names source flags including Factual, IRS, association lists, agency records and private foundations. Describes geocode data and later duplicate removal/museum qualification work. This reinforces conservative quality review.
- Secondary observation (not used as acceptance evidence): a 2016 student analysis reports 33,072 rows/44 columns, including latitude/longitude. Exact Kaggle version/schema/bytes remain unverified.
- Likely useful cultural/niche supplement only after rights and current existence/location review. Historical nonprofit administrative records may include non-venues, duplicates and stale addresses.

## Wikidata alternative

https://www.wikidata.org/wiki/Wikidata:Licensing is clear primary evidence that structured data is CC0. Names, stable Q IDs and coordinate statements are a strong independent source for museums, landmarks and public art. This assessment did not identify and verify a particular Kaggle-hosted Wikidata US POI archive, so a direct Wikidata extraction must not be described as fulfilling the requested Kaggle ingestion. Retain Wikimedia provenance and avoid copying Wikipedia text/photos under the CC0 assumption.

## Concrete prerequisite

Permit ordinary outbound HTTPS to the public Kaggle API and any download redirect host it returns, or have the user supply the original public Kaggle archive and dataset metadata/license/readme. Then measure content and establish upstream rights before importer approval. Authentication setup, credential entry and any explicit agreement acceptance remain user actions if Kaggle actually requires them. Do not bypass the proxy or weaken source safeguards to manufacture an import.
