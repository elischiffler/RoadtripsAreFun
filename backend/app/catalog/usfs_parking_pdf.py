"""Literal vehicle-parking facts from official USFS publication bullet tables.

This does not supply hours, coordinates, operating status, water or availability.
A complete publisher-native facility title must start one unique bullet and the
same title must start its published approach directions. Trailer-only capacity
never establishes ordinary visitor-car parking.
"""

from __future__ import annotations

import hashlib
import io
import re
from threading import Lock
from urllib.parse import urlsplit

MAX_PDF_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20
MAX_DECOMPRESSED_STREAM = 8 * 1024 * 1024
_PDF_LOCK = Lock()
PUBLICATION_PINS = {
    "https://www.fs.usda.gov/sites/nfs/files/r05/tahoe/publication/Equestrian%20ROG%202025.pdf": "c9e8679a0fc3050655bfe165959cb3fa09f8f738ec0b0f8efc8f4c425effebfd",
}
PUBLICATION_URLS = frozenset(PUBLICATION_PINS)


def official_publication(url):
    value = urlsplit(url)
    return (
        url in PUBLICATION_URLS
        and value.scheme == "https"
        and value.netloc == "www.fs.usda.gov"
        and value.path.startswith("/sites/nfs/files/")
        and "/publication/" in value.path
        and value.path.lower().endswith(".pdf")
        and not value.query
        and not value.fragment
    )


def extract(receipts, read_body):
    """Replay original PDF bytes locally; lazily require the pinned PDF parser."""
    from pypdf import PdfReader, filters

    if not isinstance(receipts, list) or len(receipts) > 16:
        raise ValueError("USFS parking publications require a bounded source list")
    documents = []
    for receipt in receipts:
        if not official_publication(receipt["url"]):
            raise ValueError("parking corroboration requires an official USFS publication")
        body = read_body(receipt)
        if not 0 < len(body) <= MAX_PDF_BYTES or not body.startswith(b"%PDF-"):
            raise ValueError("USFS parking publication is not a bounded original PDF")
        expected = PUBLICATION_PINS[receipt["url"]]
        if receipt.get("sha256") != expected or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError(
                "USFS parking publication edition changed; independent review required"
            )
        with _PDF_LOCK:
            previous_limit = filters.ZLIB_MAX_OUTPUT_LENGTH
            filters.ZLIB_MAX_OUTPUT_LENGTH = min(
                previous_limit or MAX_DECOMPRESSED_STREAM, MAX_DECOMPRESSED_STREAM
            )
            try:
                reader = PdfReader(io.BytesIO(body), strict=True)
                if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
                    raise ValueError("USFS parking PDF is encrypted or exceeds page ceiling")
                blocks, size = [], 0
                for number, page in enumerate(reader.pages, 1):
                    text = page.extract_text() or ""
                    size += len(text)
                    if size > 256 * 1024:
                        raise ValueError("USFS parking publication text exceeds ceiling")
                    pieces = text.split("•")
                    if blocks:
                        prefix = "\n".join(
                            line.strip() for line in pieces[0].splitlines() if line.strip()
                        )
                        # Only the visually reviewed running header can be
                        # discarded. Any other next-page prefix may continue
                        # the preceding bullet and makes that join ambiguous.
                        prefix = re.sub(
                            r"(?m)^www\.fs\.usda\.gov/[^\n]+$|^USDA in an? equal opportunity provider and employer\.$|^20[0-9]{2}$",
                            "",
                            prefix,
                        )
                        blocks[-1]["following_page_prefix"] = " ".join(prefix.split())
                    for block in pieces[1:]:
                        # Blank lines are layout, not permission to merge adjacent bullets.
                        blocks.append({"page": number, "text": " ".join(block.split())})
            finally:
                filters.ZLIB_MAX_OUTPUT_LENGTH = previous_limit
        documents.append({"receipt": receipt, "blocks": blocks})
    return documents


def match(facility, documents):
    """Join only exact complete native titles and literal single-vehicle capacity."""
    directions = " ".join(str(facility.get("directions") or "").split())
    titles = set()
    for key in ("recarea_description", "public_site_name", "recarea_name", "site_name"):
        title = " ".join(str(facility.get(key) or "").split())
        if (
            8 <= len(title) <= 120
            and re.fullmatch(r"[A-Za-z0-9 /#&'’().-]+", title)
            and re.match(re.escape(title) + r"(?=\s|$|[.,:;])", directions, re.I)
        ):
            titles.add(title)
    matches = {}
    for document in documents:
        publication = re.match(
            r"/sites/nfs/files/(r[0-9]{2})/([^/]+)/publication/",
            urlsplit(document["receipt"]["url"]).path,
        )
        native = urlsplit(facility.get("usda_portal_url") or "")
        native_unit = re.match(r"/(?:recarea/([^/]+)|r[0-9]{2}/([^/]+))/", native.path)
        if (
            not publication
            or native.hostname not in {"www.fs.usda.gov", "fs.usda.gov"}
            or not native_unit
            or publication[2] != next(value for value in native_unit.groups() if value is not None)
            or str(facility.get("region", "")).zfill(2) != publication[1][1:]
        ):
            continue
        for block in document["blocks"]:
            text = block["text"]
            if block.get("following_page_prefix"):
                continue
            matched_title = next(
                (
                    title
                    for title in sorted(titles, key=len, reverse=True)
                    if re.match(re.escape(title) + r"(?:\s+has\b|\s+is\b|\.)", text, re.I)
                ),
                None,
            )
            if not matched_title:
                continue
            sentences = re.split(r"(?<=\.)\s+", text)
            parking = [
                sentence for sentence in sentences if re.search(r"\bparking\b", sentence, re.I)
            ]
            if len(parking) != 1:
                continue
            sentence = parking[0]
            count = re.search(
                r"\bparking\s+for\b[^.]{0,160}\b([1-9][0-9]{0,3})\s+single vehicles\b",
                sentence,
                re.I,
            )
            if not count or re.search(
                r"\bonly\b|\bno (?:car |vehicle )?parking\b|reservation|permit|not available|prohibit|\bclos(?:e[sd]?|ure)\b|gate|no overnight parking",
                text,
                re.I,
            ):
                continue
            # This check intentionally excludes amenities in later sentences,
            # including older water claims that may conflict with current feeds.
            restrictions = [s for s in sentences if re.search(r"\bno overnight camping\b", s, re.I)]
            key = document["receipt"]["sha256"], block["page"], text
            matches[key] = {
                "record_id": facility["site_cn"],
                "forest_unit": publication[2],
                "matched_native_title": matched_title,
                "single_vehicle_spaces": int(count[1]),
                "literal_parking_statement": sentence,
                "literal_camping_restrictions": restrictions,
                "page": block["page"],
                "receipt": document["receipt"],
                "capacity_is_current_inventory": False,
                "hours_or_coordinates_imported_from_pdf": False,
            }
    return next(iter(matches.values())) if len(matches) == 1 else None


def joins(facilities, documents):
    """One publication bullet cannot inflate two native facility identities."""
    found, owners = {}, {}
    for ident, facility in facilities.items():
        if value := match(facility, documents):
            found[ident] = value
            key = (
                value["receipt"]["sha256"],
                value["page"],
                value["matched_native_title"].casefold(),
            )
            owners.setdefault(key, []).append(ident)
    ambiguous = {ident for values in owners.values() if len(values) != 1 for ident in values}
    return {ident: value for ident, value in found.items() if ident not in ambiguous}
