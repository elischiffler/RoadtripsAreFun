"""Vehicle parking joins are exact, scoped, and independent of clocks/GPS."""

import hashlib

import pytest

from app.catalog import usfs_parking_pdf as parking

URL = "https://www.fs.usda.gov/sites/nfs/files/r05/tahoe/publication/Equestrian%20ROG%202025.pdf"
TITLE = "Donner Summit Pacific Crest Trailhead"
TEXT = (
    TITLE + " has parking for nine trailer pulling vehicles and 16 single vehicles. "
    "No overnight camping is allowed at the trailhead. Facilities include drinking water."
)


def facility(**values):
    return {
        "site_cn": "5340.004481",
        "region": "05",
        "usda_portal_url": "https://www.fs.usda.gov/recarea/tahoe/recarea/?recid=55804",
        "recarea_description": TITLE,
        "directions": TITLE
        + " is located on the south side of I-80 at the Castle Peak/Boreal exit.",
        **values,
    }


def documents(text=TEXT, url=URL):
    return [
        {
            "receipt": {"url": url, "sha256": "a" * 64, "path": "parking.pdf"},
            "blocks": [{"page": 2, "text": text}],
        }
    ]


def synthetic_receipt(monkeypatch, body):
    digest = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(parking, "PUBLICATION_PINS", {URL: digest})
    return {"url": URL, "sha256": digest}


def test_extract_only_capacity_and_camping_restrictions():
    value = parking.match(facility(), documents())
    assert value["record_id"] == "5340.004481" and value["single_vehicle_spaces"] == 16
    assert value["forest_unit"] == "tahoe" and value["page"] == 2
    assert value["literal_parking_statement"].endswith("16 single vehicles.")
    assert "water" not in value["literal_parking_statement"]
    assert value["literal_camping_restrictions"] == [
        "No overnight camping is allowed at the trailhead."
    ]
    assert value["capacity_is_current_inventory"] is False
    assert value["hours_or_coordinates_imported_from_pdf"] is False


@pytest.mark.parametrize(
    "change",
    [
        "no_title",
        "partial_title",
        "wrong_forest",
        "wrong_region",
        "missing_approach",
        "trailer_only",
        "overnight_parking",
        "closed",
        "duplicate_bullet",
    ],
)
def test_ambiguous_or_restricted_vehicle_parking_is_not_imported(change):
    native, pubs = facility(), documents()
    if change == "no_title":
        native["recarea_description"] = ""
    if change == "partial_title":
        pubs[0]["blocks"][0]["text"] = "East " + TEXT
    if change == "wrong_forest":
        native["usda_portal_url"] = "https://www.fs.usda.gov/recarea/another/recarea/?recid=55804"
    if change == "wrong_region":
        native["region"] = "04"
    if change == "missing_approach":
        native["directions"] = "Turn right at the next road."
    if change == "trailer_only":
        pubs[0]["blocks"][0]["text"] = TITLE + " has parking for nine trailer pulling vehicles."
    if change == "overnight_parking":
        pubs[0]["blocks"][0]["text"] += " No overnight parking."
    if change == "closed":
        pubs[0]["blocks"][0]["text"] += " Parking is closed due to construction."
    if change == "duplicate_bullet":
        pubs[0]["blocks"].append({"page": 3, "text": TEXT})
    assert parking.match(native, pubs) is None


def test_one_bullet_cannot_inflate_two_native_facilities():
    first = facility()
    second = facility(site_cn="different-id")
    assert parking.joins({first["site_cn"]: first, second["site_cn"]: second}, documents()) == {}


def test_neighboring_bullet_restrictions_are_separate(monkeypatch):
    import pypdf

    class Page:
        def extract_text(self):
            return (
                "• Castle Valley Campsite has overnight camping allowed. • "
                + TEXT
                + " • Black Camp-Loney Meadow has no overnight parking."
            )

    class Reader:
        is_encrypted = False
        pages = [Page()]

    monkeypatch.setattr(pypdf, "PdfReader", lambda *args, **kwargs: Reader())
    values = parking.extract(
        [synthetic_receipt(monkeypatch, b"%PDF-original-body")],
        lambda receipt: b"%PDF-original-body",
    )
    result = parking.match(facility(), values)
    assert result and result["single_vehicle_spaces"] == 16
    assert result["literal_camping_restrictions"] == [
        "No overnight camping is allowed at the trailhead."
    ]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/parking.pdf",
        "http://www.fs.usda.gov/sites/nfs/files/r05/tahoe/publication/guide.pdf",
        URL + "?redirect=other",
        "https://www.fs.usda.gov/internal/file.pdf",
    ],
)
def test_pdf_must_be_an_official_publication_asset(url):
    assert parking.official_publication(url) is False
    with pytest.raises(ValueError, match="official USFS"):
        parking.extract([{"url": url}], lambda _: b"%PDF-body")


def test_pdf_body_is_bounded_before_parsing():
    with pytest.raises(ValueError, match="bounded original PDF"):
        parking.extract([{"url": URL}], lambda _: b"%PDF-" + b"a" * parking.MAX_PDF_BYTES)
    with pytest.raises(ValueError, match="bounded original PDF"):
        parking.extract([{"url": URL}], lambda _: b"<html>denied</html>")


def test_pdf_decompression_limit_is_restored_after_parse_failure(monkeypatch):
    import pypdf
    from pypdf import filters

    original = filters.ZLIB_MAX_OUTPUT_LENGTH

    def fail(*args, **kwargs):
        assert 0 < filters.ZLIB_MAX_OUTPUT_LENGTH <= parking.MAX_DECOMPRESSED_STREAM
        raise ValueError("malformed PDF")

    monkeypatch.setattr(pypdf, "PdfReader", fail)
    receipt = synthetic_receipt(monkeypatch, b"%PDF-body")
    with pytest.raises(ValueError, match="malformed PDF"):
        parking.extract([receipt], lambda _: b"%PDF-body")
    assert filters.ZLIB_MAX_OUTPUT_LENGTH == original


@pytest.mark.parametrize("kind", ["encrypted", "pages", "text"])
def test_pdf_page_and_text_limits_prevent_oversized_extraction(monkeypatch, kind):
    import pypdf

    class Page:
        def extract_text(self):
            return "a" * (256 * 1024 + 1) if kind == "text" else "• short"

    class Reader:
        is_encrypted = kind == "encrypted"
        pages = [Page()] * (parking.MAX_PAGES + 1 if kind == "pages" else 1)

    monkeypatch.setattr(pypdf, "PdfReader", lambda *args, **kwargs: Reader())
    receipt = synthetic_receipt(monkeypatch, b"%PDF-body")
    with pytest.raises(ValueError, match="ceiling|encrypted"):
        parking.extract([receipt], lambda _: b"%PDF-body")


def test_real_pdf_parser_preserves_bullet_identity_and_single_vehicle_fact(monkeypatch):
    # A tiny in-memory PDF exercises the pinned parser without a network fixture
    # or republishing a government document as a committed test artifact.
    text = ("\u2022 " + TEXT).encode("cp1252")
    content = b"BT /F1 12 Tf 72 720 Td (" + text + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    body, offsets = bytearray(b"%PDF-1.7\n"), [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(body))
        body.extend(str(index).encode() + b" 0 obj\n" + value + b"\nendobj\n")
    start = len(body)
    body.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(start).encode() + b"\n%%EOF\n"
    )
    values = parking.extract([synthetic_receipt(monkeypatch, bytes(body))], lambda _: bytes(body))
    result = parking.match(facility(), values)
    assert result["single_vehicle_spaces"] == 16 and result["page"] == 1
    assert result["literal_camping_restrictions"] == [
        "No overnight camping is allowed at the trailhead."
    ]


def test_changed_publication_edition_requires_independent_review():
    with pytest.raises(ValueError, match="edition changed"):
        parking.extract([{"url": URL, "sha256": "b" * 64}], lambda _: b"%PDF-new-edition")


def test_native_direction_title_must_end_at_a_word_boundary():
    assert (
        parking.match(facility(directions=TITLE + "East is located on I-80."), documents()) is None
    )


@pytest.mark.parametrize(
    "prefix,accepted",
    [
        ("No overnight parking. ", False),
        (
            "www.fs.usda.gov/r05/tahoe USDA in an equal opportunity provider and employer.\n2025\n",
            True,
        ),
    ],
)
def test_possible_cross_page_bullet_continuations_are_held(monkeypatch, prefix, accepted):
    import pypdf

    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class Reader:
        is_encrypted = False
        pages = [Page("• " + TEXT), Page(prefix + "• Another trailhead has no car parking.")]

    monkeypatch.setattr(pypdf, "PdfReader", lambda *args, **kwargs: Reader())
    values = parking.extract([synthetic_receipt(monkeypatch, b"%PDF-body")], lambda _: b"%PDF-body")
    assert (parking.match(facility(), values) is not None) is accepted
