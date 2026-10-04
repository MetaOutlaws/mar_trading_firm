"""Synthetic checks for the frozen entry and trailing engine.

These tests do not read the market cache and do not score a strategy.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import study
from entry_trailing_20261004.budget import (
    ARCHIVE_SHA256, FILE_SHA256, LEDGER_COLUMNS, OUTCOME_COLUMNS, TOKENS,
    ledger_template_rows, stage1_ids, stage2_ids,
)
from entry_trailing_20261004.execution import (
    ExitSpec, FundingBook, decluster_times, exit_specs, passes_screen,
    simulate_trade, window_inside,
)
from entry_trailing_20261004.features import bars_15m, compute_features, rule_mask
from entry_trailing_20261004.run_study import WAITING_FOR_GARWE_LOCK, main
from entry_trailing_20261004.stage1 import barrier_table, on_horizon_grid
from entry_trailing_20261004.stage2 import (
    apply_scaler, choose_frozen, fit_l2_logistic, fit_scaler, test_mask, train_mask,
)

FEE = study.FEE


def candles_from(rows):
    ix = pd.date_range('2024-06-01', periods=len(rows), freq='min', tz='UTC')
    arr = np.asarray(rows, dtype=float)
    frame = pd.DataFrame(
        {'open': arr[:, 0], 'high': arr[:, 1], 'low': arr[:, 2], 'close': arr[:, 3], 'volume': np.ones(len(rows))},
        index=ix,
    )
    return frame


def empty_funding(index=None):
    ix = pd.DatetimeIndex([], tz='UTC') if index is None else index
    return pd.DataFrame({'funding_rate': []}, index=ix)


def run(frame, side, spec, slip=0.0, funding=None, atr=None, entry_i=0):
    fund = empty_funding() if funding is None else funding
    book = FundingBook(frame, fund)
    return simulate_trade(
        frame.index, frame['open'].to_numpy(), frame['high'].to_numpy(),
        frame['low'].to_numpy(), frame['close'].to_numpy(),
        entry_i, side, slip, spec, book, atr,
    )


class ExecutionTests(unittest.TestCase):
    def test_trail_activates_only_after_completed_bar_and_not_same_bar(self):
        # Bar 1 completes a 1% extreme. Bar 2's high must not tighten the stop
        # that bar 2 is tested against.
        level = 100 * 1.01
        frame = candles_from([
            (100, 100.5, 99.5, 100.2),
            (100.2, level, 100.2, level),
            (100.5, 106, 100.0, 105),
            (105, 105, 104, 104),
            (104, 104, 104, 104),
        ])
        spec = ExitSpec('trail', activation_pct=0.01, trail_pct=0.008, holding=5)
        got = run(frame, 1, spec)
        self.assertEqual(got['reason'], 'trail')
        self.assertEqual(got['holding_minutes'], 3)
        self.assertAlmostEqual(got['exit_price'], level * 0.992, places=8)
        self.assertNotAlmostEqual(got['exit_price'], 106 * 0.992, places=4)
        self.assertTrue(got['activated'])

    def test_trail_stays_inactive_before_one_percent(self):
        frame = candles_from([
            (100, 100.9, 99.5, 100.4),
            (100.4, 100.4, 98.5, 99.4),
            (99.4, 99.4, 99.4, 99.4),
        ])
        spec = ExitSpec('trail', activation_pct=0.01, trail_pct=0.008, holding=3)
        got = run(frame, 1, spec)
        # 0.9% does not activate. The later print hits the original 1% stop.
        self.assertEqual(got['reason'], 'stop')
        self.assertFalse(got['activated'])
        self.assertAlmostEqual(got['exit_price'], 99.0, places=8)

    def test_long_stop_is_monotonic(self):
        level = 100 * 1.01
        frame = candles_from([
            (100, level, 100.5, 100.8),
            (100.8, 103, 100.5, 102.5),
            (102.5, 102.5, 102.0, 102.2),
            (102.2, 102.2, 102.2, 102.2),
        ])
        spec = ExitSpec('trail', activation_pct=0.01, trail_pct=0.008, holding=4)
        got = run(frame, 1, spec)
        self.assertEqual(got['reason'], 'trail')
        self.assertAlmostEqual(got['exit_price'], 103 * 0.992, places=8)
        self.assertEqual(got['holding_minutes'], 3)

    def test_short_stop_is_monotonic(self):
        level = 100 * 0.99
        frame = candles_from([
            (100, 99.5, level, 99.2),
            (99.2, 99.5, 97, 97.5),
            (97.5, 98.0, 97.5, 97.8),
            (97.8, 97.8, 97.8, 97.8),
        ])
        spec = ExitSpec('trail', activation_pct=0.01, trail_pct=0.008, holding=4)
        got = run(frame, -1, spec)
        self.assertEqual(got['reason'], 'trail')
        # Extreme 97, short trail 97 * 1.008. Bar 2 high 98 is through it.
        self.assertAlmostEqual(got['exit_price'], 97 * 1.008, places=8)

    def test_gap_through_long_stop_fills_at_open(self):
        frame = candles_from([
            (100, 100, 100, 100),
            (98, 98.5, 97, 97.5),
            (97.5, 97.5, 97.5, 97.5),
        ])
        got = run(frame, 1, ExitSpec('fixed', target_pct=0.02, holding=3))
        self.assertEqual(got['reason'], 'stop')
        self.assertAlmostEqual(got['exit_price'], 98.0, places=8)
        self.assertAlmostEqual(got['gross_return'], -0.02, places=8)

    def test_gap_through_short_stop_fills_at_open(self):
        frame = candles_from([
            (100, 100, 100, 100),
            (103, 104, 102, 103.5),
            (103, 103, 103, 103),
        ])
        got = run(frame, -1, ExitSpec('fixed', target_pct=0.02, holding=3))
        self.assertEqual(got['reason'], 'stop')
        self.assertAlmostEqual(got['exit_price'], 103.0, places=8)
        self.assertAlmostEqual(got['gross_return'], -0.03, places=8)

    def test_same_bar_stop_and_target_stop_wins(self):
        frame = candles_from([(100, 103, 98, 100), (100, 100, 100, 100)])
        got = run(frame, 1, ExitSpec('fixed', target_pct=0.02, holding=2))
        self.assertEqual(got['reason'], 'stop')
        self.assertTrue(got['ambiguous'])
        self.assertAlmostEqual(got['exit_price'], 99.0, places=8)

    def test_same_bar_stop_and_partial_takes_no_partial_credit(self):
        frame = candles_from([(100, 102, 98, 100), (100, 100, 100, 100)])
        spec = ExitSpec('partial_trail', activation_pct=0.01, trail_pct=0.008, partial_fraction=0.5, holding=2)
        got = run(frame, 1, spec)
        self.assertEqual(got['reason'], 'stop')
        self.assertTrue(got['ambiguous'])
        self.assertTrue(np.isnan(got['partial_price']))
        self.assertAlmostEqual(got['fees'], FEE * (1 + 99 / 100), places=12)

    def test_short_and_long_targets_match_on_mirrored_percents(self):
        long_frame = candles_from([
            (100, 100, 100, 100),
            (100, 102, 100, 101),
            (101, 101, 101, 101),
        ])
        short_frame = candles_from([
            (100, 100, 100, 100),
            (100, 100, 98, 99),
            (99, 99, 99, 99),
        ])
        spec = ExitSpec('fixed', target_pct=0.02, holding=3)
        long = run(long_frame, 1, spec)
        short = run(short_frame, -1, spec)
        self.assertEqual(long['reason'], 'target')
        self.assertEqual(short['reason'], 'target')
        self.assertAlmostEqual(long['gross_return'], 0.02, places=10)
        self.assertAlmostEqual(short['gross_return'], long['gross_return'], places=10)
        # Exit notional differs, so the fee differs. Each side still pays entry once.
        self.assertAlmostEqual(long['fees'], FEE * (1 + 102 / 100), places=12)
        self.assertAlmostEqual(short['fees'], FEE * (1 + 98 / 100), places=12)

    def test_flat_market_long_and_short_pay_the_same_fees(self):
        frame = candles_from([(100, 100, 100, 100)] * 4)
        spec = ExitSpec('fixed', target_pct=0.02, holding=4)
        long = run(frame, 1, spec)
        short = run(frame, -1, spec)
        self.assertEqual(long['reason'], 'time')
        self.assertEqual(short['reason'], 'time')
        self.assertAlmostEqual(long['net_return'], -2 * FEE, places=12)
        self.assertAlmostEqual(short['net_return'], long['net_return'], places=12)

    def test_partial_fees_charge_entry_once(self):
        level = 100 * 1.01
        frame = candles_from([
            (100, 100, 100, 100),
            (100.2, level, 100.5, level),
            (level, level, level, level),
            (level, level, level, level),
        ])
        spec = ExitSpec('partial_trail', activation_pct=0.01, trail_pct=0.008, partial_fraction=0.5, holding=4)
        got = run(frame, 1, spec)
        self.assertEqual(got['reason'], 'partial_time')
        self.assertAlmostEqual(got['gross_return'], 0.01, places=10)
        self.assertAlmostEqual(got['fees'], FEE * (1 + level / 100), places=12)
        # A second entry fee would make this larger.
        self.assertLess(got['fees'], FEE * (2 + level / 100) - 1e-12)

    def test_funding_excludes_entry_and_uses_costlier_exit_minute(self):
        frame = candles_from([
            (100, 100, 98, 99),  # stop on the entry bar at 99
            (100, 100, 100, 100),
            (100, 100, 100, 100),
        ])
        # Positive rate one minute after the stop is costly for a long, so the
        # ambiguous minute is included. The print at the entry timestamp is not.
        funding = pd.DataFrame(
            {'funding_rate': [0.01, 0.002]},
            index=pd.DatetimeIndex([frame.index[0], frame.index[1]]),
        )
        got = run(frame, 1, ExitSpec('fixed', target_pct=0.02, holding=3), funding=funding)
        self.assertEqual(got['reason'], 'stop')
        self.assertAlmostEqual(got['funding'], 0.002, places=12)

    def test_funding_ambiguous_minute_does_not_credit_a_receipt(self):
        frame = candles_from([(100, 100, 98, 99), (99, 99, 99, 99)])
        funding = pd.DataFrame({'funding_rate': [-0.002]}, index=frame.index[1:2])
        got = run(frame, 1, ExitSpec('fixed', target_pct=0.02, holding=2), funding=funding)
        self.assertAlmostEqual(got['funding'], 0.0, places=12)

    def test_partial_funding_scales_by_open_fraction(self):
        level = 100 * 1.01
        frame = candles_from([
            (100, 100, 100, 100),
            (100, level, 100.5, 100.5),
            (100, 100.5, 100.5, 100.5),
            (100, 100.5, 100.5, 100.5),
            (100, 100.5, 100.5, 100.5),
            (100, 100.5, 100.5, 100.5),
        ])
        funding = pd.DataFrame(
            {'funding_rate': [0.01, 0.003, 0.004]},
            index=pd.DatetimeIndex([frame.index[0], frame.index[1], frame.index[3]]),
        )
        spec = ExitSpec('partial_trail', activation_pct=0.01, trail_pct=0.008, partial_fraction=0.5, holding=6)
        got = run(frame, 1, spec, funding=funding)
        # Entry print excluded. The partial-bar print is charged on both halves.
        # The later print is charged only on the remainder.
        self.assertAlmostEqual(got['funding'], 0.003 + 0.5 * 0.004, places=12)

    def test_fixed_exit_matches_tape_oracle(self):
        frame = candles_from([(100, 100.2, 99.8, 100.1)] * 30)
        frame.iloc[5, frame.columns.get_loc('high')] = 103
        funding = pd.DataFrame({'funding_rate': [0.0002]}, index=frame.index[3:4])
        spec = ExitSpec('fixed', target_pct=0.02, stop_pct=0.01, holding=20)
        got = run(frame, 1, spec, slip=0.0005, funding=funding)
        tape = study.Tape(frame, funding)
        begin = frame.index[0]
        end = begin + pd.Timedelta(minutes=20)
        oracle = tape.run(frame.index[:1], 1, 0.02, 0.01, 0.0005, begin, end, holding=20).iloc[0]
        self.assertEqual(got['reason'], oracle.reason)
        self.assertEqual(got['holding_minutes'], int(oracle.holding_minutes))
        self.assertAlmostEqual(got['net_return'], float(oracle.net_return), places=12)
        self.assertAlmostEqual(got['fees'], float(oracle.fees), places=12)
        self.assertAlmostEqual(got['funding'], float(oracle.funding), places=12)

    def test_atr_trail_respects_the_cap(self):
        level = 100 * 1.01
        frame = candles_from([
            (100, level, 100.5, level),
            (level, 110, 100.5, 109),
            (109, 109, 107, 108),
            (108, 108, 108, 108),
        ])
        spec = ExitSpec('trail_atr', activation_pct=0.01, atr_mult=1.5, holding=4)
        got = run(frame, 1, spec, atr=10.0)
        # Uncapped 1.5*10 would sit below the initial stop and would not exit at 108.
        self.assertEqual(got['reason'], 'trail')
        self.assertAlmostEqual(got['exit_price'], 108.0, places=8)

    def test_partition_window_boundary(self):
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2025-01-01', tz='UTC')
        last = end - pd.Timedelta(minutes=1440)
        self.assertTrue(window_inside(last, start, end, 1440))
        self.assertFalse(window_inside(last + pd.Timedelta(minutes=1), start, end, 1440))
        self.assertFalse(window_inside(start - pd.Timedelta(minutes=1), start, end, 60))

    def test_decluster_keeps_nonoverlapping_labels(self):
        base = pd.Timestamp('2024-01-01', tz='UTC')
        times = [base, base + pd.Timedelta(minutes=100), base + pd.Timedelta(minutes=240), base + pd.Timedelta(minutes=241)]
        kept = decluster_times(times, 240)
        self.assertEqual(list(kept), [times[0], times[2]])

    def test_only_four_exit_specs(self):
        self.assertEqual(tuple(exit_specs()), ('fixed', 'trail', 'trail_atr', 'partial_trail'))


class FeatureTests(unittest.TestCase):
    def _minute_walk(self, n, seed=1):
        ix = pd.date_range('2022-01-01', periods=n, freq='min', tz='UTC')
        rng = np.random.default_rng(seed)
        price = 100 * np.exp(np.cumsum(rng.normal(0, 0.0004, n)))
        frame = pd.DataFrame({
            'open': price, 'close': price, 'high': price * 1.0005, 'low': price * 0.9995,
            'volume': rng.uniform(1, 3, n),
        }, index=ix)
        return frame

    def test_future_bars_do_not_change_completed_features(self):
        frame = self._minute_walk(15 * 160)
        cut = frame.index[15 * 140]
        changed = frame.copy()
        changed.loc[changed.index >= cut, ['open', 'high', 'low', 'close']] *= 1.4
        original = compute_features(bars_15m(frame))
        perturbed = compute_features(bars_15m(changed))
        pd.testing.assert_frame_equal(original.loc[:cut], perturbed.loc[:cut])

    def test_rules_use_only_the_frozen_inequalities(self):
        row = pd.DataFrame([{
            'rv_24h': 0.01, 'atr_pct': 0.002, 'rel_volume': 2.0, 'range_compression': 0.40,
            'trend': 0.0, 'dist_high': 0.001, 'dist_low': 0.0, 'hour_sin': 0.0, 'hour_cos': 1.0,
        }], index=pd.DatetimeIndex(['2024-01-01 00:15'], tz='UTC'))
        self.assertTrue(bool(rule_mask(row, 'compression', 1).iloc[0]))
        row.loc[row.index[0], 'rel_volume'] = 1.99
        self.assertFalse(bool(rule_mask(row, 'compression', 1).iloc[0]))
        fade = row.copy()
        fade.loc[fade.index[0], 'dist_high'] = 0.01
        fade.loc[fade.index[0], 'rel_volume'] = 2
        self.assertTrue(bool(rule_mask(fade, 'fade', -1).iloc[0]))

    def test_hour_features_are_a_function_of_the_bar_clock(self):
        ix = pd.date_range('2024-01-01', periods=15 * 120, freq='min', tz='UTC')
        price = np.full(len(ix), 100.0)
        frame = pd.DataFrame({
            'open': price, 'high': price + 0.1, 'low': price - 0.1, 'close': price, 'volume': 1.0,
        }, index=ix)
        features = compute_features(bars_15m(frame)).dropna()
        at_midnight = features.loc[features.index.hour == 0].iloc[0]
        at_six = features.loc[features.index.hour == 6].iloc[0]
        self.assertAlmostEqual(at_midnight.hour_sin, 0.0, places=12)
        self.assertAlmostEqual(at_midnight.hour_cos, 1.0, places=12)
        self.assertAlmostEqual(at_six.hour_sin, 1.0, places=12)
        self.assertAlmostEqual(at_six.hour_cos, 0.0, places=12)


class ModelAndPartitionTests(unittest.TestCase):
    def test_purge_drops_the_day_before_the_fold(self):
        times = pd.DatetimeIndex([
            '2022-12-31 00:00',
            '2022-12-31 00:01',
            '2023-01-01 00:00',
        ], tz='UTC')
        train = train_mask(times, '2022-01-01', '2023-01-01')
        test = test_mask(times, '2023-01-01', '2024-01-01')
        self.assertEqual(train.tolist(), [True, False, False])
        self.assertEqual(test.tolist(), [False, False, True])

    def test_scaler_and_fit_ignore_rows_outside_training(self):
        rng = np.random.default_rng(4)
        features = rng.normal(size=(200, 9))
        labels = np.zeros(200)
        labels[:80] = 1
        features[:80, 0] += 2
        features[80:, 0] -= 2
        mu, sd = fit_scaler(features[:150])
        coef, status = fit_l2_logistic(apply_scaler(features[:150], mu, sd), labels[:150])
        self.assertIn(status, ('ok', 'ok_max_iter'))
        changed = features.copy()
        changed[150:] += 50
        mu2, sd2 = fit_scaler(changed[:150])
        coef2, _ = fit_l2_logistic(apply_scaler(changed[:150], mu2, sd2), labels[:150])
        np.testing.assert_allclose(mu, mu2)
        np.testing.assert_allclose(sd, sd2)
        np.testing.assert_allclose(coef, coef2)
        self.assertGreater(coef[0], 0)

    def test_small_class_refuses_instead_of_loosening(self):
        features = np.ones((80, 3))
        labels = np.zeros(80)
        labels[:10] = 1
        coef, status = fit_l2_logistic(features, labels)
        self.assertIsNone(coef)
        self.assertEqual(status, 'failed_class_count')

    def test_freeze_ranks_discovery_mean_not_validation(self):
        rows = [
            self._row('rule_fade_BTCUSDT_long', 'BTCUSDT', 0.002, 0.020, True),
            self._row('rule_compression_BTCUSDT_long', 'BTCUSDT', 0.004, 0.001, True),
            self._row('model_l2_ETHUSDT_short', 'ETHUSDT', 0.010, 0.010, False),
            self._row('rule_fade_ETHUSDT_long', 'ETHUSDT', -0.001, 0.020, False),
        ]
        frozen = choose_frozen(rows)
        self.assertEqual(frozen['BTCUSDT'], 'rule_compression_BTCUSDT_long')
        self.assertIsNone(frozen['ETHUSDT'])
        self.assertIsNone(frozen['SOLUSDT'])

    def test_tie_breaks_by_identifier(self):
        rows = [
            self._row('rule_fade_SOLUSDT_short', 'SOLUSDT', 0.003, 0.002, True),
            self._row('rule_compression_SOLUSDT_long', 'SOLUSDT', 0.003, 0.009, True),
        ]
        self.assertEqual(choose_frozen(rows)['SOLUSDT'], 'rule_compression_SOLUSDT_long')

    def _row(self, experiment_id, token, mean_d, mean_v, passes):
        return {
            'experiment_id': experiment_id,
            'token': token,
            'mean_discovery': mean_d,
            'mean_validation': mean_v,
            'passes_screen': passes,
        }

    def test_screen_rejects_null_profit_factor(self):
        good = {'trades': 50, 'mean': 0.001, 'pf': 1.2}
        no_loss = {'trades': 50, 'mean': 0.001, 'pf': None}
        stress = {'mean': 0.0001}
        self.assertFalse(passes_screen(good, no_loss, stress, stress))
        self.assertTrue(passes_screen(good, good, stress, stress))


class BarrierTests(unittest.TestCase):
    def test_same_bar_barrier_is_adverse_and_failures_stay(self):
        open_ = np.array([100.0, 100.0])
        high = np.array([101.0, 100.2])
        low = np.array([99.0, 99.9])
        # One-bar windows, evaluated as if each row is its own entry of horizon 1.
        table = barrier_table(open_, high, low, np.array([0, 1]), 1, 1)
        self.assertEqual(table[0.01]['race'][0], 'adverse_first')
        self.assertEqual(table[0.01]['race'][1], 'neither')
        self.assertEqual(table[0.01]['minutes_to_favourable'][1], 1)

    def test_horizon_grid_uses_nanosecond_clock(self):
        times = pd.date_range('2022-01-01', periods=5, freq='60min', tz='UTC')
        if times.tz is None:
            times = times.tz_localize('UTC')
        flag = on_horizon_grid(times, 60)
        self.assertTrue(flag.all())
        shifted = times + pd.Timedelta(minutes=15)
        self.assertFalse(on_horizon_grid(shifted, 60).any())


class BudgetAndLockTests(unittest.TestCase):
    def test_budgets_match_the_addendum(self):
        self.assertEqual(len(stage1_ids()), 96)
        self.assertEqual(len(stage2_ids()), 18)
        self.assertEqual(TOKENS, study.SYMBOLS)
        text = Path(__file__).with_name('EXECUTION_ADDENDUM.md').read_text()
        self.assertIn(ARCHIVE_SHA256, text)
        for digest in FILE_SHA256.values():
            self.assertIn(digest, text)

    def test_ledger_template_has_no_outcomes(self):
        path = Path(__file__).with_name('experiment_ledger.csv')
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        self.assertEqual(list(frame.columns), list(LEDGER_COLUMNS))
        self.assertEqual(len(frame), len(ledger_template_rows()))
        self.assertTrue((frame['status'] == 'pre-registered').all())
        for column in OUTCOME_COLUMNS:
            self.assertTrue((frame[column] == '').all(), column)

    def test_runner_refuses_before_opening_the_cache(self):
        with patch('entry_trailing_20261004.run_study.run', side_effect=AssertionError('cache opened')):
            code = main(['--cache', '/tmp/does-not-exist-cache', '--out', '/tmp/does-not-exist-out'])
        self.assertEqual(code, 2)
        self.assertIn('WAITING_FOR_GARWE_LOCK', WAITING_FOR_GARWE_LOCK)


if __name__ == '__main__':
    unittest.main(verbosity=2)
