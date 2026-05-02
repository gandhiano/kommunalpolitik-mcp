"""Chunking and actor mention extraction for local SessionNet text."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


ACTION_VERBS = [
    "beantragt",
    "beantragte",
    "fragt",
    "fragte",
    "bittet",
    "bat",
    "merkt an",
    "merkte an",
    "kritisiert",
    "kritisierte",
    "schlägt vor",
    "schlug vor",
    "berichtet",
    "berichtete",
    "erläutert",
    "erläuterte",
    "nimmt Stellung",
    "nahm Stellung",
    "stellt",
    "stellte",
]

PARTY_PATTERNS = [
    "SPD",
    "CDU",
    "FWG",
    "FDP",
    "Bündnis 90/Die Grünen",
    "Grüne",
    "DIE LINKE",
    "Die Linke",
    "Bunte Liste",
]


def chunk_document(row: Any, max_chars: int = 1400) -> list[dict[str, Any]]:
    """Split extracted document text into page-aware chunks."""

    text = row["text"] or ""
    pages = _split_pages(text)
    chunks: list[dict[str, Any]] = []
    chunk_index = 0
    for page_number, page_text in pages:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", page_text) if paragraph.strip()]
        current = ""
        for paragraph in paragraphs:
            paragraph = re.sub(r"\s+", " ", paragraph).strip()
            if not paragraph:
                continue
            if current and len(current) + len(paragraph) + 2 > max_chars:
                chunks.append(_chunk_row(row, page_number, chunk_index, current))
                chunk_index += 1
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            chunks.append(_chunk_row(row, page_number, chunk_index, current))
            chunk_index += 1

    return chunks


def extract_actor_mentions(chunk: Any, faction_names: Iterable[str]) -> list[dict[str, Any]]:
    """Extract lightweight person/faction mentions from one chunk.

    This is heuristic by design. It marks explicit action verbs as stronger
    evidence and plain nearby mentions as weaker evidence.
    """

    text = chunk["text"] or ""
    mentions: list[dict[str, Any]] = []
    for actor_name, actor_type in _candidate_actors(text, faction_names):
        verb = _nearby_action_verb(text, actor_name)
        confidence = "strong" if verb else "weak"
        mentions.append(
            {
                "id": _mention_id(chunk["id"], actor_name, actor_type, verb),
                "actor_name": actor_name,
                "actor_type": actor_type,
                "verb": verb,
                "confidence": confidence,
                "document_id": chunk["document_id"],
                "chunk_id": chunk["id"],
                "source_type": chunk["source_type"],
                "source_id": chunk["source_id"],
                "document_type": chunk["document_type"],
                "document_name": chunk["document_name"],
                "body_name": chunk["body_name"],
                "meeting_date": chunk["meeting_date"],
                "snippet": _snippet(text, actor_name),
            }
        )
    return mentions


def _split_pages(text: str) -> list[tuple[int | None, str]]:
    parts = re.split(r"\n*--- Seite (\d+) ---\n*", text)
    if len(parts) == 1:
        return [(None, text)]

    pages: list[tuple[int | None, str]] = []
    prefix = parts[0].strip()
    if prefix:
        pages.append((None, prefix))
    for index in range(1, len(parts), 2):
        pages.append((int(parts[index]), parts[index + 1]))
    return pages


def _chunk_row(row: Any, page_number: int | None, chunk_index: int, text: str) -> dict[str, Any]:
    document_id = row["id"]
    return {
        "id": f"{document_id}:{chunk_index}",
        "document_id": document_id,
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "document_type": row["document_type"],
        "document_name": row["document_name"],
        "body_name": row["body_name"],
        "meeting_date": row["meeting_date"],
        "page_number": page_number,
        "chunk_index": chunk_index,
        "text": text,
    }


def _candidate_actors(text: str, faction_names: Iterable[str]) -> list[tuple[str, str]]:
    candidates: dict[tuple[str, str], None] = {}

    for match in re.finditer(r"\b(?:Herr|Frau)\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+){0,2})", text):
        name = _clean_actor_name(match.group(1))
        if name:
            candidates[(name, "person")] = None

    for name in list(faction_names) + PARTY_PATTERNS:
        if name and re.search(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE):
            actor_type = "faction" if "fraktion" in name.lower() else "party"
            candidates[(name, actor_type)] = None

    for match in re.finditer(r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-/ ]+?-Fraktion)\b", text):
        candidates[(_clean_actor_name(match.group(1)), "faction")] = None

    return list(candidates.keys())


def _clean_actor_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" ,.;:()")
    value = re.sub(r"\b(fragt|beantragt|bittet|berichtet|erläutert|stellt)\b.*$", "", value, flags=re.IGNORECASE).strip()
    return value


def _nearby_action_verb(text: str, actor_name: str) -> str | None:
    match = re.search(re.escape(actor_name), text, flags=re.IGNORECASE)
    if not match:
        return None
    window = text[match.start() : match.start() + 260].lower()
    for verb in ACTION_VERBS:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in verb.lower().split()) + r"\b"
        if re.search(pattern, window):
            return verb
    return None


def _snippet(text: str, actor_name: str, radius: int = 450) -> str:
    match = re.search(re.escape(actor_name), text, flags=re.IGNORECASE)
    if not match:
        return text[: radius * 2].strip()
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()


def _mention_id(chunk_id: str, actor_name: str, actor_type: str, verb: str | None) -> str:
    raw = f"{chunk_id}|{actor_type}|{actor_name}|{verb or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
