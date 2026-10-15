# Roadside source follow-up — October 15, 2026

Dedicated Kaggle roadside intake remains **zero accepted destinations**. The
archive-rights investigation advanced; current visitor-access and practical
arrival-point evidence still prevents an import. The 400-record local evaluation
catalog and its immutable generation remain unchanged.

## Actual LOC archive statement located

The Kaggle v4 description links the original
[LOC rights statement](https://www.loc.gov/rr/print/res/723_marg.html). That URL
now redirects to the [LOC rights guide](https://guides.loc.gov/p-and-p-rights-and-restrictions/rights#723_marg.html).
The guide initially shows a loading placeholder: its published page script reads
[this public rights table](https://guides.loc.gov/ld.php?content_id=76336558).
Following that publisher-provided data reference required no account, API key or
alternate network route.

The retained table is **1,105,202 bytes / 689 statements**, SHA-256
`3c7ad29bc2ad742dc3b0b37145b71ce9b3aadeab19bbbdc359b2190a22b9f43c`.
Exactly one row matches the archive: ID `723_marg.html`, title **John Margolies
Roadside America Photograph Archive**, prepared by the Prints and Photographs
Division and last revised April 28, 2017. That row explains that LOC purchased
photograph intellectual-property rights with the archive and reports no known
copyright restrictions. It separately cautions about privacy/publicity rights
and copyright in depicted sculpture or artwork. This is the archive-specific
statement; the generic redirect alone did not establish it.

The table contains invalid UTF-8 in an unrelated record. Parsing preserved those
bytes with surrogate escapes; every field of the selected Margolies row passed
strict UTF-8 validation. No bytes were silently discarded or replaced. Original
bytes, page/data receipts and the selected statement are retained outside Git.
No photographs, depicted artwork or descriptive website prose are imported.
The mirror's CC0 metadata label is not relabeled as a blanket LOC CC0 grant.

## Current arrival review

The authentic Kaggle CSV contains historical leads for Teapot Dome (index 1),
Corn Palace (including index 279), Blue Whale (including index 2404), and Cabazon
Prehistoric Museum (including index 2450). Multiple photographs are not multiple
destinations. Titles/year/image references contain no arrival coordinates and do
not establish current operation or the current location of moved structures.

A bounded official Overture source inspection near Corn Palace read 135 source
features / 191,225 decoded bytes and matched two names. One is the gift shop,
which must not replace the attraction. The other is the venue at the published
physical street address, with source identity
`bb5dda13-ffd0-4791-8715-7b82aed55d42`, source open status and confidence about
0.920. Its source category is `stadium_arena`, outside the current conservative
admission taxonomy. The feature is retained as **review-only**, not relabeled or
staged to inflate the roadside count. No coordinates were guessed.

The official [Corn Palace visitor page](https://cornpalace.com/31/Visiting) and
[parking page](https://cornpalace.com/173/Parking) were readable through the web
tool and describe public visiting, a physical address and auto/RV parking. A
separate ordinary download returned 404 for those exact URLs, so current direct
page acquisition remains inconsistent. The City of Catoosa homepage names Blue
Whale but does not establish a place-specific operating schedule or driving
arrival. City-office hours must not be assigned to the attraction. The old
Zillah Teapot page returned 404. These observations do not clear a visitor
arrival or justify inventing one from a city/park centroid.

Before an explicit roadside adapter/import, retain consistent current official
visitor/arrival evidence, a legally admitted coordinate source and point role,
native source mappings, one canonical destination per surviving venue and the
appropriate separate notices. Validate actual driving arrival and deduplication
in isolated PostgreSQL. The [mixed-pilot evidence](catalog-mixed-pilot.md) and
production recovery/data gates remain in effect.
