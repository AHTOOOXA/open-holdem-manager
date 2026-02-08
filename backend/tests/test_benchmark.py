"""Benchmark test for import pipeline throughput."""

import time
import re
import pytest
import duckdb
from pathlib import Path

from app.parsers.ggpoker import parse_hand_history
from app.stat_flags import compute_stat_flags
from app.api.import_hands import _flush_batch, reset_import_cache, split_hands
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures"

RE_HAND_ID = re.compile(r"Poker Hand #(\w+):")


def _load_and_duplicate_hands(target: int = 500) -> list[str]:
    """Load all fixture hands and duplicate them with unique IDs to reach target count."""
    base_hands: list[str] = []
    for fixture in FIXTURES.glob("*.txt"):
        text = fixture.read_text()
        for h in split_hands(text):
            h = h.strip()
            if h:
                base_hands.append(h)

    hands: list[str] = []
    for i in range(target):
        src = base_hands[i % len(base_hands)]
        new_id = f"BENCH{i:08d}"
        hands.append(RE_HAND_ID.sub(f"Poker Hand #{new_id}:", src, count=1))
    return hands


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestBenchmark:
    def test_import_pipeline_speed(self, db):
        """Benchmark full pipeline: parse + stats + DB insert (batched)."""
        hands = _load_and_duplicate_hands(500)
        n = len(hands)
        batch_size = 100

        t_parse = 0.0
        t_stats = 0.0
        t_db = 0.0
        total_imported = 0
        total_errors = 0
        pending = []

        for hand_text in hands:
            t0 = time.perf_counter()
            parsed = parse_hand_history(hand_text)
            t1 = time.perf_counter()
            stats = compute_stat_flags(parsed)
            t2 = time.perf_counter()
            t_parse += t1 - t0
            t_stats += t2 - t1
            pending.append((parsed, stats))

            if len(pending) >= batch_size:
                t0 = time.perf_counter()
                imp, errs, _ = _flush_batch(db, pending)
                t_db += time.perf_counter() - t0
                total_imported += imp
                total_errors += errs
                pending = []

        if pending:
            t0 = time.perf_counter()
            imp, errs, _ = _flush_batch(db, pending)
            t_db += time.perf_counter() - t0
            total_imported += imp
            total_errors += errs

        t_total = t_parse + t_stats + t_db
        hps = n / t_total if t_total > 0 else 0

        print(f"\n{'='*50}")
        print(f"  Benchmark: {n} hands (batch={batch_size})")
        print(f"  Total:  {t_total*1000:.0f}ms  ({hps:.0f} h/s)")
        print(f"  Parse:  {t_parse*1000:.0f}ms  ({t_parse/t_total*100:.0f}%)")
        print(f"  Stats:  {t_stats*1000:.0f}ms  ({t_stats/t_total*100:.0f}%)")
        print(f"  DB:     {t_db*1000:.0f}ms  ({t_db/t_total*100:.0f}%)")
        print(f"{'='*50}")

        assert total_imported == n
        assert total_errors == 0
        # Minimum speed gate — actual speed varies by machine
        assert hps > 10, f"Pipeline too slow: {hps:.0f} h/s (expected >10)"
