"""Read original hand texts from another tracker's PostgreSQL database.

Supported: PokerTracker 4 ('pt4') and Holdem Manager 3 ('hm3'). Hand texts are
fed through OHM's own parsers, so nothing here understands hand structure.

DB access goes through two tiny interfaces (TrackerServer / TrackerConn) so the
logic is testable without a PostgreSQL server; psycopg2 is imported lazily. Imports
stream the hand texts through a server-side cursor (iter_hand_batches), so a big
database is never loaded into memory at once. Tables are looked up in the `public`
schema and names keep their real case (quoted in SQL).

SCHEMA STATUS
  PT4: table names/columns below come from memory of PT4's public schema
       (cash_hand_histories.history, cash_hand_summary.date_played, joined on
       id_hand). UNVERIFIED against a real database; discovery via
       information_schema falls back to any text column containing "history".
  HM3: ALL UNVERIFIED. The H2N spec treats HM3 as a file DB, but HM3 is believed to
       be PostgreSQL-backed like HM2 (handhistories.handhistory, possibly
       compressed). Candidates are discovered at runtime; bytes values are tried
       as gzip, zlib, then plain text.
"""

from __future__ import annotations

import gzip
import zlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Protocol

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5432
DEFAULT_USER = "postgres"
DEFAULT_PASSWORDS = {"pt4": "dbpass", "hm3": "postgrespass"}  # stock credentials
HIDDEN_DATABASES = {"postgres", "template0", "template1"}
CONNECT_TIMEOUT = 5
SCHEMA = "public"  # where both trackers keep their tables
ITERSIZE = 2000  # rows per round trip of the server-side cursor


class TrackerError(Exception):
    """A problem with the tracker database, message safe to show to the user."""


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    user: str
    password: str

    @property
    def where(self) -> str:
        return f"{self.host}:{self.port}"


def make_connection(software: str, host=None, port=None, user=None, password=None) -> Connection:
    """Blank (None or empty) fields mean the stock default, password included."""
    if software not in DEFAULT_PASSWORDS:
        raise TrackerError(f"Unsupported tracker: {software}")
    return Connection(
        host=(host or "").strip() or DEFAULT_HOST,
        port=int(port or DEFAULT_PORT),
        user=(user or "").strip() or DEFAULT_USER,
        password=password or DEFAULT_PASSWORDS[software],
    )


def redact(message: str, conn: Connection) -> str:
    """Never let the password reach a message."""
    if conn.password:
        message = message.replace(conn.password, "***")
    return message


# ── DB interface ─────────────────────────────────────────────────────────────
class TrackerConn(Protocol):
    def query(self, sql: str, params: tuple = ()) -> list[tuple]: ...
    def stream(self, sql: str, params: tuple = (), itersize: int = ITERSIZE) -> Iterator[tuple]:
        """Rows of a big SELECT, fetched `itersize` at a time (server-side cursor)."""
        ...
    def close(self) -> None: ...


class TrackerServer(Protocol):
    def list_databases(self) -> list[str]: ...
    def open(self, dbname: str) -> TrackerConn: ...
    def close(self) -> None: ...


class _PgConn:
    def __init__(self, raw):
        self._raw = raw

    def query(self, sql, params=()):
        with self._raw.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def stream(self, sql, params=(), itersize=ITERSIZE):
        # A named (server-side) cursor: PostgreSQL sends itersize rows per round trip
        # instead of the whole result. Named cursors need a transaction (no autocommit).
        raw = self._raw
        raw.autocommit = False
        try:
            with raw.cursor(name="ohm_hand_texts") as cur:
                cur.itersize = itersize
                cur.execute(sql, params)
                for row in cur:
                    yield row
        finally:
            try:
                raw.rollback()  # read-only: nothing to keep
                raw.autocommit = True
            except Exception:
                pass

    def close(self):
        self._raw.close()


class _PgServer:
    def __init__(self, conn: Connection):
        self._c = conn

    def _raw(self, dbname):
        try:
            import psycopg2  # lazy: the app must start without it
        except ImportError as e:
            raise TrackerError("PostgreSQL support is not installed (psycopg2)") from e
        try:
            raw = psycopg2.connect(
                host=self._c.host, port=self._c.port, user=self._c.user,
                password=self._c.password, dbname=dbname, connect_timeout=CONNECT_TIMEOUT,
            )
        except Exception as e:
            msg = redact(str(e), self._c)
            if "password authentication failed" in msg:
                raise TrackerError(f"Wrong user name or password for {self._c.where}") from None
            raise TrackerError(f"Could not connect to {self._c.where}") from None
        raw.set_session(readonly=True, autocommit=True)
        return raw

    def list_databases(self):
        raw = self._raw("postgres")
        try:
            with raw.cursor() as cur:
                cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname")
                return [r[0] for r in cur.fetchall()]
        finally:
            raw.close()

    def open(self, dbname):
        return _PgConn(self._raw(dbname))

    def close(self):
        pass


def connect_server(conn: Connection) -> TrackerServer:
    """Factory; tests monkeypatch this with a fake."""
    return _PgServer(conn)


# ── schema discovery ─────────────────────────────────────────────────────────
@dataclass
class HandSource:
    """Names as they are in the database (case kept: they are quoted in SQL)."""
    table: str
    text_col: str
    date_table: str | None = None  # table holding the hand date (== table when same)
    date_col: str | None = None
    join_col: str | None = None  # column shared by table and date_table when they differ
    schema: str = SCHEMA


# (software) -> candidate layouts, first match wins
_PT4 = dict(table="cash_hand_histories", text="history", id_col="id_hand",
            date_table="cash_hand_summary", date_col="date_played")
_HM3_TABLE = "handhistories"  # UNVERIFIED
_HM3_TEXT = ("handhistory", "history", "hand_history", "handtext")
_HM3_DATE = ("handtimestamp", "handtimestamp_utc", "date_played", "timestamp")
_HM3_ID = ("handhistory_id", "gamenumber", "id_hand", "id")


_TEXT_TYPES = ("text", "character varying", "bytea")


def _table(db: TrackerConn, table: str) -> tuple[str, dict[str, tuple[str, str]]] | None:
    """(real table name, {lowercased column name: (real name, data type)}) of a table in the
    tracker's schema, matched case-insensitively; None when there is no such table."""
    rows = db.query(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = %s AND lower(table_name) = %s",
        (SCHEMA, table.lower()),
    )
    if not rows:
        return None
    real = rows[0][0]
    return real, {r[1].lower(): (r[1], (r[2] or "").lower()) for r in rows if r[0] == real}


def _text_col(cols: dict[str, tuple[str, str]], preferred: tuple[str, ...]) -> str | None:
    for c in preferred:
        if c in cols:
            return cols[c][0]
    return next((real for low, (real, t) in cols.items() if "history" in low and t in _TEXT_TYPES), None)


def discover(db: TrackerConn, software: str) -> HandSource | None:
    """Locate the hand text column (and a date column) or None when the DB is not this tracker's."""
    if software == "pt4":
        found = _table(db, _PT4["table"])
        if found is None:
            return None
        table, cols = found
        text_col = _text_col(cols, (_PT4["text"],))
        if text_col is None:
            return None
        src = HandSource(table, text_col)
        summary = _table(db, _PT4["date_table"])
        if summary is not None:
            stable, scols = summary
            if _PT4["date_col"] in scols and _PT4["id_col"] in cols and _PT4["id_col"] in scols \
                    and cols[_PT4["id_col"]][0] == scols[_PT4["id_col"]][0]:
                src.date_table, src.date_col, src.join_col = (
                    stable, scols[_PT4["date_col"]][0], cols[_PT4["id_col"]][0])
        return src
    if software == "hm3":
        found = _table(db, _HM3_TABLE)
        if found is None:
            return None
        table, cols = found
        text_col = _text_col(cols, _HM3_TEXT)
        if text_col is None:
            return None
        src = HandSource(table, text_col)
        date_col = next((cols[c][0] for c in _HM3_DATE if c in cols), None)
        if date_col:
            src.date_table, src.date_col = table, date_col
        return src
    raise TrackerError(f"Unsupported tracker: {software}")


def _ident(name: str) -> str:
    """Quoted identifier, case kept (PostgreSQL folds unquoted names, not quoted ones)."""
    if not name or not name.replace("_", "").isalnum():
        raise TrackerError("Unexpected column name in the database")
    return f'"{name}"'


def _qualified(schema: str, table: str) -> str:
    return f"{_ident(schema)}.{_ident(table)}"


def build_query(src: HandSource, date_from: str | None, date_to: str | None, limit: int | None = None,
                *, order: bool = True):
    """SELECT for hand texts, with the date range applied in SQL when the date is known.

    date_from/date_to are ISO dates (inclusive); returns (sql, params). PT4 dates live in
    the summary table: it is LEFT JOINed, so a hand without a summary row is still read.
    Its date is unknown in SQL, so a date range keeps it too (the import then filters on the
    date in the hand text)."""
    t, tc = _qualified(src.schema, src.table), _ident(src.text_col)
    sql = f"SELECT h.{tc} FROM {t} h"
    where, params = [], []
    if src.date_col and src.date_table:
        dc = _ident(src.date_col)
        nullable = False
        if src.date_table == src.table:
            dref = f"h.{dc}"
        else:
            j = _ident(src.join_col)
            sql += f" LEFT JOIN {_qualified(src.schema, src.date_table)} s ON s.{j} = h.{j}"
            dref = f"s.{dc}"
            nullable = True
        conds = []
        if date_from:
            conds.append(f"{dref} >= %s")
            params.append(date_from)
        if date_to:
            conds.append(f"{dref} < %s")
            params.append((date.fromisoformat(date_to) + timedelta(days=1)).isoformat())
        if conds:
            cond = " AND ".join(conds)
            where.append(f"({cond} OR {dref} IS NULL)" if nullable else cond)
        sql_order = f" ORDER BY {dref} NULLS LAST" if order else ""
    else:
        sql_order = ""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += sql_order
    if limit:
        sql += f" LIMIT {int(limit)}"
    return sql, tuple(params)


def decode_text(value) -> str | None:
    """Hand text from a text column or a (possibly compressed) bytes column."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raw = bytes(value)
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError, zlib.error):
            pass
    else:
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
    return raw.decode("utf-8", errors="replace")


def _clean(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\x00", "").strip()


def probe(db: TrackerConn, src: HandSource) -> bool:
    """Read one hand; True when it decodes to non-empty text."""
    sql, params = build_query(src, None, None, limit=1, order=False)
    rows = db.query(sql, params)
    return bool(rows) and bool(decode_text(rows[0][0]))


def count_hands(db: TrackerConn, src: HandSource, date_from: str | None = None,
                date_to: str | None = None) -> int:
    if not date_from and not date_to:
        return int(db.query(f"SELECT COUNT(*) FROM {_qualified(src.schema, src.table)}")[0][0])
    sql, params = build_query(src, date_from, date_to, order=False)
    return int(db.query(f"SELECT COUNT(*) FROM ({sql}) q", params)[0][0])


def list_databases(software: str, conn: Connection) -> tuple[list[dict], str | None]:
    """(databases, error). Never raises."""
    try:
        server = connect_server(conn)
        names = [n for n in server.list_databases() if n.lower() not in HIDDEN_DATABASES]
    except TrackerError as e:
        return [], redact(str(e), conn)
    except Exception:
        return [], f"Could not connect to {conn.where}"
    found: list[dict] = []
    for name in names:
        try:
            db = server.open(name)
        except Exception:
            continue
        try:
            src = discover(db, software)
            if src is None or not probe(db, src):
                continue
            found.append({"name": name, "hands": count_hands(db, src)})
        except Exception:
            continue
        finally:
            db.close()
    return found, None


def _open(software: str, conn: Connection, database: str):
    try:
        server = connect_server(conn)
        return server.open(database)
    except TrackerError as e:
        raise TrackerError(redact(str(e), conn)) from None
    except Exception:
        raise TrackerError(f"Could not connect to {conn.where}") from None


def _source(db: TrackerConn, software: str, database: str, date_from, date_to) -> HandSource:
    src = discover(db, software)
    if src is None:
        raise TrackerError(f'"{database}" is not a {"PokerTracker 4" if software == "pt4" else "Holdem Manager 3"} database')
    try:
        for d in (date_from, date_to):
            if d:
                date.fromisoformat(d)
    except ValueError:
        raise TrackerError("Invalid date, expected YYYY-MM-DD") from None
    return src


def count_source(software: str, conn: Connection, database: str,
                 date_from: str | None = None, date_to: str | None = None) -> int:
    """Hands an import of this database (and SQL date range) will read. Raises TrackerError
    (connection, not this tracker's database, bad date): checked before the import streams."""
    db = _open(software, conn, database)
    try:
        src = _source(db, software, database, date_from, date_to)
        try:
            return count_hands(db, src, date_from, date_to)
        except Exception as e:
            raise TrackerError(redact(f"Could not read hands: {e}", conn)) from None
    finally:
        db.close()


def iter_hand_batches(software: str, conn: Connection, database: str,
                      date_from: str | None = None, date_to: str | None = None,
                      batch: int = ITERSIZE) -> Iterator[list[str]]:
    """Hand texts in lists of up to `batch`, streamed from the server (never all in memory).
    The connection is closed when the generator ends or is closed."""
    db = _open(software, conn, database)
    try:
        src = _source(db, software, database, date_from, date_to)
        sql, params = build_query(src, date_from, date_to)
        out: list[str] = []
        rows = db.stream(sql, params, batch)
        try:
            for (value,) in rows:
                text = decode_text(value)
                if text:
                    text = _clean(text)
                    if text:
                        out.append(text)
                        if len(out) >= batch:
                            yield out
                            out = []
        except TrackerError:
            raise
        except GeneratorExit:
            raise
        except Exception as e:
            raise TrackerError(redact(f"Could not read hands: {e}", conn)) from None
        finally:
            close = getattr(rows, "close", None)
            if close:
                close()
        if out:
            yield out
    finally:
        db.close()


def iter_hand_texts(software: str, conn: Connection, database: str,
                    date_from: str | None = None, date_to: str | None = None) -> Iterator[str]:
    for texts in iter_hand_batches(software, conn, database, date_from, date_to):
        yield from texts
