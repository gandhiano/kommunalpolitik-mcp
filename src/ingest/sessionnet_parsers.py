"""Parsers for Witzenhausen's public SessionNet HTML pages."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


BASE_URL = "https://sessionnet.owl-it.de/witzenhausen/BI/"


def parse_bodies(html: str, base_url: str = BASE_URL) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    bodies: dict[str, dict[str, str | None]] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        body_id = _query_value(href, "__kgrnr")
        if not body_id or "kp0040.asp" not in href:
            continue
        name = _clean_text(anchor.get_text(" "))
        if not name:
            continue

        bodies.setdefault(
            body_id,
            {
                "id": body_id,
                "name": name,
                "detail_url": urljoin(base_url, href),
                "meeting_list_url": None,
            },
        )

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        body_id = _query_value(href, "__ksigrnr")
        if body_id and body_id in bodies and "si0046.asp" in href:
            bodies[body_id]["meeting_list_url"] = urljoin(base_url, href)

    return sorted(bodies.values(), key=lambda row: row["name"] or "")


def parse_meeting_list(html: str, body_id: str | None = None, base_url: str = BASE_URL) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    meetings: dict[str, dict[str, str | None]] = {}
    page_title = _clean_text(soup.find("h1").get_text(" ")) if soup.find("h1") else ""
    default_body = page_title.split(" - Termine", 1)[0] if " - Termine" in page_title else None

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        meeting_id = _query_value(href, "__ksinr")
        if not meeting_id or "si0057.asp" not in href:
            continue

        title_attr = anchor.get("title") or ""
        text = _clean_text(anchor.get_text(" "))
        title, meeting_date = _parse_meeting_title(title_attr, text, default_body)
        context_lines = _nearby_lines(anchor)

        meetings[meeting_id] = {
            "id": meeting_id,
            "body_id": body_id,
            "body_name": title or default_body,
            "title": title or text or default_body or f"Sitzung {meeting_id}",
            "meeting_date": meeting_date,
            "meeting_time": _first_matching(context_lines, r"\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?\s*Uhr"),
            "location": _infer_location(context_lines),
            "detail_url": urljoin(base_url, href),
        }

    return list(meetings.values())


def parse_meeting_detail(html: str, meeting_id: str, base_url: str = BASE_URL) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.find("h1").get_text(" ")) if soup.find("h1") else f"Sitzung {meeting_id}"
    lines = _page_lines(soup)
    info = _parse_label_value_block(lines, ["Sitzung", "Gremium", "Raum", "Datum", "Zeit"])
    documents = parse_documents(html, source_type="meeting", source_id=meeting_id, base_url=base_url)

    return {
        "meeting": {
            "id": meeting_id,
            "body_id": None,
            "body_name": info.get("Gremium") or title.split(" - ", 1)[0],
            "title": title.split(" - ", 1)[0] if " - " in title else title,
            "meeting_date": _date_to_iso(info.get("Datum")),
            "meeting_time": info.get("Zeit"),
            "location": info.get("Raum"),
            "detail_url": urljoin(base_url, f"si0057.asp?__ksinr={meeting_id}"),
        },
        "agenda_items": _parse_agenda_items(lines, soup, meeting_id, base_url),
        "documents": documents,
        "papers": _parse_paper_links(soup, base_url),
    }


def parse_paper_detail(html: str, paper_id: str, base_url: str = BASE_URL) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.find("h1").get_text(" ")) if soup.find("h1") else f"Vorlage {paper_id}"
    reference_match = re.search(r"[A-ZÄÖÜ]{2,}/\d{1,4}/\d{4}", title)
    return {
        "paper": {
            "id": paper_id,
            "reference": reference_match.group(0) if reference_match else None,
            "title": title,
            "detail_url": urljoin(base_url, f"vo0050.asp?__kvonr={paper_id}"),
        },
        "documents": parse_documents(html, source_type="paper", source_id=paper_id, base_url=base_url),
    }


def parse_documents(html: str, source_type: str, source_id: str, base_url: str = BASE_URL) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    documents: dict[str, dict[str, str | None]] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "getfile.asp" not in href:
            continue
        file_id = _query_value(href, "id")
        if not file_id:
            continue
        name = _clean_text(anchor.get_text(" ")) or f"Dokument {file_id}"
        label = _infer_label(anchor)
        documents[file_id] = {
            "id": file_id,
            "source_type": source_type,
            "source_id": source_id,
            "document_type": classify_document(label, name),
            "label": label,
            "name": name,
            "url": urljoin(base_url, href),
        }

    return list(documents.values())


def classify_document(label: str | None, name: str) -> str:
    normalized = f"{label or ''} {name}".lower()
    if label == "NS" or "niederschrift" in normalized or "protokoll" in normalized:
        return "minutes"
    if label == "BM" or "bekanntmachung" in normalized:
        return "notice"
    if label == "VO" or "vorlage" in normalized:
        return "paper"
    if "änderungsantrag" in normalized or "aend.antrag" in normalized or "antrag" in normalized:
        return "motion"
    if "anlage" in normalized:
        return "attachment"
    return "other"


def _parse_agenda_items(lines: list[str], soup: BeautifulSoup, meeting_id: str, base_url: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    paper_by_reference = {
        _clean_text(anchor.get_text(" ")): urljoin(base_url, anchor["href"])
        for anchor in soup.find_all("a", href=True)
        if "vo0050.asp" in anchor["href"]
    }

    index = 0
    sort_order = 0
    while index < len(lines):
        match = re.match(r"^([ÖOEN])\s+([\d.]+)", lines[index])
        if not match:
            index += 1
            continue

        number = f"{match.group(1)} {match.group(2)}"
        title_parts: list[str] = []
        index += 1
        while index < len(lines) and not re.match(r"^([ÖOEN])\s+[\d.]+", lines[index]):
            line = lines[index]
            if line not in {"*BM*", "*VO*", "*NS*"} and not line.startswith("Software:"):
                title_parts.append(line)
            index += 1

        title = _clean_text(" ".join(title_parts))
        if not title:
            continue
        paper_reference = _first_paper_reference(title)
        items.append(
            {
                "id": f"{meeting_id}:{number.replace(' ', '-')}",
                "meeting_id": meeting_id,
                "number": number,
                "title": title,
                "paper_reference": paper_reference,
                "paper_url": paper_by_reference.get(paper_reference) if paper_reference else None,
                "public": number.startswith(("Ö", "O")),
                "sort_order": sort_order,
            }
        )
        sort_order += 1

    return items


def _parse_paper_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, str | None]]:
    papers: dict[str, dict[str, str | None]] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "vo0050.asp" not in href:
            continue
        paper_id = _query_value(href, "__kvonr")
        if not paper_id:
            continue
        reference = _clean_text(anchor.get_text(" ")) or None
        title = anchor.get("title") or reference or f"Vorlage {paper_id}"
        title = title.replace("Vorlage anzeigen:", "").strip()
        papers[paper_id] = {
            "id": paper_id,
            "reference": reference,
            "title": title,
            "detail_url": urljoin(base_url, href),
        }
    return list(papers.values())


def _query_value(href: str, name: str) -> str | None:
    values = parse_qs(urlparse(href).query).get(name)
    return values[0] if values else None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _page_lines(soup: BeautifulSoup) -> list[str]:
    text = soup.get_text("\n")
    return [_clean_text(line) for line in text.splitlines() if _clean_text(line)]


def _nearby_lines(anchor) -> list[str]:
    parent = anchor.find_parent(["tr", "li", "div"])
    if not parent:
        parent = anchor.parent
    return [_clean_text(line) for line in parent.get_text("\n").splitlines() if _clean_text(line)]


def _parse_meeting_title(title_attr: str, text: str, default_body: str | None) -> tuple[str | None, str | None]:
    candidate = title_attr.replace("Details anzeigen:", "").strip() or text
    match = re.search(r"(.+?)\s+(\d{2}\.\d{2}\.\d{4})", candidate)
    if match:
        return _clean_text(match.group(1)), _date_to_iso(match.group(2))
    return text or default_body, None


def _parse_label_value_block(lines: list[str], labels: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    label_set = set(labels)
    for index, line in enumerate(lines[:-1]):
        if line in label_set and lines[index + 1] not in label_set:
            result[line] = lines[index + 1]
    return result


def _date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", value)
    if not match:
        return value
    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"


def _first_matching(lines: list[str], pattern: str) -> str | None:
    for line in lines:
        match = re.search(pattern, line)
        if match:
            return match.group(0)
    return None


def _infer_location(lines: list[str]) -> str | None:
    for line in lines:
        if "Uhr" not in line and any(token in line for token in ["Rathaus", "Saal", "Haus", "Generationentreff", "Dorfgemeinschaftshaus"]):
            return line
    return None


def _infer_label(anchor) -> str | None:
    snippets: list[str] = []
    previous = anchor.find_previous(string=True)
    if previous:
        snippets.append(str(previous))
    parent_text = anchor.parent.get_text(" ") if anchor.parent else ""
    snippets.append(parent_text)
    text = " ".join(snippets)
    match = re.search(r"\*(BM|VO|NS)\*", text)
    return match.group(1) if match else None


def _first_paper_reference(value: str) -> str | None:
    match = re.search(r"[A-ZÄÖÜ]{2,}/\d{1,4}/\d{4}", value)
    return match.group(0) if match else None
