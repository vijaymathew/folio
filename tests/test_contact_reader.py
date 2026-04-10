from __future__ import annotations

from pathlib import Path

from folio.core.contact_reader import ContactReader
from folio.renderers.base import RendererFileAccess


def test_contact_reader_parses_single_vcard_fields() -> None:
    text = """BEGIN:VCARD
VERSION:3.0
FN:Sara Chen
EMAIL;TYPE=work:sara@example.com
TEL;TYPE=cell:+1-555-0100
ORG:Northwind Labs
TITLE:Finance Lead
NOTE:Quarterly review owner
END:VCARD
"""

    contacts = ContactReader().parse_text(text)

    assert len(contacts) == 1
    assert contacts[0].full_name == "Sara Chen"
    assert contacts[0].emails == ["sara@example.com"]
    assert contacts[0].phones == ["+1-555-0100"]
    assert contacts[0].organization == "Northwind Labs"
    assert contacts[0].title == "Finance Lead"


def test_contact_reader_reads_directory_of_vcards(tmp_path: Path) -> None:
    contacts_dir = tmp_path / "contacts"
    contacts_dir.mkdir()
    (contacts_dir / "sara.vcf").write_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Sara Chen\nEMAIL:sara@example.com\nEND:VCARD\n",
        encoding="utf-8",
    )
    (contacts_dir / "omar.vcf").write_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Omar Rizvi\nEMAIL:omar@example.com\nEND:VCARD\n",
        encoding="utf-8",
    )

    cards = ContactReader().read_path(contacts_dir, RendererFileAccess(tmp_path / "notes.folio"))

    assert [card.full_name for card in cards] == ["Omar Rizvi", "Sara Chen"]
    assert all(card.source and card.source.endswith(".vcf") for card in cards)


def test_contact_reader_writes_normalized_vcard(tmp_path: Path) -> None:
    card = ContactReader().parse_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Sara Chen\nEMAIL:sara@example.com\nEND:VCARD\n"
    )[0]
    card.organization = "Northwind Labs"
    card.title = "Finance Lead"
    path = tmp_path / "sara.vcf"

    reader = ContactReader()
    reader.write_path(path, [card], RendererFileAccess(tmp_path / "notes.folio"))

    updated = path.read_text(encoding="utf-8")
    assert "FN:Sara Chen" in updated
    assert "ORG:Northwind Labs" in updated
    assert "TITLE:Finance Lead" in updated
