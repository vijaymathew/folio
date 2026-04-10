from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from folio.renderers.base import RendererFileAccess


@dataclass(slots=True)
class ContactCard:
    full_name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    organization: str | None = None
    title: str | None = None
    role: str | None = None
    addresses: list[str] = field(default_factory=list)
    note: str | None = None
    source: str | None = None
    index: int = 0


class ContactReaderError(RuntimeError):
    pass


class ContactReader:
    def read_path(self, path: Path, file_access: RendererFileAccess) -> list[ContactCard]:
        if not path.exists():
            raise ContactReaderError(f"Path not found: {path}")

        if path.is_dir():
            contacts: list[ContactCard] = []
            entries = [entry for entry in file_access.list_dir(path) if entry.is_file() and entry.suffix.lower() == ".vcf"]
            for entry in entries:
                cards = self.parse_text(file_access.read_text(entry))
                for index, card in enumerate(cards):
                    card.source = entry.name
                    card.index = index
                contacts.extend(cards)
            return contacts

        if path.suffix.lower() != ".vcf":
            raise ContactReaderError(f"Unsupported contact source: {path.name}. Expected a .vcf file or directory of .vcf files.")

        cards = self.parse_text(file_access.read_text(path))
        for index, card in enumerate(cards):
            card.source = path.name
            card.index = index
        return cards

    def write_path(self, path: Path, cards: list[ContactCard], file_access: RendererFileAccess) -> None:
        text = "\n".join(self.serialize_card(card) for card in cards).rstrip() + "\n"
        file_access.write_text(path, text)

    def serialize_card(self, card: ContactCard) -> str:
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{self._escape(card.full_name)}"]
        family, given = self._split_name(card.full_name)
        lines.append(f"N:{self._escape(family)};{self._escape(given)};;;")
        for email in card.emails:
            lines.append(f"EMAIL;TYPE=internet:{self._escape(email)}")
        for phone in card.phones:
            lines.append(f"TEL:{self._escape(phone)}")
        if card.organization:
            lines.append(f"ORG:{self._escape(card.organization)}")
        if card.title:
            lines.append(f"TITLE:{self._escape(card.title)}")
        if card.role:
            lines.append(f"ROLE:{self._escape(card.role)}")
        for address in card.addresses:
            lines.append(f"ADR:;;{self._escape(address)};;;;")
        if card.note:
            lines.append(f"NOTE:{self._escape(card.note)}")
        lines.append("END:VCARD")
        return "\n".join(lines)

    def parse_text(self, text: str) -> list[ContactCard]:
        cards: list[ContactCard] = []
        current: dict[str, object] | None = None

        for line in self._unfold_lines(text):
            stripped = line.strip()
            upper = stripped.upper()
            if upper == "BEGIN:VCARD":
                current = {}
                continue
            if upper == "END:VCARD":
                if current is not None:
                    cards.append(self._build_card(current))
                current = None
                continue
            if current is None or ":" not in stripped:
                continue

            raw_key, raw_value = stripped.split(":", 1)
            key = raw_key.split(";", 1)[0].upper()
            value = self._decode_value(raw_value)
            self._store_value(current, key, value)

        return cards

    def _unfold_lines(self, text: str) -> list[str]:
        unfolded: list[str] = []
        for line in text.splitlines():
            if line.startswith((" ", "\t")) and unfolded:
                unfolded[-1] += line[1:]
            else:
                unfolded.append(line)
        return unfolded

    def _decode_value(self, value: str) -> str:
        decoded = []
        index = 0
        while index < len(value):
            char = value[index]
            if char == "\\" and index + 1 < len(value):
                next_char = value[index + 1]
                if next_char in {"n", "N"}:
                    decoded.append("\n")
                elif next_char == ",":
                    decoded.append(",")
                elif next_char == ";":
                    decoded.append(";")
                else:
                    decoded.append(next_char)
                index += 2
                continue
            decoded.append(char)
            index += 1
        return "".join(decoded).strip()

    def _store_value(self, current: dict[str, object], key: str, value: str) -> None:
        if key in {"EMAIL", "TEL", "ADR"}:
            current.setdefault(key, []).append(value)
            return
        current[key] = value

    def _build_card(self, current: dict[str, object]) -> ContactCard:
        full_name = str(current.get("FN") or self._name_from_n(current.get("N")) or "Unnamed Contact")
        organization = self._join_parts(current.get("ORG"), " / ")
        title = self._clean_string(current.get("TITLE"))
        role = self._clean_string(current.get("ROLE"))
        note = self._clean_string(current.get("NOTE"))
        emails = self._values(current.get("EMAIL"))
        phones = self._values(current.get("TEL"))
        addresses = [self._format_address(item) for item in self._values(current.get("ADR"))]
        addresses = [item for item in addresses if item]
        return ContactCard(
            full_name=full_name,
            emails=emails,
            phones=phones,
            organization=organization,
            title=title,
            role=role,
            addresses=addresses,
            note=note,
        )

    def _name_from_n(self, raw_name: object) -> str | None:
        value = self._clean_string(raw_name)
        if value is None:
            return None
        parts = [part.strip() for part in value.split(";")]
        family = parts[0] if len(parts) > 0 else ""
        given = parts[1] if len(parts) > 1 else ""
        additional = parts[2] if len(parts) > 2 else ""
        prefix = parts[3] if len(parts) > 3 else ""
        suffix = parts[4] if len(parts) > 4 else ""
        ordered = [prefix, given, additional, family, suffix]
        name = " ".join(part for part in ordered if part)
        return name or None

    def _join_parts(self, value: object, separator: str) -> str | None:
        raw = self._clean_string(value)
        if raw is None:
            return None
        parts = [part.strip() for part in raw.split(";") if part.strip()]
        if not parts:
            return None
        return separator.join(parts)

    def _format_address(self, value: str) -> str:
        parts = [part.strip() for part in value.split(";") if part.strip()]
        return ", ".join(parts)

    def _values(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        cleaned = self._clean_string(value)
        return [cleaned] if cleaned else []

    def _clean_string(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _escape(self, value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(";", "\\;")
            .replace(",", "\\,")
        )

    def _split_name(self, full_name: str) -> tuple[str, str]:
        parts = [part for part in full_name.strip().split() if part]
        if not parts:
            return ("", "")
        if len(parts) == 1:
            return ("", parts[0])
        return (parts[-1], " ".join(parts[:-1]))
