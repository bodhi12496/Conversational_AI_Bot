import csv
import hashlib
import io
import math
import re
import zipfile
from datetime import date
from pathlib import Path

from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import Column, Metric, View
from app.repository import Repository, now, uid


def identifier(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    if not value or not value[0].isalpha():
        value = "field_" + value
    return value[:63]


def quote(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
        raise DomainError("Invalid internal identifier.")
    return '"' + name + '"'


def parse_upload(content: bytes, filename: str, settings: Settings):
    if len(content) > settings.max_upload_bytes:
        raise DomainError("File exceeds the 5 MiB upload limit.", 413)
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            reader = csv.reader(io.StringIO(content.decode("utf-8-sig")))
            raw_headers = next(reader, [])
            rows = []
            for row in reader:
                if not any(str(v).strip() for v in row):
                    continue
                if len(row) != len(raw_headers):
                    raise DomainError("Every CSV row must have the same number of fields as its header.")
                rows.append(row)
                if len(rows) > settings.max_rows:
                    raise DomainError("At most 25,000 rows are supported per upload.", 413)
        elif suffix == ".xlsx":
            from openpyxl import load_workbook

            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 30 * 1024 * 1024:
                    raise DomainError("Expanded XLSX exceeds the 30 MiB limit.", 413)
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
            try:
                if len(book.worksheets) != 1:
                    raise DomainError("Use one worksheet per file so the source is unambiguous.")
                sheet = book.worksheets[0]
                if sheet.max_column > settings.max_columns or sheet.max_row > settings.max_rows + 1:
                    raise DomainError("XLSX exceeds the row or column limit.", 413)
                rows = []
                raw_headers = None
                for cells in sheet.iter_rows():
                    if any(c.data_type == "f" for c in cells):
                        raise DomainError("Export calculated values before uploading formulas.")
                    values = [c.value for c in cells]
                    if raw_headers is None:
                        raw_headers = values
                    elif any(v is not None for v in values):
                        rows.append(values)
            finally:
                book.close()
        else:
            raise DomainError("Supported uploads: UTF-8 CSV and single-sheet XLSX.")
    except DomainError:
        raise
    except (ValueError, UnicodeError, csv.Error, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise DomainError("Cannot read this file. Check its format and encoding.") from exc
    if not raw_headers or any(v is None or not str(v).strip() for v in raw_headers):
        raise DomainError("Every column needs a non-empty header.")
    headers = [identifier(str(v)) for v in raw_headers]
    if len(headers) != len(set(headers)):
        raise DomainError("Column headers collide after normalization. Rename the duplicates.")
    if len(headers) > settings.max_columns:
        raise DomainError("At most 100 columns are supported.", 413)
    if not rows:
        raise DomainError("The dataset has no data rows.")
    cleaned = [[None if v is None or str(v).strip() == "" else str(v).strip() for v in row] for row in rows]
    if any(len(str(v)) > 10000 for row in cleaned for v in row if v is not None):
        raise DomainError("Cell values must be shorter than 10,000 characters.")
    columns = []
    for i, name in enumerate(headers):
        values = [row[i] for row in cleaned if row[i] is not None]
        dtype = "text"
        is_identifier = name == "id" or name.endswith("_id") or name.endswith("_code")
        if values and not is_identifier:
            if all(re.fullmatch(r"-?(0|[1-9][0-9]*)", v) for v in values):
                if all(-(2**63) < int(v) < 2**63 for v in values):
                    dtype = "integer"
            elif all(_finite_number(v) for v in values):
                dtype = "number"
            elif all(_iso_date(v) for v in values):
                dtype = "date"
        if dtype in ("integer", "number"):
            for row in cleaned:
                if row[i] is not None:
                    row[i] = int(row[i]) if dtype == "integer" else float(row[i])
        sensitive = bool(re.search(r"(^|_)(email|phone|ssn|password|token|salary|address|dob)(_|$)", name))
        distinct = len(set(values))
        columns.append(
            Column(
                name=name,
                source_name=str(raw_headers[i]),
                dtype=dtype,
                description=f"Inferred from uploaded column '{raw_headers[i]}'; business meaning unconfirmed.",
                null_count=len(cleaned) - len(values),
                distinct_count=distinct,
                candidate_key=len(values) == len(cleaned) and distinct == len(cleaned),
                sensitive=sensitive,
            )
        )
    return columns, cleaned


def _finite_number(v):
    try:
        return math.isfinite(float(v))
    except (ValueError, OverflowError):
        return False


def _iso_date(v):
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def ingest(repo: Repository, settings: Settings, project_id: str, content: bytes, filename: str):
    columns, rows = parse_upload(content, filename, settings)
    dataset_id = "data_" + uid()
    view_id = identifier(Path(filename).stem)
    with repo.connection(write=True) as conn:
        project = repo.project(conn, project_id)
        model = repo.version(conn, project_id)
        if len(model.views) >= settings.max_views:
            raise DomainError("This version supports up to 12 views per project.")
        existing = {v.id for v in model.views}
        original = view_id
        n = 2
        while view_id in existing:
            view_id = original[:58] + "_" + str(n)
            n += 1
        definitions = ",".join(
            quote(c.name) + " " + {"integer": "INTEGER", "number": "REAL"}.get(c.dtype, "TEXT")
            for c in columns
        )
        conn.execute(f"CREATE TABLE {quote(dataset_id)} ({definitions})")
        conn.executemany(f"INSERT INTO {quote(dataset_id)} VALUES ({','.join('?' for _ in columns)})", rows)
        conn.execute(
            "INSERT INTO datasets VALUES(?,?,?,?,?,?,?)",
            (
                dataset_id,
                project_id,
                view_id,
                Path(filename).name,
                len(rows),
                hashlib.sha256(content).hexdigest(),
                now(),
            ),
        )
        metrics = [
            Metric(
                name="row_count",
                aggregation="count",
                expression="*",
                description="Number of uploaded rows after view filters.",
                unit="rows",
                confirmed=True,
            )
        ]
        for c in columns:
            if c.dtype in ("integer", "number") and not c.sensitive:
                metrics.append(
                    Metric(
                        name=("total_" + c.name)[:63],
                        aggregation="sum",
                        expression=c.name,
                        description=f"Suggested sum of {c.name}. Confirm additivity and units.",
                    )
                )
        model.views.append(
            View(
                id=view_id, dataset_id=dataset_id, name=Path(filename).stem, columns=columns, metrics=metrics
            )
        )
        model.selected_views.append(view_id)
        version = repo.add_version(
            conn, project_id, model, f"Imported {Path(filename).name}", project["head"]
        )
        return {
            "view_id": view_id,
            "version": version,
            "row_count": len(rows),
            "columns": [c.model_dump() for c in columns],
        }
