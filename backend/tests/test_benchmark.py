"""Benchmark test for import pipeline throughput.

Uses real GGPoker hand histories (bench_sample_20k.txt) for realistic measurement.
Results are appended to tests/benchmark_log.jsonl so regressions are visible.
Run: cd backend && python -m pytest tests/test_benchmark.py -v -s
"""

import json
import time
import pytest
import duckdb
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.parsers.ggpoker import parse_hand_history
from app.stat_flags import compute_stat_flags
from app.api.import_hands import (
    _flush_batch, _compute_financials, reset_import_cache, split_hands, BATCH_SIZE,
)
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures"
BENCH_LOG = Path(__file__).parent / "benchmark_log.jsonl"
BENCH_SAMPLE = FIXTURES / "bench_sample_20k.txt"


def _load_real_hands() -> list[str]:
    """Load real GGPoker hands from bench_sample_20k.txt fixture."""
    if not BENCH_SAMPLE.exists():
        pytest.skip("bench_sample_20k.txt not found — run with real sample data")
    text = BENCH_SAMPLE.read_text()
    hands = [h.strip() for h in split_hands(text) if h.strip()]
    assert len(hands) > 10000, f"Expected >10000 hands, got {len(hands)}"
    return hands


def _log_result(name: str, n: int, batch_size: int, hps: float,
                t_total: float, t_parse: float, t_stats: float, t_db: float,
                **extra) -> None:
    """Append benchmark result to JSONL log file."""
    entry = {
        "h_per_sec": round(hps),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "name": name,
        "hands": n,
        "total_ms": round(t_total * 1000),
        "parse_ms": round(t_parse * 1000),
        "stats_ms": round(t_stats * 1000),
        "db_ms": round(t_db * 1000),
        "batch": batch_size,
    }
    with open(BENCH_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _print_result(label: str, n: int, batch_size: int,
                  t_total: float, t_parse: float, t_stats: float, t_db: float) -> None:
    hps = n / t_total if t_total > 0 else 0
    print(f"\n{'='*60}")
    print(f"  {label}: {n} hands (batch={batch_size})")
    print(f"  Total:  {t_total*1000:.0f}ms  ({hps:.0f} h/s)")
    print(f"  Parse:  {t_parse*1000:.0f}ms  ({t_parse/t_total*100:.0f}%)")
    print(f"  Stats:  {t_stats*1000:.0f}ms  ({t_stats/t_total*100:.0f}%)")
    print(f"  DB:     {t_db*1000:.0f}ms  ({t_db/t_total*100:.0f}%)")
    print(f"  Per-hand: parse={t_parse/n*1000:.2f}ms  stats={t_stats/n*1000:.2f}ms  db={t_db/n*1000:.3f}ms")
    print(f"{'='*60}")


def _run_import(db, hands: list[str], *, rebuild=False, in_transaction=False,
                disable_equity=False):
    """Run parse→stats→flush pipeline. Returns (imported, t_parse, t_stats, t_db)."""
    t_parse = 0.0
    t_stats = 0.0
    t_db = 0.0
    total_imported = 0
    pending = []

    ctx = patch("app.api.import_hands._calc_equity", None) if disable_equity else _noop_ctx()
    with ctx:
        for item in hands:
            if isinstance(item, tuple):
                hand_id, raw_text = item
            else:
                raw_text = item

            t0 = time.perf_counter()
            parsed = parse_hand_history(raw_text)
            t1 = time.perf_counter()
            stats = compute_stat_flags(parsed)
            t2 = time.perf_counter()
            financials = _compute_financials(parsed)
            t3 = time.perf_counter()
            t_parse += t1 - t0
            t_stats += t2 - t1 + (t3 - t2)
            pending.append((parsed, stats, financials))

            if len(pending) >= BATCH_SIZE:
                t0 = time.perf_counter()
                imp, errs, _ = _flush_batch(db, pending, rebuild=rebuild,
                                            in_transaction=in_transaction)
                t_db += time.perf_counter() - t0
                total_imported += imp
                pending = []

        if pending:
            t0 = time.perf_counter()
            imp, errs, _ = _flush_batch(db, pending, rebuild=rebuild,
                                        in_transaction=in_transaction)
            t_db += time.perf_counter() - t0
            total_imported += imp

    return total_imported, t_parse, t_stats, t_db


class _noop_ctx:
    def __enter__(self): return self
    def __exit__(self, *a): pass


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestBenchmark:
    def test_import_real_hands(self, db):
        """Import 20k real GGPoker hands with equity calculation."""
        hands = _load_real_hands()
        n = len(hands)

        total_imported, t_parse, t_stats, t_db = _run_import(db, hands)
        t_total = t_parse + t_stats + t_db
        hps = n / t_total if t_total > 0 else 0

        _print_result("Import (real, with equity)", n, BATCH_SIZE, t_total, t_parse, t_stats, t_db)
        _log_result("import_real", n, BATCH_SIZE, hps, t_total, t_parse, t_stats, t_db)

        assert total_imported == n
        assert hps > 100, f"Too slow: {hps:.0f} h/s (expected >100)"

    def test_import_no_equity(self, db):
        """Import 20k real hands without equity (isolates parse+stats+DB)."""
        hands = _load_real_hands()
        n = len(hands)

        total_imported, t_parse, t_stats, t_db = _run_import(
            db, hands, disable_equity=True)
        t_total = t_parse + t_stats + t_db
        hps = n / t_total if t_total > 0 else 0

        _print_result("Import (real, no equity)", n, BATCH_SIZE, t_total, t_parse, t_stats, t_db)
        _log_result("import_real_no_eq", n, BATCH_SIZE, hps, t_total, t_parse, t_stats, t_db)

        assert total_imported == n
        assert hps > 500, f"Too slow: {hps:.0f} h/s (expected >500)"

    def test_rebuild_real_hands(self, db):
        """Rebuild 20k real hands: single txn, skip hands table insert."""
        hands = _load_real_hands()
        n = len(hands)

        # Phase 1: seed DB with hands (using no-equity for speed)
        _run_import(db, hands, disable_equity=True)

        # Phase 2: wipe derived tables, simulate rebuild
        db.execute("DELETE FROM board_cards")
        db.execute("DELETE FROM hand_players")
        db.execute("DELETE FROM players")
        reset_import_cache()

        all_rows = db.execute("SELECT id, raw_text FROM hands ORDER BY id").fetchall()

        db.execute("BEGIN TRANSACTION")
        total_imported, t_parse, t_stats, t_db = _run_import(
            db, all_rows, rebuild=True, in_transaction=True, disable_equity=True)
        db.execute("COMMIT")

        t_total = t_parse + t_stats + t_db
        hps = n / t_total if t_total > 0 else 0

        _print_result("Rebuild (real, single txn)", n, BATCH_SIZE, t_total, t_parse, t_stats, t_db)
        _log_result("rebuild_real", n, BATCH_SIZE, hps, t_total, t_parse, t_stats, t_db)

        assert total_imported == n
        assert hps > 500, f"Too slow: {hps:.0f} h/s (expected >500)"
