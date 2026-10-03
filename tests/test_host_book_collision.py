"""Collision checks on in-memory rows. No database and no droplet."""

from __future__ import annotations

import inspect

import pytest

from core.ledger.host_identity import (
    composite_identity,
    detect_book_collisions,
)


def _position(server: str, epoch: str, row_id: int, symbol: str) -> dict:
    return {
        "source_server": server,
        "epoch": epoch,
        "table": "positions",
        "id": row_id,
        "symbol": symbol,
    }


def test_composite_key_is_server_epoch_and_id() -> None:
    identity = composite_identity("nyc3", "2026-09", "positions", 1)
    assert identity.as_key() == ("nyc3", "2026-09", 1)
    assert identity.table == "positions"


def test_same_integer_id_on_two_hosts_is_a_collision() -> None:
    report = detect_book_collisions(
        [
            _position("nyc3", "2026-09", 1, "BTCUSDT"),
            _position("sgp1", "2026-10", 1, "ETHUSDT"),
        ]
    )
    assert len(report.id_collisions) == 1
    collision = report.id_collisions[0]
    assert collision.table == "positions"
    assert collision.row_id == 1
    assert [item.as_key() for item in collision.identities] == [
        ("nyc3", "2026-09", 1),
        ("sgp1", "2026-10", 1),
    ]
    assert report.host_mix is True
    assert report.epoch_mix is True
    assert report.blocks_naive_merge is True


def test_disjoint_ids_still_block_a_host_union() -> None:
    """No shared integer is not permission to concatenate the books."""
    report = detect_book_collisions(
        [
            _position("nyc3", "2026-09", 1, "BTCUSDT"),
            _position("sgp1", "2026-09", 2, "ETHUSDT"),
        ]
    )
    assert report.id_collisions == ()
    assert report.host_mix is True
    assert report.epoch_mix is False
    assert report.blocks_naive_merge is True


def test_sep_and_oct_cash_epochs_are_not_one_journal() -> None:
    report = detect_book_collisions(
        [
            {
                "source_server": "nyc3",
                "epoch": "2026-09",
                "table": "cash_events",
                "id": 0,
                "kind": "capital",
            },
            {
                "source_server": "nyc3",
                "epoch": "2026-10",
                "table": "cash_events",
                "id": 0,
                "kind": "capital",
            },
        ]
    )
    assert report.epoch_mix is True
    assert report.host_mix is False
    assert len(report.id_collisions) == 1
    assert report.id_collisions[0].table == "cash_events"
    assert report.blocks_naive_merge is True


def test_position_id_does_not_collide_with_trade_id() -> None:
    report = detect_book_collisions(
        [
            _position("nyc3", "2026-09", 1, "BTCUSDT"),
            {
                "source_server": "nyc3",
                "epoch": "2026-09",
                "table": "trades",
                "id": 1,
                "position_id": 1,
            },
        ]
    )
    assert report.id_collisions == ()
    assert report.blocks_naive_merge is False


def test_duplicate_export_is_not_a_collision() -> None:
    row = _position("sgp1", "2026-10", 4, "SOLUSDT")
    report = detect_book_collisions([row, dict(row)])
    assert report.id_collisions == ()
    assert report.payload_conflicts == ()
    assert len(report.duplicate_exports) == 1
    assert report.duplicate_exports[0].as_key() == ("sgp1", "2026-10", 4)
    assert report.blocks_naive_merge is False


def test_same_identity_with_different_payload_is_a_conflict() -> None:
    report = detect_book_collisions(
        [
            _position("nyc3", "2026-09", 3, "BTCUSDT"),
            _position("nyc3", "2026-09", 3, "ETHUSDT"),
        ]
    )
    assert report.payload_conflicts[0].as_key() == ("nyc3", "2026-09", 3)
    assert report.id_collisions == ()
    assert report.blocks_naive_merge is True


def test_insert_or_replace_is_banned() -> None:
    report = detect_book_collisions(
        [_position("nyc3", "2026-09", 1, "BTCUSDT")],
        statement="INSERT OR REPLACE INTO positions (id, symbol) VALUES (1, 'ETHUSDT')",
        destination="offline-staging",
    )
    assert report.banned_statement is True
    assert report.banned_destination is False
    assert report.blocks_naive_merge is True


def test_on_conflict_do_update_is_banned_with_a_column_list() -> None:
    statement = (
        "INSERT INTO positions (id) VALUES (1) "
        "ON CONFLICT (id) DO UPDATE SET symbol = excluded.symbol"
    )
    report = detect_book_collisions([], statement=statement, destination="staging")
    assert report.banned_statement is True
    assert report.blocks_naive_merge is True


def test_live_sgp1_and_nyc3_are_banned_destinations() -> None:
    rows = [_position("nyc3", "2026-09", 1, "BTCUSDT")]
    sgp1 = detect_book_collisions(rows, destination="sgp1")
    live = detect_book_collisions(rows, destination="live-sgp1")
    nyc3 = detect_book_collisions(rows, destination="nyc3")
    assert sgp1.banned_destination is True
    assert live.banned_destination is True
    assert nyc3.banned_destination is True
    assert sgp1.blocks_naive_merge is True


def test_destructive_sql_is_flagged_so_nyc3_is_not_a_target() -> None:
    report = detect_book_collisions(
        [],
        statement="DROP TABLE positions",
        destination="nyc3",
    )
    assert report.destructive_statement is True
    assert report.banned_destination is True
    assert report.blocks_naive_merge is True


def test_single_book_inventory_has_nothing_to_merge() -> None:
    report = detect_book_collisions(
        [
            _position("sgp1", "2026-10", 1, "BTCUSDT"),
            {
                "source_server": "sgp1",
                "epoch": "2026-10",
                "table": "equity_snapshots",
                "id": 8,
                "equity": 10_000.0,
            },
        ],
        destination="",
    )
    assert report.servers_present == ("sgp1",)
    assert report.epochs_present == ("2026-10",)
    assert report.blocks_naive_merge is False


def test_unknown_labels_fail_closed() -> None:
    with pytest.raises(ValueError, match="source_server"):
        composite_identity("lon1", "2026-09", "positions", 1)
    with pytest.raises(ValueError, match="epoch"):
        composite_identity("nyc3", "2026-11", "positions", 1)
    with pytest.raises(ValueError, match="id"):
        detect_book_collisions(
            [{"source_server": "nyc3", "epoch": "2026-09", "table": "positions", "id": True}]
        )


def test_module_does_not_open_a_database_or_network() -> None:
    import core.ledger.host_identity as identity

    source = inspect.getsource(identity)
    for banned in (
        "sqlite3",
        "sqlalchemy",
        "create_engine",
        "session_scope",
        "socket",
        "urllib",
        "DATABASE_URL",
        "approved_strategies",
    ):
        assert banned not in source
