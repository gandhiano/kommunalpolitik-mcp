"""CLI for ingesting public Witzenhausen SessionNet data."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .pdf_text import extract_pdf_text
from .sessionnet_client import SessionNetClient
from .sessionnet_parsers import (
    BASE_URL,
    parse_bodies,
    parse_meeting_detail,
    parse_meeting_list,
    parse_paper_detail,
)
from .sessionnet_repository import SessionNetRepository


DEFAULT_DATA_DIR = Path("data/witzenhausen")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest public Witzenhausen SessionNet data")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between live HTTP requests")
    parser.add_argument("--force", action="store_true", help="Ignore cached HTML/PDF files")
    parser.add_argument(
        "--allow-public-crawl",
        action="store_true",
        help="Required for commands that fetch public SessionNet pages",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    subparsers.add_parser("bodies")

    meetings = subparsers.add_parser("meetings")
    meetings.add_argument("--from-year", type=int, default=2026)
    meetings.add_argument("--to-year", type=int, default=2026)
    meetings.add_argument("--body-id", help="Only crawl one SessionNet body id")

    details = subparsers.add_parser("details")
    details.add_argument("--limit", type=int)
    details.add_argument("--meeting-id", help="Only parse a single meeting id")

    papers = subparsers.add_parser("papers")
    papers.add_argument("--limit", type=int)

    documents = subparsers.add_parser("documents")
    documents.add_argument("--limit", type=int)

    text = subparsers.add_parser("extract-text")
    text.add_argument("--limit", type=int)

    subparsers.add_parser("status")

    sync = subparsers.add_parser("sync")
    sync.add_argument("--from-year", type=int, default=2000)
    sync.add_argument("--to-year", type=int, default=date.today().year)
    sync.add_argument("--detail-limit", type=int, help="Maximum meeting detail pages to parse")
    sync.add_argument("--paper-limit", type=int, help="Maximum Vorlage detail pages to parse")
    sync.add_argument("--download-limit", type=int, help="Maximum PDFs to download")
    sync.add_argument("--text-limit", type=int, help="Maximum PDFs to extract text from")

    args = parser.parse_args()
    repo = _repo(args.data_dir)
    client = _client(args.data_dir, args.delay, not args.force)

    try:
        if args.command == "init-db":
            repo.init_schema()
            print(json.dumps({"database": str(repo.db_path), "status": "initialized"}, indent=2))
        elif args.command == "bodies":
            _require_crawl(args)
            print(json.dumps(command_bodies(repo, client, args.force), indent=2, ensure_ascii=False))
        elif args.command == "meetings":
            _require_crawl(args)
            print(json.dumps(command_meetings(repo, client, args.from_year, args.to_year, args.body_id, args.force), indent=2, ensure_ascii=False))
        elif args.command == "details":
            _require_crawl(args)
            print(json.dumps(command_details(repo, client, args.limit, args.meeting_id, args.force), indent=2, ensure_ascii=False))
        elif args.command == "papers":
            _require_crawl(args)
            print(json.dumps(command_papers(repo, client, args.limit, args.force), indent=2, ensure_ascii=False))
        elif args.command == "documents":
            _require_crawl(args)
            print(json.dumps(command_documents(repo, client, args.data_dir, args.limit, args.force), indent=2, ensure_ascii=False))
        elif args.command == "extract-text":
            print(json.dumps(command_extract_text(repo, args.data_dir, args.limit), indent=2, ensure_ascii=False))
        elif args.command == "status":
            repo.init_schema()
            print(json.dumps(repo.counts(), indent=2, ensure_ascii=False))
        elif args.command == "sync":
            _require_crawl(args)
            result = {
                "bodies": command_bodies(repo, client, args.force),
                "meetings": command_meetings(repo, client, args.from_year, args.to_year, None, args.force),
                "details": command_details(repo, client, args.detail_limit, None, args.force),
                "papers": command_papers(repo, client, args.paper_limit, args.force),
                "documents": command_documents(repo, client, args.data_dir, args.download_limit, args.force),
                "text": command_extract_text(repo, args.data_dir, args.text_limit),
                "counts": repo.counts(),
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        repo.close()


def command_bodies(repo: SessionNetRepository, client: SessionNetClient, force: bool) -> dict[str, int]:
    repo.init_schema()
    html = client.get_text("gr0040.asp?__cwpall=1&", force=force)
    bodies = parse_bodies(html, BASE_URL)
    return {"upserted": repo.upsert_bodies(bodies)}


def command_meetings(
    repo: SessionNetRepository,
    client: SessionNetClient,
    from_year: int,
    to_year: int,
    body_id: str | None,
    force: bool,
) -> dict[str, int]:
    repo.init_schema()
    total = 0
    bodies = [body for body in repo.bodies() if body_id is None or body["id"] == body_id]
    if not bodies:
        return {"upserted": 0, "bodies": 0}

    for body in bodies:
        for year in range(from_year, to_year + 1):
            path = f"si0046.asp?__cjahr={year}&__cmonat=1&__canz=12&smccont=85&__osidat=d&__ksigrnr={body['id']}&__cselect=65536"
            html = client.get_text(path, force=force)
            meetings = parse_meeting_list(html, body_id=body["id"], base_url=BASE_URL)
            for meeting in meetings:
                meeting["body_id"] = body["id"]
                meeting["body_name"] = body["name"]
            total += repo.upsert_meetings(meetings)
    return {"upserted": total, "bodies": len(bodies)}


def command_details(
    repo: SessionNetRepository,
    client: SessionNetClient,
    limit: int | None,
    meeting_id: str | None,
    force: bool,
) -> dict[str, int]:
    repo.init_schema()
    if meeting_id:
        rows = [repo.connection.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()]
        rows = [row for row in rows if row]
    else:
        rows = repo.meetings_without_details(limit)

    meetings = agenda_items = papers = documents = 0
    for row in rows:
        html = client.get_text(row["detail_url"], force=force)
        parsed = parse_meeting_detail(html, row["id"], BASE_URL)
        meeting = parsed["meeting"]
        meeting["body_id"] = row["body_id"]
        meetings += repo.upsert_meetings([meeting])
        agenda_items += repo.upsert_agenda_items(parsed["agenda_items"])
        papers += repo.upsert_papers(parsed["papers"])
        documents += repo.upsert_documents(parsed["documents"])
    return {"meetings": meetings, "agenda_items": agenda_items, "papers": papers, "documents": documents}


def command_papers(repo: SessionNetRepository, client: SessionNetClient, limit: int | None, force: bool) -> dict[str, int]:
    repo.init_schema()
    sql = "SELECT * FROM papers ORDER BY first_seen_at"
    params = ()
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    rows = repo.connection.execute(sql, params).fetchall()

    papers = documents = 0
    for row in rows:
        html = client.get_text(row["detail_url"], force=force)
        parsed = parse_paper_detail(html, row["id"], BASE_URL)
        papers += repo.upsert_papers([parsed["paper"]])
        documents += repo.upsert_documents(parsed["documents"])
    return {"papers": papers, "documents": documents}


def command_documents(
    repo: SessionNetRepository,
    client: SessionNetClient,
    data_dir: Path,
    limit: int | None,
    force: bool,
) -> dict[str, int]:
    repo.init_schema()
    rows = repo.documents_pending_download(limit)
    downloaded = 0
    pdf_dir = data_dir / "raw" / "pdf"
    for row in rows:
        extension = _extension_from_url(row["url"]) or ".pdf"
        target = pdf_dir / f"{row['id']}{extension}"
        sha256, size = client.download(row["url"], target, force=force)
        repo.mark_document_downloaded(row["id"], target, sha256, size)
        downloaded += 1
    return {"downloaded": downloaded}


def command_extract_text(repo: SessionNetRepository, data_dir: Path, limit: int | None) -> dict[str, int]:
    repo.init_schema()
    rows = repo.documents_pending_text(limit)
    text_dir = data_dir / "text"
    extracted = failed = 0
    for row in rows:
        file_path = Path(row["file_path"])
        try:
            text = _sanitize_text(extract_pdf_text(file_path))
        except Exception:
            failed += 1
            continue
        text_path = text_dir / f"{row['id']}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(text, encoding="utf-8")
        repo.save_document_text(row["id"], text_path, text)
        extracted += 1
    return {"extracted": extracted, "failed": failed}


def _sanitize_text(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _repo(data_dir: Path) -> SessionNetRepository:
    return SessionNetRepository(data_dir / "witzenhausen.sqlite")


def _client(data_dir: Path, delay: float, use_cache: bool) -> SessionNetClient:
    return SessionNetClient(BASE_URL, data_dir / "raw" / "html", delay_seconds=delay, use_cache=use_cache)


def _require_crawl(args: argparse.Namespace) -> None:
    if not args.allow_public_crawl:
        raise SystemExit("Refusing to fetch public SessionNet pages without --allow-public-crawl")


def _extension_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.path.endswith("getfile.asp") and parse_qs(parsed.query).get("type") == ["do"]:
        return ".pdf"
    path = parsed.path
    match = re.search(r"\.([a-zA-Z0-9]{2,5})$", path)
    return f".{match.group(1).lower()}" if match else None


if __name__ == "__main__":
    main()
