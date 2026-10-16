"""Replay a second, bounded review of admitted NPS facility schedules.

Only immutable reviewed bodies are supported. Native clocks, dated selectors and
all parent/component facts are read again; rows and coordinates are preserved.
The acquisition-year date range is an extraction scope, never a published source
expiry or an assertion that the source guarantees every future visit. Unknown
individual dates are omitted, with reasons, and no weekly fallback is emitted.

Confined standalone evidence replay requires POSIX directory descriptors and
NOFOLLOW (Linux is supported). Unsupported platforms fail with CalendarHold;
the evidence filenames and serialized artifacts remain Windows-safe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path, PureWindowsPath

from app.catalog.nps_visit_calendar import (
    SCHEMA,
    CalendarHold,
    _clock,
    _day_windows,
    _exception_applies,
    _fact,
    _holiday,
    _intersect,
)

TRANSFORMATION = "roadtrips-reviewed-nps-facility-calendar-more/1"
MAX_SOURCE_ROWS = 50_000
MAX_SOURCE_BYTES = 100 * 1024 * 1024


class EvidenceBoundaryError(CalendarHold):
    """Abort an invocation that violates a source path or resource boundary."""


def _confined_reads_supported():
    return (
        os.name == "posix"
        and all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"))
        and {os.open, os.stat} <= os.supports_dir_fd
    )


class _EvidenceReader:
    """One bounded offline invocation; no shared cache or aggregate counters."""

    def __init__(self, evidence_root=None, *, allow_private_absolute=False):
        if not _confined_reads_supported():
            raise EvidenceBoundaryError(
                "Confined offline evidence replay requires POSIX directory descriptors and NOFOLLOW; run standalone replay on Linux"
            )
        if evidence_root is None and not allow_private_absolute:
            raise EvidenceBoundaryError(
                "An evidence root is required; absolute fixtures need explicit private offline mode"
            )
        self.root = Path(evidence_root).resolve(strict=True) if evidence_root else None
        if self.root is not None and not self.root.is_dir():
            raise EvidenceBoundaryError("Evidence root must be a directory")
        self.allow_private_absolute = allow_private_absolute
        self.total_bytes = 0
        self._files = {}

    @staticmethod
    def _relative(value):
        if not isinstance(value, str) or not value or "\\" in value:
            raise EvidenceBoundaryError("Evidence path must be a portable relative path")
        windows = PureWindowsPath(value)
        parts = value.split("/")
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10))
        if (
            windows.drive
            or windows.root
            or Path(value).is_absolute()
            or any(
                part in ("", ".", "..")
                or part.endswith((" ", "."))
                or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                or part.split(".", 1)[0].upper() in reserved
                for part in parts
            )
        ):
            raise EvidenceBoundaryError("Evidence path must be a portable relative path")
        return parts

    @staticmethod
    def _stamp(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    def _read(self, base, parts):
        # Resolve each source-controlled directory relative to an already opened
        # directory descriptor. NOFOLLOW also rejects symlink swaps between the
        # lexical check and open, including intermediate-directory escapes.
        try:
            directory = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError as exc:
            raise EvidenceBoundaryError(
                "Evidence directory is missing, unsafe, or inaccessible"
            ) from exc
        descriptor = None
        try:
            for part in parts[:-1]:
                next_directory = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                os.close(directory)
                directory = next_directory
            before = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise EvidenceBoundaryError("Evidence must be a regular file without symlinks")
            if not 0 < before.st_size <= MAX_SOURCE_BYTES:
                raise EvidenceBoundaryError(
                    "Source body exceeds the unchanged 100MiB limit or is empty"
                )
            identity = (before.st_dev, before.st_ino)
            cached = self._files.get(identity)
            if cached is not None:
                if cached[0] != self._stamp(before):
                    raise EvidenceBoundaryError("Evidence file changed during the invocation")
                return cached[1]
            if self.total_bytes + before.st_size > MAX_SOURCE_BYTES:
                raise EvidenceBoundaryError(
                    "Aggregate unique-file source bytes exceed the unchanged 100MiB limit"
                )
            descriptor = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            if self._stamp(os.fstat(descriptor)) != self._stamp(before):
                raise EvidenceBoundaryError("Evidence file changed before reading")
            # Reserve the stat-proven size even if later hash/JSON validation
            # rejects this body. Rejected source reads still consume the budget.
            self.total_bytes += before.st_size
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                body = stream.read(before.st_size + 1)
                after = os.fstat(stream.fileno())
            if len(body) != before.st_size or self._stamp(after) != self._stamp(before):
                raise EvidenceBoundaryError("Evidence file changed while reading")
            self._files[identity] = (self._stamp(before), body)
            return body
        except OSError as exc:
            raise EvidenceBoundaryError(
                "Evidence file is missing, unsafe, or inaccessible"
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(directory)

    def read(self, value):
        if self.root is not None:
            parts = self._relative(value)
            return self.root.joinpath(*parts), self._read(self.root, parts)
        path = Path(value)
        if not self.allow_private_absolute or not path.is_absolute():
            raise EvidenceBoundaryError("Private offline fixtures require explicit absolute paths")
        # This opt-in helper is for existing private fixture files. Portable
        # replay must supply a root instead and cannot enable this escape hatch.
        path = path.resolve(strict=True)
        return path, self._read(Path(path.anchor), path.parts[1:])

    def read_control(self, value):
        """Explicit CLI JSON operands share the same pre-read/aggregate budget."""
        path = Path(value).resolve(strict=True)
        return self._read(Path(path.anchor), path.parts[1:])


def _validate_inputs(extraction, catalog_items):
    records = extraction.get("records") if isinstance(extraction, dict) else None
    if not isinstance(records, list) or not 0 < len(records) <= MAX_SOURCE_ROWS:
        raise EvidenceBoundaryError("Extraction requires 1..50000 source records")
    if not isinstance(catalog_items, list) or not 0 < len(catalog_items) <= MAX_SOURCE_ROWS:
        raise EvidenceBoundaryError("Parent requires 1..50000 catalog records")
    # Check lengths above before iterating either potentially hostile list.
    if any(
        not isinstance(record, dict) or not isinstance(record.get("catalog_source_id"), str)
        for record in records
    ):
        raise EvidenceBoundaryError("Extraction records require native source identities")
    if any(
        not isinstance(row, dict) or not isinstance(row.get("source_id"), str)
        for row in catalog_items
    ):
        raise EvidenceBoundaryError("Parent records require admitted source identities")
    return records


# All source prose, exceptions and component scopes are pinned by these full-body
# hashes. These profiles are intentionally separate from the frozen first batch.
PROFILES = {
    "nps:mora": {
        "sha256": "f77b484bc884c3891d5b3b534cf6848a6091d92d7afef12395f6e221e0b318ff",
        "checked_at": "2026-10-15T00:11:55.762947+00:00",
        "facility_id": 1270,
        "schedule_id": 1606,
        "full": [1489, 1505],
        "closed_holidays": [],
        "review": "Nisqually and general access apply to Longmire. Carbon River bridge, White River, Paradise and seasonal wilderness desks are other locations/components. The retained official Longmire page locates nightly closure on the road FROM Longmire TO Paradise. Museum lunch split applies to every visit.",
    },
    "nps:pefo": {
        "sha256": "e408cff451489b73850c8badced69b5c9d9b66c54842b89481c0891b6f4f6cae",
        "checked_at": "2026-10-15T00:11:55.931250+00:00",
        "facility_id": 1281,
        "schedule_id": 1630,
        "full": [18053],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day"],
        "review": "Park road 08:00–17:00 applies. Whole-park Thanksgiving/Christmas negatives duplicated in other visitor center records are retained; selected museum and applied park road carry both closures.",
    },
    "nps:seki": {
        "sha256": "b1670d05192e5b5787809047980838224ce5f966d36e1c8d065261fddd6e232f",
        "checked_at": "2026-10-15T00:11:56.196980+00:00",
        "facility_id": 191,
        "schedule_id": 400,
        "full": [252],
        "closed_holidays": [],
        "review": "Selected museum has exact Oct13–Jan3 fall/early winter table; other museums, permit stations and campground closures are separately scoped. General park all-day access does not widen museum.",
    },
    "nps:zion": {
        "sha256": "bdef7fc32aab48af8fecd07732a54cb8538273fe2ea16fb55ff6e7949ddd6f65",
        "checked_at": "2026-10-15T00:11:56.742309+00:00",
        "facility_id": 5847,
        "schedule_id": 20665,
        "full": [2709],
        "closed_holidays": [],
        "review": "Museum has exact fall Sep13–Nov28 10:00–17:00 and Nov29–Mar8 winter closure. Kolob lunch is a different visitor center.",
    },
    "nps-heritage:ande": {
        "sha256": "c8992ad11d7021e835b06155d5b27c5fc122bf169c5bd5d3943041c83bc24643",
        "checked_at": "2026-10-15T02:31:32.744264+00:00",
        "facility_id": 2568,
        "schedule_id": 3491,
        "full": [3487],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:efmo": {
        "sha256": "c4afcb39816f899180fa416e0287466607ecfc66ac811842b33ad9a479d322e4",
        "checked_at": "2026-10-15T02:31:33.008690+00:00",
        "facility_id": 136,
        "schedule_id": 286,
        "full": [],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Parent explicitly describes trails dawn–dusk; it does not establish visitor-center clocks or gate access. Selected facility is explicitly year-round except named holidays.",
    },
    "nps-heritage:crmo": {
        "sha256": "f5a5cfe4b434d81f965229e3b6c389b32ee59bd65e0d8e0304ff8215fa4afdbf",
        "checked_at": "2026-10-15T02:31:33.035006+00:00",
        "facility_id": 1265,
        "schedule_id": 1599,
        "full": [1591],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Loop Road and Lava Flow campground seasonal closures are a different activity; selected visitor center has explicit Nov 30–Jan28 winter closure.",
    },
    "nps-heritage:agfo": {
        "sha256": "fe654eddc9a8cc3cc78e789ab6f45e70c1353f8fb550dbbb2df0c1aca1da7f6e",
        "checked_at": "2026-10-15T02:31:34.202478+00:00",
        "facility_id": 104,
        "schedule_id": 247,
        "full": [],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Parent schedule explicitly names Trails, separate from selected year-round visitor center. Winter actual selected clocks narrow to 09:00–16:00 after intersection with base.",
    },
    "nps-heritage:chir": {
        "sha256": "f7529df8f50c31d8aa86d86879ee312221fb57e9b02b7732b65dde5398c48699",
        "checked_at": "2026-10-15T03:15:54.019790+00:00",
        "facility_id": 2445,
        "schedule_id": 3102,
        "full": [3097],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:colm": {
        "sha256": "fb3a745fbc32110b4a1f7c21fdd76768f8c890544303e79e3ec8a45bd92a4cf4",
        "checked_at": "2026-10-15T03:15:54.241487+00:00",
        "facility_id": 2437,
        "schedule_id": 3068,
        "full": [3055],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:dino": {
        "sha256": "fb4ff3178e46139d49a26725326360873a0e31d6a90842f70c6daa3313512e72",
        "checked_at": "2026-10-15T03:15:54.498310+00:00",
        "facility_id": 25,
        "schedule_id": 66,
        "full": [70],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:elma": {
        "sha256": "b14021417cb950ad18ee2607f16e24bab4412567cd8fee2775c7d36e7a78721a",
        "checked_at": "2026-10-15T03:15:54.611289+00:00",
        "facility_id": 1310,
        "schedule_id": 21213,
        "full": [1685],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:nabr": {
        "sha256": "4c2b635d302ab33c539d6154f255d59d3a98fb1efaef16ec073d162ebed1cf96",
        "checked_at": "2026-10-15T03:15:57.617988+00:00",
        "facility_id": 2493,
        "schedule_id": 3254,
        "full": [2705],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected facility prose says off-season fall/winter/early spring Friday–Monday and 09:00–16:00; apply this narrower subset throughout Oct 15–Dec 31, including before table Nov 1.",
    },
    "nps-heritage:orpi": {
        "sha256": "d149f45599fe48839e7262cc4c17761a5d7824c02f1e3e8c414368a7028d1e03",
        "checked_at": "2026-10-15T03:15:57.971504+00:00",
        "facility_id": 2312,
        "schedule_id": 2690,
        "full": [2689],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:peco": {
        "sha256": "87fe29bf6bc9cae73f4be24f460a011200d6f1ed34d222c9df90b1e271f7bc79",
        "checked_at": "2026-10-15T03:15:58.078550+00:00",
        "facility_id": 1304,
        "schedule_id": 1674,
        "full": [21350],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:pisp": {
        "sha256": "0883f64232e24880aa3590a8f79a1ebc61790aa3d170627717052cc5650ae873",
        "checked_at": "2026-10-15T03:15:58.197677+00:00",
        "facility_id": 2549,
        "schedule_id": 3394,
        "full": [2764],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected 08:30–16:30 is contained in both literal summer 08:00–17:00 and winter 08:30–16:30 variants; parent explicitly supplies same narrower clocks. No mid-month date guessed.",
    },
    "nps-heritage:sucr": {
        "sha256": "1c6842df4503a8da043732309ca53d60f06348d291cf23e508d65a08bf98be4b",
        "checked_at": "2026-10-15T03:15:59.039810+00:00",
        "facility_id": 1306,
        "schedule_id": 1678,
        "full": [1676],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:tont": {
        "sha256": "894ade1b5d46ca4f01c6a19a907716f3429d4e52211724e627e9c0f1745f019e",
        "checked_at": "2026-10-15T03:15:59.207337+00:00",
        "facility_id": 2516,
        "schedule_id": 3287,
        "full": [3005],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Summer exception explicitly refers 2025 but ends Oct 1, wholly before this acquisition-year evaluation. No summer-year reuse. Parent Christmas/NewYearEve 13:45 is stricter than selected 14:00; cap at13:45. Lower-cliff hike cutoffs are separate activity.",
    },
    "nps-heritage:tuma": {
        "sha256": "22cf93a559acac42544f36d28b34a869785e6e67cc385645d1e883790a0d4d73",
        "checked_at": "2026-10-15T03:15:59.331936+00:00",
        "facility_id": 91,
        "schedule_id": 200,
        "full": [199],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:tuzi": {
        "sha256": "56b60b7c49b76f16c6f694e666537eadf9dbb4d75955115a9459893392cf4618",
        "checked_at": "2026-10-15T03:15:59.395491+00:00",
        "facility_id": 1309,
        "schedule_id": 21230,
        "full": [1681],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:cabr": {
        "sha256": "fd6a93c4e80d07cffa0987762b4cc84619dfe60c2e224fea63e5c4877bb0e7d0",
        "checked_at": "2026-10-15T03:15:53.488206+00:00",
        "facility_id": 1234,
        "schedule_id": 1502,
        "full": [1501],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:joda": {
        "sha256": "3fa9619c5f465723263c35a2d24d43964bb1b41e5dcfb251947d99c2ad44948c",
        "checked_at": "2026-10-15T03:15:56.557133+00:00",
        "facility_id": 2491,
        "schedule_id": 3251,
        "full": [17948],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:labe": {
        "sha256": "07b7147e0dd848d9da091ef640ecabf78d99693faff2dce94be755c2ff9cde01",
        "checked_at": "2026-10-15T03:15:56.916537+00:00",
        "facility_id": 2428,
        "schedule_id": 3022,
        "full": [21313],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:deto": {
        "sha256": "96be16eb046c2abd5e4ff25cb51f3c02dd122a5f8afe47395a9fe153c008ab68",
        "checked_at": "2026-10-15T03:15:54.490070+00:00",
        "facility_id": 2396,
        "schedule_id": 20902,
        "full": [18213],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:grko": {
        "sha256": "f4580b6fc4c29531cf273e14fb3b197af4071b5fa9aee17e86d7b562030c614c",
        "checked_at": "2026-10-15T03:15:55.863501+00:00",
        "facility_id": 2336,
        "schedule_id": 2736,
        "full": [2732],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:grpo": {
        "sha256": "87b6349dc50d31e0d14532eec752871339f8e4f386b647971009c78bc947828d",
        "checked_at": "2026-10-15T03:15:55.905775+00:00",
        "facility_id": 5810,
        "schedule_id": 19366,
        "full": [21809],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Heritage Center is distinct from Historic Depot, closed after Oct 12. Native 2026–27 winter table supplies Sunday/federal holiday negatives; finite scope stops2026.",
    },
    "nps-heritage:heho": {
        "sha256": "9e56089ae413c44f5371f2429dd1ae6a2a769c3742d27e46de74c4bd525e315f",
        "checked_at": "2026-10-15T03:15:56.132573+00:00",
        "facility_id": 36,
        "schedule_id": 88,
        "full": [82],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Visitor center winter native table17:00 conflicts with literal16:30 prose and applied parent winter16:30 table. Conservative end16:30 wins Nov 1 onward.22:00–06:00 road/parking restriction cannot intersect daytime session.",
    },
    "nps-heritage:pipe": {
        "sha256": "c6d82c1d036e431ed5d718c118616ff023c4761170c217efd49fb2f552cc8040",
        "checked_at": "2026-10-15T03:15:58.168600+00:00",
        "facility_id": 5792,
        "schedule_id": 20519,
        "full": [116],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Native off-season table startsNov 30 but its literal description says Sundays/Mondays closed November–April. Apply earlierNov 1 weekday closure; no widening on contradictory dates.",
    },
    "nps-heritage:scbl": {
        "sha256": "d90c2cc29b21741d024a6bec10691a487e2edca2394abccf59cbfa8db3980a72",
        "checked_at": "2026-10-15T03:15:58.793561+00:00",
        "facility_id": 70,
        "schedule_id": 163,
        "full": [],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Parent explicitly states its sunrise/sunset clocks are grounds/picnic/trails only and VC/SummitRoad hours differ. Summit road is optional summit activity, not visitor-center entrance.",
    },
    "nps-heritage:ulsg": {
        "sha256": "3a444930bc5c331c2b7da520da7f59b13f644c96d1b185d089951be7a210f529",
        "checked_at": "2026-10-15T03:15:59.396227+00:00",
        "facility_id": 2429,
        "schedule_id": 3025,
        "full": [3023],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:abli": {
        "sha256": "ff3fee807b18ec681f84624a1b85c3339a7d34ed572cd41c1ff9a19f2483be91",
        "checked_at": "2026-10-15T03:15:52.599973+00:00",
        "facility_id": 5710,
        "schedule_id": 17954,
        "full": [114],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:anjo": {
        "sha256": "4081b658ad57b623d8c87bc6ddfa02fdb0bc4326abe9ae28dfc7dde03bbc06b3",
        "checked_at": "2026-10-15T03:15:52.835639+00:00",
        "facility_id": 66,
        "schedule_id": 150,
        "full": [3563],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Parent prose winter/spring Wednesday–Sunday conflicts with daily table and has no seasonal boundaries. Constrain entire finite scope to Wednesday–Sunday; retain homestead tours separately.",
    },
    "nps-heritage:chsc": {
        "sha256": "77c4e752dc614030237c43a8f54f2daebeec1a86f5df42e43f93645ca8d93091",
        "checked_at": "2026-10-15T03:15:54.138114+00:00",
        "facility_id": 1245,
        "schedule_id": 1561,
        "full": [1560],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:guco": {
        "sha256": "1959c8f2b3fe459aabe475eae25a75716c63aeb9d6693c2f8b56d7273259d83c",
        "checked_at": "2026-10-15T03:15:55.914740+00:00",
        "facility_id": 2571,
        "schedule_id": 3500,
        "full": [17982],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Monday/Tuesday holiday special openings do not override selected closed weekdays. Negative Thanksgiving/Christmas/NewYear access facts always win.",
    },
    "nps-heritage:kimo": {
        "sha256": "e245a05a56585d04ac67919ad10e134f2762e4523e050d197df0af2e05d951e7",
        "checked_at": "2026-10-15T03:15:56.809859+00:00",
        "facility_id": 96,
        "schedule_id": 212,
        "full": [3395],
        "closed_holidays": [],
        "review": "Blank holiday flag-zero cells carry no literal clocks; omit their dates as unknown unless independently explicit closure. Ordinary Wed–Sun sessions remain supported by selected and parent tables.",
    },
    "nps-heritage:malu": {
        "sha256": "a8354ac629791e5cbdf97b1ff52ecdc4eb65d7c5425cd84cc3a09b6ff45a8eae",
        "checked_at": "2026-10-15T03:15:57.098297+00:00",
        "facility_id": 2579,
        "schedule_id": 3518,
        "full": [3517],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected prose contradicts itself about Sundays; explicit park-closed Sunday wins, although parent table says daily. Birth-home tours on hold and fire station staffing are other components.",
    },
    "nps-heritage:ruca": {
        "sha256": "62d6059270e2ba2042c8434e17b99fdc9253c85e8df14288fc0e10bed018e4e0",
        "checked_at": "2026-10-15T03:15:58.461715+00:00",
        "facility_id": 4685,
        "schedule_id": 18284,
        "full": [215],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:waco": {
        "sha256": "f0baf9feddc41b2f6c69cf2266383c265a0cfa8234d4ddf7145e21e388d63c87",
        "checked_at": "2026-10-15T03:15:59.622463+00:00",
        "facility_id": 2337,
        "schedule_id": 2739,
        "full": [2735],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Native Sunday09:00PM–05:00PM is reversed and withheld. Do not repair AM/PM using parent daily table; retain other six native day sessions.",
    },
    "nps-heritage:wicl": {
        "sha256": "409916d44bdcd616193f247616eb85bd936a50700d4372f94ff03550ceb9b48f",
        "checked_at": "2026-10-15T03:15:59.698591+00:00",
        "facility_id": 3679,
        "schedule_id": 10737,
        "full": [3126],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:frdo": {
        "sha256": "64ccb860db70b8714d6b0ad9256ee91f6d9fab99e787b97855b7cf09ca55d778",
        "checked_at": "2026-10-15T03:15:55.383038+00:00",
        "facility_id": 5967,
        "schedule_id": 21135,
        "full": [356],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected literal facility hours intersect all native exceptions and the identified parent access schedule. Other components cannot supply wider positive hours. Named literal closure facts override blank clock cells; unknown cells are held.",
    },
    "nps-heritage:jofl": {
        "sha256": "e6050ecd72484471373812ebbcf0309743ccc7d20aa915a83f2b39cbb25219f4",
        "checked_at": "2026-10-15T03:15:56.620214+00:00",
        "facility_id": 1228,
        "schedule_id": 1479,
        "full": [1477],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Parent explicitly says All Park Hours reflect visitor-center operations, not sunrise/sunset park grounds. Film starts:15 each hour are not exclusive access start constraints.",
    },
    "nps-heritage:spar": {
        "sha256": "a1dfed5e4a06601250577d9311509e6059bec095a7c0ff21d1feff130cd8f2ab",
        "checked_at": "2026-10-15T03:15:58.905109+00:00",
        "facility_id": 2609,
        "schedule_id": 19423,
        "full": [21542],
        "closed_holidays": ["Thanksgiving Day", "Christmas Day", "New Year’s Day"],
        "review": "Selected museum and parent full schedules agree on current Wed–Sun 09:30–16:00; winter Jan 2–Apr 5 exception is outside 2026 Oct–Dec finite scope, never repeated into 2027.",
    },
}

CURRENT_EVIDENCE = {
    "mora": {
        "source_url": "https://www.nps.gov/mora/planyourvisit/longmire.htm",
        "snapshot_sha256": "6b0eee2381ecb6cdc1cb5fb9ed14c1f42842be03160fcbfe337e8faa977a2adf",
        "checked_at": "2026-10-15T19:47:02.194450+00:00",
        "facts": [
            "The Longmire Museum , usually open daily all year, offers exhibits, information, and books sales.",
            "During the winter, the road to Paradise from Longmire is closed nightly.",
        ],
        "interpretation": "The official page locates the nightly winter road closure from Longmire to Paradise, beyond the selected Longmire museum. The native museum midday closure still applies. Original acquisition time is preserved.",
    },
    "cabr": {
        "source_url": "https://www.nps.gov/cabr/planyourvisit/hours.htm",
        "snapshot_sha256": "b322bde9ec88b1a7bc940f29e35172b5a929152f29d2c9dbd4e79c05c4de4176",
        "checked_at": "2026-10-15T21:56:57.107087+00:00",
        "facts": [
            "Cabrillo National Monument (Main Park) is open daily from 9:00 AM to 5:00 PM, with the exception of Thanksgiving Day and Christmas Day when we are closed.",
            "Visitor Center / Bookstore: 10:00 AM - 4:00 PM (weekdays), 10:00 AM - 5:00 PM (weekends)",
            "The park is CLOSED on Thanksgiving Day and Christmas Day. There is no public access to any areas of the park on these two holidays.",
        ],
        "interpretation": "Current official page confirms selected facility weekday/weekend clocks and explicit Thanksgiving/Christmas whole-park closure; trail/tidepool times are distinct activities.",
    },
    "seki": {
        "source_url": "https://www.nps.gov/seki/planyourvisit/visitorcenters.htm",
        "snapshot_sha256": "52ab49079b0eaab19345312ebcc82f114e923735150494dc17146a56ef805219",
        "checked_at": "2026-10-15T21:56:57.107877+00:00",
        "facts": [
            "While our parks are open 24 hours a day, 365 days a year , not all visitor centers are open year-round. Some close seasonally."
        ],
        "interpretation": "Current general directory does not supply selected clocks or negate native specific museum fall table. Seasonal closure statements belong to named other components; native full original retains all component scopes.",
    },
    "labe": {
        "source_url": "https://www.nps.gov/labe/planyourvisit/hours.htm",
        "snapshot_sha256": "e8e6d46372973520e279aa7d777940d21dc3c8b1fca6e6d875c76a0ed1c5ba69",
        "checked_at": "2026-10-15T21:56:57.254248+00:00",
        "facts": [
            "The Visitor Center is Open Daily from 9:00 am to 5:00 pm.",
            "Christmas Day - December 25th, 2025: Closed",
        ],
        "interpretation": "Current page confirms same selected 09:00–17:00 clocks. Stale 2025 Christmas listing never erases retained native Thanksgiving/Christmas negative facts or supplies 2026 holiday clocks.",
    },
}

REVIEW_HOLDS = {
    "nps:lavo": "Loomis off-season prose begins post-Columbus-Day, earlier than November 2 table; no positive acquisition-year fall dates survive the stricter closure.",
    "nps-heritage:puho": "Applicable park gate closes at sunset, exact clock deferred to phone/social page; no verified literal full-dwell access end.",
    "nps-heritage:pete": "Applicable access schedule has astronomical boundaries and season conflicts; no literal full-dwell access end established for the review scope.",
    "nps-heritage:saan": "Selected visitor-center description says often closed for lunch without exact clocks; Park Store 13:00–14:00 break cannot establish the visitor-center break.",
    "nps-heritage:paal": "Selected visitor center may close during unspecified lunch hour; do not invent an uninterrupted two-hour session from nominal daily clocks.",
    "nps-heritage:knri": "Parent all-park sunrise/sunset boundary is not clearly separated from selected visitor-center motor access; no solar clock inferred.",
    "nps-heritage:fobu": "Parent explicitly limits entry sunrise–sunset and says motor access varies; no literal access end supplied.",
    "nps-heritage:fola": "Parent grounds dawn–dusk access boundary remains unresolved for selected facility; mixed holiday/date seasonal selectors also require further review.",
    "nps-heritage:mima": "Parking gates close at sunset; no verified literal full-dwell motor-access end, despite explicit 2026 facility dates.",
    "nps-heritage:flni": "Parent gates/grounds follow sunrise–sunset and adverse-weather closures; no literal motor-access end verified.",
    "nps-heritage:fone": "Entrance is explicitly allowed sunrise–sunset; indoor schedule alone does not establish full-dwell motor access.",
    "nps-heritage:fosc": "Parent parking and access follow half-hour solar boundaries; no exact gate clocks and blank holiday exceptions remain unresolved.",
    "nps-heritage:nebe": "Base clock boundaries are astronomical/zero and seasonal exception clocks cannot silently replace them; requires explicit reviewed active-season override semantics.",
}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _load(record, row, reader):
    source_id = record["catalog_source_id"]
    if source_id not in PROFILES:
        raise CalendarHold(
            REVIEW_HOLDS.get(
                source_id,
                "No reviewed second-batch native profile; retained source constraints require further scoped review.",
            )
        )
    pin = PROFILES[source_id]
    code = source_id.split(":", 1)[1]
    url = f"https://www.nps.gov/{code}/structured_data_{code}.json"
    body_path, body = reader.read(record["retained_snapshot_path"])
    if hashlib.sha256(body).hexdigest() != pin["sha256"]:
        raise CalendarHold("Original body differs from second-batch immutable review pin")
    if (
        record["source_url"] != url
        or record["source_snapshot_sha256"] != pin["sha256"]
        or record["source_acquired_at"] != pin["checked_at"]
        or row["source_id"] != source_id
    ):
        raise CalendarHold("Original receipt/source identity differs")
    original = json.loads(body.decode("utf-8-sig"))
    if original.get("siteCode") != code:
        raise CalendarHold("Native park identity differs")
    matches = [
        (i, f)
        for i, f in enumerate(original["visitorCenters"])
        if f.get("visitorCenterID") == pin["facility_id"]
    ]
    if len(matches) != 1:
        raise CalendarHold("Selected native facility is not unique")
    index, facility = matches[0]
    pointer = f"/visitorCenters/{index}"
    if record["facility_json_pointer"] != pointer:
        raise CalendarHold("Native facility pointer differs")
    if any(float(facility["location"][axis]) != row[axis] for axis in ("latitude", "longitude")):
        raise CalendarHold("Native selected-facility coordinates differ")
    receipt_matches = [
        p
        for p in row.get("provenance", [])
        if p.get("dataset") == "National Park Service structured visitor facility"
        and str(p.get("record_id")) == str(pin["facility_id"])
        and p.get("source_url") == url
        and p.get("snapshot_sha256") == pin["sha256"]
        and p.get("checked_at") == pin["checked_at"]
    ]
    if len(receipt_matches) != 1:
        raise CalendarHold("Admitted raw-row facility provenance differs")
    receipt = {
        "source_url": url,
        "snapshot_sha256": pin["sha256"],
        "checked_at": pin["checked_at"],
        "evidence_path": str(body_path),
        "native_facility_id": pin["facility_id"],
        "native_json_pointer": pointer,
    }
    return pin, original, facility, pointer, receipt


def _current(record, code, reader):
    if code not in CURRENT_EVIDENCE:
        return [], []
    pin = CURRENT_EVIDENCE[code]
    if not record.get("current_official_evidence_path"):
        raise CalendarHold("Reviewed current official evidence is required")
    body_path, body = reader.read(record["current_official_evidence_path"])
    if hashlib.sha256(body).hexdigest() != pin["snapshot_sha256"]:
        raise CalendarHold("Current official corroboration hash differs")
    page = _Text()
    page.feed(body.decode("utf-8"))
    text = " ".join(" ".join(page.parts).split())
    if any(literal not in text for literal in pin["facts"]):
        raise CalendarHold("Reviewed current official literal is absent")
    receipt = {key: pin[key] for key in ("source_url", "snapshot_sha256", "checked_at")}
    receipt["evidence_path"] = str(body_path)
    return [receipt], [
        {
            **receipt,
            "literal": fact,
            "scope": "current_official_corroboration",
            "interpretation": pin["interpretation"],
        }
        for fact in pin["facts"]
    ]


def _schedule(schedule, day):
    windows = _day_windows(schedule["hours"], day)
    for exception in schedule.get("exceptions", []):
        if not windows:
            break
        if not _exception_applies(exception, day):
            continue
        text = " ".join(str(exception.get(k, "")) for k in ("name", "description")).lower()
        # Explicit whole-day closure prose wins over stale weekday cells. Weekly
        # winter tables must still use their actual weekday; never close a whole
        # season just because its prose includes "closed Sundays".
        weekly = any(
            word in text
            for word in (
                "sunday",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "weekly",
            )
        )
        if not weekly and any(word in text for word in ("closed", "closure")):
            windows = []
        else:
            windows = _intersect(windows, _day_windows(exception["schedule"], day))
    return windows


def _required(text, literal):
    if literal not in text:
        raise CalendarHold("Pinned source restriction literal is absent")


def _prose_restrictions(code, day, windows, facility, selected, parents):
    """Narrow literal rules; none can enlarge source-table availability."""
    if code == "mora":
        _required(selected["description"], "Closed midday from 12:00 pm - 1:00 pm.")
        windows = _intersect(windows, [(0, _clock("12:00 pm")), (_clock("1:00 pm"), 1440)])
    if code == "colm":
        _required(selected["description"], "Winter hours are 9:00 a.m. to 4:00 p.m.")
        windows = _intersect(windows, [(_clock("9:00 AM"), _clock("4:00 PM"))])
    if code == "nabr":
        _required(facility["description"], "9 am to 4 pm")
        _required(facility["description"], "Friday through Monday")
        windows = (
            _intersect(windows, [(_clock("9:00 AM"), _clock("4:00 PM"))])
            if day.weekday() in (4, 5, 6, 0)
            else []
        )
    if code == "tont" and (day.month, day.day) in ((12, 24), (12, 31)):
        _required(
            parents[3005]["description"],
            "The park closes early at 1:45 pm on Christmas Eve and New Year's Eve.",
        )
        windows = _intersect(windows, [(0, _clock("1:45 pm"))])
    if code == "pipe" and day.month in (11, 12):
        exception = next(
            e for e in selected["exceptions"] if e["operatingScheduleExceptionID"] == 29297
        )
        _required(
            exception["description"], "closed on Sundays and Mondays from November through April"
        )
        if day.weekday() in (6, 0):
            windows = []
    if code == "anjo":
        _required(
            parents[3563]["description"],
            "Winter/Spring Hours: Generally open Wednesday through Sunday from 9 am to 4 pm.",
        )
        if day.weekday() in (0, 1):
            windows = []
    if code == "malu":
        _required(selected["description"], "The park is closed on Sunday.")
        if day.weekday() == 6:
            windows = []
    return windows


def _transform_record(record: dict, catalog_row: dict, reader: _EvidenceReader) -> dict:
    pin, original, facility, pointer, receipt = _load(record, catalog_row, reader)
    code = record["catalog_source_id"].split(":", 1)[1]
    corroboration, current_constraints = _current(record, code, reader)
    schedules = facility["operatingHours"]
    if len(schedules) != 1:
        raise CalendarHold("Multiple selected facility schedules need explicit review")
    key, selected = next(iter(schedules.items()))
    if selected["operatingScheduleID"] != pin["schedule_id"]:
        raise CalendarHold("Native selected schedule differs")
    selected_pointer = f"{pointer}/operatingHours/{key}"
    constraints = [
        _fact(
            receipt,
            f"{pointer}/description",
            facility.get("description", ""),
            "selected_facility",
            "Retain identity, component access, staffing, ticket and all negative qualifications.",
        ),
        _fact(
            receipt,
            selected_pointer,
            selected,
            "selected_facility",
            "Literal base hours intersect every applicable exception and all reviewed prose restrictions; blanks never establish openness.",
        ),
    ]
    parents = {s["operatingScheduleID"]: s for s in original["operatingHours"]}
    if len(parents) != len(original["operatingHours"]) or any(
        i not in parents for i in pin["full"]
    ):
        raise CalendarHold("Parent access schedule identities differ")
    for index, schedule in enumerate(original["operatingHours"]):
        identity = schedule["operatingScheduleID"]
        if identity == pin["schedule_id"]:
            if any(
                schedule.get(f) != selected.get(f)
                for f in ("hours", "exceptions", "description", "label")
            ):
                raise CalendarHold("Parent/facility duplicate schedule conflict")
            scope, interpretation = (
                "selected_facility_duplicate",
                "Exact selected schedule duplicate; retained without inventing extra availability.",
            )
        elif identity in pin["full"]:
            scope, interpretation = (
                "applicable_access",
                "Intersect this full access schedule and every applicable exception; negative facts win.",
            )
        else:
            scope, interpretation = (
                "other_component",
                "Separately retained other component. The pinned review explains boundaries; its clocks cannot establish selected-facility availability.",
            )
        constraints.append(
            _fact(receipt, f"/operatingHours/{index}", schedule, scope, interpretation)
        )
    constraints.extend(current_constraints)
    start = datetime.fromisoformat(pin["checked_at"]).date()
    if start.year != 2026:
        raise CalendarHold(
            "Profiles are reviewed only for their original 2026 acquisition-year scope"
        )
    end = date(2026, 12, 31)
    closed_days = {_holiday(name, 2026) for name in pin["closed_holidays"]}
    overrides, withheld = [], []
    day = start
    while day <= end:
        try:
            if day in closed_days:
                windows = []
            else:
                windows = _schedule(selected, day)
                for identity in pin["full"]:
                    if not windows:
                        break
                    windows = _intersect(windows, _schedule(parents[identity], day))
                windows = _prose_restrictions(code, day, windows, facility, selected, parents)
            overrides.append(
                {
                    "date": day.isoformat(),
                    "windows": [
                        {
                            "opens": f"{a // 60:02d}:{a % 60:02d}",
                            "closes": f"{b // 60:02d}:{b % 60:02d}",
                            "end_day_offset": 0,
                        }
                        for a, b in windows
                    ],
                }
            )
        except (CalendarHold, StopIteration) as exc:
            withheld.append({"date": day.isoformat(), "reason": str(exc)})
        day += timedelta(days=1)
    if not any(w["windows"] for w in overrides):
        raise CalendarHold("No supported positive dated windows remain")
    return {
        "source_id": record["catalog_source_id"],
        "source_visit_calendar": {
            "schema_version": SCHEMA,
            "weekly_windows": [],
            "seasons": [{"kind": "dated", "start": start.isoformat(), "end": end.isoformat()}],
            "date_overrides": overrides,
            "annual_closures": [],
            "source_receipts": [receipt, *corroboration],
            "unknown_reasons": [],
        },
        "source_constraints": constraints,
        "transformation": {
            "schema_version": TRANSFORMATION,
            "native_facility_id": pin["facility_id"],
            "native_schedule_id": pin["schedule_id"],
            "native_facility_pointer": pointer,
            "evaluated_date_scope": {"start": start.isoformat(), "end": end.isoformat()},
            "scope_basis": "Original 2026 acquisition date through 2026 year end only. Finite interpretation scope, not source-published expiry, source freshness refresh, or future validity guarantee. No 2027 annual/year reuse.",
            "reviewed_scope_and_negative_facts": pin["review"],
            "named_literal_holiday_closures": pin["closed_holidays"],
            "withheld_dates": withheld,
            "rules": [
                "Unmodified native facility ID, coordinates and admitted source receipt required.",
                "Every selected/parent raw schedule, exception, label and description is retained separately.",
                "All applicable clocks intersect; closure and earlier seasonal/prose restrictions win.",
                "Blank, reversed, solar or unsupported active clocks withhold the date; no AM/PM repair.",
                "No inferred timezone, observed holiday, fixed start, ticket, price or parking.",
            ],
        },
    }


def transform_record(
    record: dict, catalog_row: dict, *, evidence_root=None, allow_private_absolute=False
) -> dict:
    """Replay one row; absolute fixture access requires explicit private opt-in."""
    _validate_inputs({"records": [record]}, [catalog_row])
    return _transform_record(
        record,
        catalog_row,
        _EvidenceReader(evidence_root, allow_private_absolute=allow_private_absolute),
    )


def _build_entries(extraction, catalog_items, reader):
    records = _validate_inputs(extraction, catalog_items)
    items = {row["source_id"]: row for row in catalog_items}
    if len(items) != len(catalog_items):
        raise CalendarHold("Duplicate admitted source identity")
    entries, holds = [], []
    source_ids = [record["catalog_source_id"] for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise CalendarHold("Duplicate extraction source identity")
    for record in records:
        source_id = record["catalog_source_id"]
        try:
            entries.append(_transform_record(record, items[source_id], reader))
        except EvidenceBoundaryError:
            raise  # Import ceilings/path violations cannot become partial admission.
        except (CalendarHold, KeyError, OSError, TypeError, ValueError) as exc:
            holds.append(
                {
                    "source_id": source_id,
                    "source_url": record.get("source_url"),
                    "snapshot_sha256": record.get("source_snapshot_sha256"),
                    "checked_at": record.get("source_acquired_at"),
                    "evidence_path": record.get("retained_snapshot_path"),
                    "native_json_pointer": record.get("facility_json_pointer"),
                    "reason": str(exc),
                }
            )
    return {
        "schema_version": TRANSFORMATION,
        "entries": entries,
        "holds": holds,
        "summary": {
            "requested_rows": len(source_ids),
            "emitted_rows": len(entries),
            "held_rows": len(holds),
            "positive_dated_days": sum(
                bool(d["windows"])
                for e in entries
                for d in e["source_visit_calendar"]["date_overrides"]
            ),
            "positive_dated_windows": sum(
                len(d["windows"])
                for e in entries
                for d in e["source_visit_calendar"]["date_overrides"]
            ),
            "withheld_ambiguous_dates": sum(
                len(e["transformation"]["withheld_dates"]) for e in entries
            ),
        },
    }


def build_entries(
    extraction: dict,
    catalog_items: list[dict],
    *,
    evidence_root=None,
    allow_private_absolute=False,
) -> dict:
    """Replay one bounded import, sharing a single unique-file read budget."""
    _validate_inputs(extraction, catalog_items)
    return _build_entries(
        extraction,
        catalog_items,
        _EvidenceReader(evidence_root, allow_private_absolute=allow_private_absolute),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", required=True, type=Path)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--evidence-root", type=Path)
    mode.add_argument("--private-offline-absolute", action="store_true")
    args = parser.parse_args()
    reader = _EvidenceReader(
        args.evidence_root,
        allow_private_absolute=args.private_offline_absolute,
    )
    extraction = json.loads(reader.read_control(args.extraction))
    # Reject an excessive source-record list before reading the parent operand.
    records = extraction.get("records") if isinstance(extraction, dict) else None
    if not isinstance(records, list) or not 0 < len(records) <= MAX_SOURCE_ROWS:
        raise EvidenceBoundaryError("Extraction requires 1..50000 source records")
    result = _build_entries(
        extraction,
        json.loads(reader.read_control(args.items)),
        reader,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
