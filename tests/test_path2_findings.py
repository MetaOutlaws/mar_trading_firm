"""Path2 findings render only Marcus-sealed rows.

The shipped table is thirty rows, all FAIL. ma_macd_rsi_agree is one cell.
RSI is a state, not a 70/30 cross. A less-negative net stays FAIL.
funding_extreme_agree is BTCUSDT 4h with one frozen threshold line.
london_am_range_break is one BTCUSDT 4h cell. Rates stay decimals.
prior_utc_day_mid_cross is one BTCUSDT 4h cell. A less-negative net stays FAIL.
eth_btc_return_agree is one BTCUSDT 4h cell. Rates stay decimals.
oi_delta_agree is one BTCUSDT 4h cell. Rates stay decimals.
Where an older cell says none, that metric stays null. An empty cells list
still renders nothing.
"""

from __future__ import annotations

import json

from config.settings import PROJECT_ROOT
from firm.path2_findings import (
    METRIC_KEYS,
    PATH2_FINDINGS_PATH,
    SEALED_TABLE_NOTE,
    load_path2_findings,
)


# Figures copied from the sealed rows. Strings keep the sign, the percent,
# and the trailing zero that a float would drop.
_LONG = {
    "n": 533,
    "target_first_count": 166,
    "target_first_rate": "31.1%",
    "gross": "+0.009634",
    "net_after_0_31_rt": "-0.197033",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.178630",
}
_SHORT = {
    "n": 484,
    "target_first_count": 150,
    "target_first_rate": "31.0%",
    "gross": "+0.025144",
    "net_after_0_31_rt": "-0.181523",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.095669",
}


_RSI_LONG = {
    "n": 1,
    "target_first_count": 1,
    "target_first_rate": "100%",
    "gross": "+2.000",
    "net_after_0_31_rt": "+1.793333",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "+1.345",
}
_RSI_SHORT = {
    "n": 3,
    "target_first_count": 2,
    "target_first_rate": "66.7%",
    "gross": "+1.000",
    "net_after_0_31_rt": "+0.793333",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "+0.511667",
}


# 80/20 had zero trades. n and target-first count are real zeros. The sealed
# table says none for the rate, gross, net, and stress stop, so those stay null.
_RSI_80_LONG = {
    "n": 0,
    "target_first_count": 0,
    "target_first_rate": None,
    "gross": None,
    "net_after_0_31_rt": None,
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": None,
}
_RSI_80_SHORT = {
    "n": 0,
    "target_first_count": 0,
    "target_first_rate": None,
    "gross": None,
    "net_after_0_31_rt": None,
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": None,
}


_VA_70_LONG = {
    "n": 127,
    "target_first_count": 33,
    "target_first_rate": "26.0%",
    "gross": "-0.130728",
    "net_after_0_31_rt": "-0.337395",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.274343",
}
_VA_70_SHORT = {
    "n": 133,
    "target_first_count": 41,
    "target_first_rate": "30.8%",
    "gross": "+0.008648",
    "net_after_0_31_rt": "-0.198018",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.219031",
}
_VA_80_LONG = {
    "n": 20,
    "target_first_count": 8,
    "target_first_rate": "40.0%",
    "gross": "+0.252953",
    "net_after_0_31_rt": "+0.046287",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "+0.045730",
}
_VA_80_SHORT = {
    "n": 40,
    "target_first_count": 13,
    "target_first_rate": "32.5%",
    "gross": "-0.025000",
    "net_after_0_31_rt": "-0.231667",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.246742",
}
_LABELS = [
    "EMA 21 and MACD 12, 26, 9, agreement required",
    "EMA 21, RSI 14, cell 70/30",
    "EMA 21, RSI 14, cell 80/20",
    "6 bars, 70% volume at the close, RSI 14, pair 70/30",
    "6 bars, 70% volume at the close, RSI 14, pair 80/20",
    "Wilder 14, ADX floor 20 as a state, DI direction as a state, RSI 70/30. Both legs required.",
    "Wilder 14, ADX floor 25 as a state, DI direction as a state, RSI 70/30.",
    "Wilder 14, ADX floor 20 as a state, DI direction as a state, close versus EMA 21. Both legs required.",
    "Wilder 14, ADX floor 25 as a state, DI direction as a state, close versus EMA 21. Both legs required.",
    "EMA 21, MACD 12/26/9, RSI 14 as a state at or above 30 for long and at or below 70 for short. All three required. Note that RSI at the prior bar was not read.",
]
_MA_MACD_RSI_LONG = {
    "n": 1162,
    "target_first_count": 375,
    "target_first_rate": "32.3%",
    "gross": "+0.024716",
    "net_after_0_31_rt": "-0.181951",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.126355",
}
_MA_MACD_RSI_SHORT = {
    "n": 1267,
    "target_first_count": 397,
    "target_first_rate": "31.3%",
    "gross": "-0.006383",
    "net_after_0_31_rt": "-0.213050",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.153812",
}
# Rates stay decimals. Clock and the frozen line were filled later; the figures were not.
_FUNDING_CLOCK = "BTCUSDT 4h"
_FUNDING_LABEL = (
    "0.0005 inclusive, which is 1/2000, five times the 0.01% eight-hour baseline. "
    "Frozen before any count. Long: the latest funding print known at the bar close "
    "is >= +0.0005 and that bar closes above its open. Short: the print is <= -0.0005 "
    "and that bar closes below its open. Either piece alone is no trade. Not a fade."
)
_FUNDING_LONG = {
    "n": 180,
    "target_first_count": 55,
    "target_first_rate": "0.305556",
    "gross": "-0.083333",
    "net_after_0_31_rt": "-0.290000",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.208048",
}
_FUNDING_SHORT = {
    "n": 20,
    "target_first_count": 2,
    "target_first_rate": "0.100000",
    "gross": "-0.700000",
    "net_after_0_31_rt": "-0.906667",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.713824",
}
_LONDON_CLOCK = "BTCUSDT 4h"
_LONDON_LABEL = (
    "prior completed 07:00\u201311:00 UTC box from 1h bars opening 07/08/09/10; "
    "min range (H-L)/mid >= 0.004; long = close cross up through high; "
    "short = cross down through low; close back inside is no trade."
)
_LONDON_LONG = {
    "n": 862,
    "target_first_count": 274,
    "target_first_rate": "0.317865",
    "gross": "+0.033733",
    "net_after_0_31_rt": "-0.172933",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.138613",
}
_LONDON_SHORT = {
    "n": 855,
    "target_first_count": 263,
    "target_first_rate": "0.307602",
    "gross": "-0.000012",
    "net_after_0_31_rt": "-0.206679",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.128235",
}
_MID_CLOCK = "BTCUSDT 4h"
_MID_LABEL = (
    "prior completed UTC day mid=(H+L)/2; "
    "min range (H\u2212L)/mid \u2265 0.005; "
    "long = first close cross up through mid; "
    "short = first close cross down; "
    "wick pierce that closes back is no trade."
)
_MID_LONG = {
    "n": 682,
    "target_first_count": 210,
    "target_first_rate": "0.307918",
    "gross": "+0.007469",
    "net_after_0_31_rt": "-0.199198",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.194115",
}
_MID_SHORT = {
    "n": 677,
    "target_first_count": 205,
    "target_first_rate": "0.302806",
    "gross": "-0.000931",
    "net_after_0_31_rt": "-0.207597",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.133446",
}
_ETH_CLOCK = "BTCUSDT 4h"
_ETH_LABEL = (
    "prior ETH close-to-close (close[t-1]\u2212close[t-2])/close[t-2] "
    "at or beyond \u00b10.003 AND BTC same-bar close through open; either alone no trade."
)
_ETH_LONG = {
    "n": 1128,
    "target_first_count": 347,
    "target_first_rate": "0.307624",
    "gross": "+0.011404",
    "net_after_0_31_rt": "-0.195263",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.159413",
}
_ETH_SHORT = {
    "n": 1111,
    "target_first_count": 360,
    "target_first_rate": "0.324032",
    "gross": "+0.052204",
    "net_after_0_31_rt": "-0.154463",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.109531",
}
_OI_CLOCK = "BTCUSDT 4h"
_OI_LABEL = (
    "Binance USDT-M OI 4h change at or beyond \u00b10.75%, "
    "using the last 5m snapshot strictly before close (declared cross-venue proxy), "
    "AND same-bar close through open; either leg alone no trade; "
    "OI NaN or 0 counts as missing, no trade."
)
_OI_LONG = {
    "n": 1104,
    "target_first_count": 349,
    "target_first_rate": "0.316123",
    "gross": "+0.029848",
    "net_after_0_31_rt": "-0.176818",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.119969",
}
_OI_SHORT = {
    "n": 1147,
    "target_first_count": 322,
    "target_first_rate": "0.280732",
    "gross": "-0.077282",
    "net_after_0_31_rt": "-0.283949",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.202034",
}
_ADX_MA25_LONG = {
    "n": 700,
    "target_first_count": 234,
    "target_first_rate": "33.4%",
    "gross": "+0.048085",
    "net_after_0_31_rt": "-0.158581",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.065004",
}
_ADX_MA25_SHORT = {
    "n": 976,
    "target_first_count": 313,
    "target_first_rate": "32.1%",
    "gross": "+0.001735",
    "net_after_0_31_rt": "-0.204931",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.150666",
}
_ADX_MA_LONG = {
    "n": 944,
    "target_first_count": 310,
    "target_first_rate": "32.8%",
    "gross": "+0.040455",
    "net_after_0_31_rt": "-0.166212",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.108236",
}
_ADX_MA_SHORT = {
    "n": 1231,
    "target_first_count": 389,
    "target_first_rate": "31.6%",
    "gross": "-0.017631",
    "net_after_0_31_rt": "-0.224298",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.153372",
}
_ADX_LONG = {
    "n": 0,
    "target_first_count": 0,
    "target_first_rate": None,
    "gross": None,
    "net_after_0_31_rt": None,
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": None,
}
_ADX_SHORT = {
    "n": 1,
    "target_first_count": 1,
    "target_first_rate": "100%",
    "gross": "+2.000000",
    "net_after_0_31_rt": "+1.793333",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "+1.345000",
}


def test_shipped_findings_are_the_thirty_sealed_rows() -> None:
    raw_text = PATH2_FINDINGS_PATH.read_text(encoding="utf-8")
    raw = json.loads(raw_text)
    assert raw["sealed"] is True
    assert "Marcus-sealed table" in raw["note"]
    assert "not from briefs" in raw["note"]
    assert [cell["family"] for cell in raw["cells"]] == [
        "macd_ma_agree",
        "ma_rsi_agree",
        "ma_rsi_agree",
        "va_rsi_agree",
        "va_rsi_agree",
        "adx_rsi_agree",
        "adx_rsi_agree",
        "adx_ma_agree",
        "adx_ma_agree",
        "ma_macd_rsi_agree",
        "funding_extreme_agree",
        "london_am_range_break",
        "prior_utc_day_mid_cross",
        "eth_btc_return_agree",
        "oi_delta_agree",
    ]
    macd, rsi_70, rsi_80, va_70, va_80, adx20, adx25, adx_ma20, adx_ma25, ma_macd, funding, london, mid, eth, oi = raw["cells"]
    assert macd["clock"] == "4h"
    assert macd["thresholds"]["label"] == "EMA 21 and MACD 12, 26, 9, agreement required"
    assert macd["verdict"] == "FAIL"
    assert macd.get("green_year_note") in (None, "")
    assert macd["sides"]["long"] == _LONG
    assert macd["sides"]["short"] == _SHORT
    assert rsi_70["clock"] == "4h"
    assert rsi_70["thresholds"]["label"] == "EMA 21, RSI 14, cell 70/30"
    assert rsi_70["verdict"] == "FAIL"
    assert rsi_70.get("green_year_note") in (None, "")
    assert rsi_70["sides"]["long"] == _RSI_LONG
    assert rsi_70["sides"]["short"] == _RSI_SHORT
    assert rsi_80["id"] != rsi_70["id"]
    assert rsi_80["clock"] == "4h"
    assert rsi_80["thresholds"]["label"] == "EMA 21, RSI 14, cell 80/20"
    assert rsi_80["verdict"] == "FAIL"
    assert rsi_80.get("green_year_note") in (None, "")
    assert rsi_80["sides"]["long"] == _RSI_80_LONG
    assert rsi_80["sides"]["short"] == _RSI_80_SHORT
    assert va_70["id"] != va_80["id"]
    assert va_70["clock"] == "4h"
    assert va_70["thresholds"]["label"] == _LABELS[3]
    assert va_70["verdict"] == "FAIL"
    assert va_70.get("green_year_note") in (None, "")
    assert va_70["sides"]["long"] == _VA_70_LONG
    assert va_70["sides"]["short"] == _VA_70_SHORT
    assert va_80["clock"] == "4h"
    assert va_80["thresholds"]["label"] == _LABELS[4]
    assert va_80["verdict"] == "FAIL"
    assert va_80.get("green_year_note") in (None, "")
    assert va_80["sides"]["long"] == _VA_80_LONG
    assert va_80["sides"]["short"] == _VA_80_SHORT
    assert adx20["id"] != adx25["id"]
    assert adx20["clock"] == "4h"
    assert adx20["thresholds"]["label"] == _LABELS[5]
    assert "floor 20" in adx20["thresholds"]["label"]
    assert "floor 25" not in adx20["thresholds"]["label"]
    assert adx20["verdict"] == "FAIL"
    assert adx20.get("green_year_note") in (None, "")
    assert adx20["sides"]["long"] == _ADX_LONG
    assert adx20["sides"]["short"] == _ADX_SHORT
    assert adx25["clock"] == "4h"
    assert adx25["thresholds"]["label"] == _LABELS[6]
    assert "floor 25" in adx25["thresholds"]["label"]
    assert "floor 20" not in adx25["thresholds"]["label"]
    assert adx25["verdict"] == "FAIL"
    assert adx25.get("green_year_note") in (None, "")
    assert adx25["sides"]["long"] == _ADX_LONG
    assert adx25["sides"]["short"] == _ADX_SHORT
    assert adx_ma20["id"] != adx_ma25["id"]
    assert adx_ma20["family"] == "adx_ma_agree"
    assert adx_ma20["clock"] == "4h"
    assert adx_ma20["thresholds"]["label"] == _LABELS[7]
    assert "floor 20" in adx_ma20["thresholds"]["label"]
    assert "floor 25" not in adx_ma20["thresholds"]["label"]
    assert "RSI" not in adx_ma20["thresholds"]["label"]
    assert adx_ma20["verdict"] == "FAIL"
    assert adx_ma20.get("green_year_note") in (None, "")
    assert adx_ma20["sides"]["long"] == _ADX_MA_LONG
    assert adx_ma20["sides"]["short"] == _ADX_MA_SHORT
    assert adx_ma25["family"] == "adx_ma_agree"
    assert adx_ma25["clock"] == "4h"
    assert adx_ma25["thresholds"]["label"] == _LABELS[8]
    assert "floor 25" in adx_ma25["thresholds"]["label"]
    assert "floor 20" not in adx_ma25["thresholds"]["label"]
    assert "RSI" not in adx_ma25["thresholds"]["label"]
    assert adx_ma25["verdict"] == "FAIL"
    assert adx_ma25.get("green_year_note") in (None, "")
    assert adx_ma25["sides"]["long"] == _ADX_MA25_LONG
    assert adx_ma25["sides"]["short"] == _ADX_MA25_SHORT
    assert ma_macd["family"] == "ma_macd_rsi_agree"
    assert ma_macd["clock"] == "4h"
    assert ma_macd["thresholds"]["label"] == _LABELS[9]
    assert "70/30" not in ma_macd["thresholds"]["label"]
    assert "prior bar was not read" in ma_macd["thresholds"]["label"]
    assert ma_macd["verdict"] == "FAIL"
    assert ma_macd.get("green_year_note") in (None, "")
    assert ma_macd["sides"]["long"] == _MA_MACD_RSI_LONG
    assert ma_macd["sides"]["short"] == _MA_MACD_RSI_SHORT
    assert funding["id"] == "funding_extreme_agree"
    assert funding["family"] == "funding_extreme_agree"
    assert funding["clock"] == _FUNDING_CLOCK
    assert funding["thresholds"]["label"] == _FUNDING_LABEL
    assert funding["verdict"] == "FAIL"
    assert funding.get("green_year_note") in (None, "")
    assert funding["sides"]["long"] == _FUNDING_LONG
    assert funding["sides"]["short"] == _FUNDING_SHORT
    assert london["id"] == "london_am_range_break"
    assert london["family"] == "london_am_range_break"
    assert london["clock"] == _LONDON_CLOCK
    assert london["thresholds"]["label"] == _LONDON_LABEL
    assert "\u2013" in london["thresholds"]["label"]
    assert london["verdict"] == "FAIL"
    assert london.get("green_year_note") in (None, "")
    assert london["sides"]["long"] == _LONDON_LONG
    assert london["sides"]["short"] == _LONDON_SHORT
    assert mid["id"] == "prior_utc_day_mid_cross"
    assert mid["family"] == "prior_utc_day_mid_cross"
    assert mid["clock"] == _MID_CLOCK
    assert mid["thresholds"]["label"] == _MID_LABEL
    assert "\u2212" in mid["thresholds"]["label"]
    assert "\u2265" in mid["thresholds"]["label"]
    assert mid["verdict"] == "FAIL"
    assert mid.get("green_year_note") in (None, "")
    assert mid["sides"]["long"] == _MID_LONG
    assert mid["sides"]["short"] == _MID_SHORT
    assert eth["id"] == "eth_btc_return_agree"
    assert eth["family"] == "eth_btc_return_agree"
    assert eth["clock"] == _ETH_CLOCK
    assert eth["thresholds"]["label"] == _ETH_LABEL
    assert "\u2212" in eth["thresholds"]["label"]
    assert "\u00b1" in eth["thresholds"]["label"]
    assert eth["verdict"] == "FAIL"
    assert eth.get("green_year_note") in (None, "")
    assert eth["sides"]["long"] == _ETH_LONG
    assert eth["sides"]["short"] == _ETH_SHORT
    assert oi["id"] == "oi_delta_agree"
    assert oi["family"] == "oi_delta_agree"
    assert oi["clock"] == _OI_CLOCK
    assert oi["thresholds"]["label"] == _OI_LABEL
    assert "\u00b1" in oi["thresholds"]["label"]
    assert oi["verdict"] == "FAIL"
    assert oi.get("green_year_note") in (None, "")
    assert oi["sides"]["long"] == _OI_LONG
    assert oi["sides"]["short"] == _OI_SHORT
    assert "0.316123" in raw_text
    assert "0.280732" in raw_text
    assert "+0.029848" in raw_text
    assert "-0.176818" in raw_text
    assert "-0.119969" in raw_text
    assert "-0.077282" in raw_text
    assert "-0.283949" in raw_text
    assert "-0.202034" in raw_text
    assert "0.307624" in raw_text
    assert "0.324032" in raw_text
    assert "+0.011404" in raw_text
    assert "-0.195263" in raw_text
    assert "-0.159413" in raw_text
    assert "+0.052204" in raw_text
    assert "-0.154463" in raw_text
    assert "-0.109531" in raw_text
    assert "0.307918" in raw_text
    assert "0.302806" in raw_text
    assert "+0.007469" in raw_text
    assert "-0.199198" in raw_text
    assert "-0.194115" in raw_text
    assert "-0.000931" in raw_text
    assert "-0.207597" in raw_text
    assert "-0.133446" in raw_text
    assert "0.317865" in raw_text
    assert "0.307602" in raw_text
    assert "+0.033733" in raw_text
    assert "-0.172933" in raw_text
    assert "-0.138613" in raw_text
    assert "-0.000012" in raw_text
    assert "-0.206679" in raw_text
    assert "-0.128235" in raw_text
    assert "0.305556" in raw_text
    assert "0.100000" in raw_text
    assert "-0.083333" in raw_text
    assert "-0.290000" in raw_text
    assert "-0.208048" in raw_text
    assert "-0.700000" in raw_text
    assert "-0.906667" in raw_text
    assert "-0.713824" in raw_text
    assert "32.3%" in raw_text
    assert "-0.181951" in raw_text
    assert "-0.126355" in raw_text
    assert "31.3%" in raw_text
    assert "-0.006383" in raw_text
    assert "-0.153812" in raw_text
    assert "33.4%" in raw_text
    assert "+0.048085" in raw_text
    assert "-0.065004" in raw_text
    assert "32.1%" in raw_text
    assert "+0.001735" in raw_text
    assert "-0.150666" in raw_text
    assert "PASS" not in raw_text
    assert "32.8%" in raw_text
    assert "-0.166212" in raw_text
    assert "-0.153372" in raw_text
    assert "+2.000000" in raw_text
    assert "+1.345000" in raw_text
    assert "+2.000" in raw_text
    assert "26.0%" in raw_text
    assert "40.0%" in raw_text
    assert "-0.025000" in raw_text
    assert "+0.046287" in raw_text


def test_shipped_file_loads_thirty_rows_all_fail() -> None:
    loaded = load_path2_findings()
    assert loaded["sealed"] is True
    assert loaded["load_error"] is None
    assert loaded["note"] == SEALED_TABLE_NOTE
    labels = [cell["thresholds_label"] for cell in loaded["cells"]]
    assert labels == _LABELS + [_FUNDING_LABEL, _LONDON_LABEL, _MID_LABEL, _ETH_LABEL, _OI_LABEL]
    macd, rsi_70, rsi_80, va_70, va_80, adx20, adx25, adx_ma20, adx_ma25, ma_macd, funding, london, mid, eth, oi = loaded["cells"]
    assert macd["verdict"] == "FAIL"
    assert macd["green_year_note"] is None
    assert macd["sides"]["long"] == _LONG
    assert macd["sides"]["short"] == _SHORT
    assert rsi_70["verdict"] == "FAIL"
    assert rsi_70["sides"]["long"] == _RSI_LONG
    assert rsi_70["sides"]["short"] == _RSI_SHORT
    assert rsi_80["verdict"] == "FAIL"
    assert rsi_80["green_year_note"] is None
    assert rsi_80["sides"]["long"] == _RSI_80_LONG
    assert rsi_80["sides"]["short"] == _RSI_80_SHORT
    # Zero trades stay zero. "None" metrics stay missing, not a made-up zero rate.
    for side in ("long", "short"):
        assert rsi_80["sides"][side]["n"] == 0
        assert rsi_80["sides"][side]["target_first_count"] == 0
        assert rsi_80["sides"][side]["target_first_rate"] is None
        assert rsi_80["sides"][side]["gross"] is None
        assert rsi_80["sides"][side]["net_after_0_31_rt"] is None
        assert rsi_80["sides"][side]["stress_stop_2_net"] is None
    # Positive net on the thin 80/20 long side stays the sealed FAIL.
    assert va_70["verdict"] == "FAIL"
    assert va_80["verdict"] == "FAIL"
    assert va_70["sides"]["long"] == _VA_70_LONG
    assert va_70["sides"]["short"] == _VA_70_SHORT
    assert va_80["sides"]["long"] == _VA_80_LONG
    assert va_80["sides"]["short"] == _VA_80_SHORT
    assert va_80["sides"]["long"]["net_after_0_31_rt"] == "+0.046287"
    assert adx20["verdict"] == "FAIL"
    assert adx20["green_year_note"] is None
    assert adx20["thresholds_label"] == _LABELS[5]
    assert adx20["sides"]["long"] == _ADX_LONG
    assert adx20["sides"]["short"] == _ADX_SHORT
    assert adx25["verdict"] == "FAIL"
    assert adx25["green_year_note"] is None
    assert adx25["thresholds_label"] == _LABELS[6]
    assert adx25["sides"]["long"] == _ADX_LONG
    assert adx25["sides"]["short"] == _ADX_SHORT
    # Zero-trade blanks stay missing. The thin short side's green net stays FAIL.
    for adx in (adx20, adx25):
        assert adx["sides"]["long"]["n"] == 0
        assert adx["sides"]["long"]["target_first_rate"] is None
        assert adx["sides"]["long"]["gross"] is None
        assert adx["sides"]["long"]["net_after_0_31_rt"] is None
        assert adx["sides"]["long"]["stress_stop_2_net"] is None
        assert adx["sides"]["short"]["net_after_0_31_rt"] == "+1.793333"
        assert adx["sides"]["short"]["gross"] == "+2.000000"
        assert adx["sides"]["short"]["stress_stop_2_net"] == "+1.345000"
    assert adx_ma20["verdict"] == "FAIL"
    assert adx_ma20["family"] == "adx_ma_agree"
    assert adx_ma20["thresholds_label"] == _LABELS[7]
    assert adx_ma20["sides"]["long"] == _ADX_MA_LONG
    assert adx_ma20["sides"]["short"] == _ADX_MA_SHORT
    assert adx_ma20["sides"]["long"]["net_after_0_31_rt"] == "-0.166212"
    assert adx_ma25["verdict"] == "FAIL"
    assert adx_ma25["family"] == "adx_ma_agree"
    assert adx_ma25["thresholds_label"] == _LABELS[8]
    assert adx_ma25["sides"]["long"] == _ADX_MA25_LONG
    assert adx_ma25["sides"]["short"] == _ADX_MA25_SHORT
    assert adx_ma25["sides"]["long"]["net_after_0_31_rt"] == "-0.158581"
    assert adx_ma25["sides"]["short"]["net_after_0_31_rt"] == "-0.204931"
    assert ma_macd["verdict"] == "FAIL"
    assert ma_macd["family"] == "ma_macd_rsi_agree"
    assert ma_macd["thresholds_label"] == _LABELS[9]
    assert ma_macd["sides"]["long"] == _MA_MACD_RSI_LONG
    assert ma_macd["sides"]["short"] == _MA_MACD_RSI_SHORT
    assert ma_macd["sides"]["long"]["net_after_0_31_rt"] == "-0.181951"
    assert ma_macd["sides"]["short"]["net_after_0_31_rt"] == "-0.213050"
    assert funding["verdict"] == "FAIL"
    assert funding["family"] == "funding_extreme_agree"
    assert funding["clock"] == _FUNDING_CLOCK
    assert funding["thresholds_label"] == _FUNDING_LABEL
    assert funding["green_year_note"] is None
    assert funding["sides"]["long"] == _FUNDING_LONG
    assert funding["sides"]["short"] == _FUNDING_SHORT
    assert funding["sides"]["long"]["target_first_rate"] == "0.305556"
    assert funding["sides"]["short"]["target_first_rate"] == "0.100000"
    assert funding["sides"]["long"]["net_after_0_31_rt"] == "-0.290000"
    assert funding["sides"]["short"]["net_after_0_31_rt"] == "-0.906667"
    assert london["verdict"] == "FAIL"
    assert london["family"] == "london_am_range_break"
    assert london["clock"] == _LONDON_CLOCK
    assert london["thresholds_label"] == _LONDON_LABEL
    assert london["green_year_note"] is None
    assert london["sides"]["long"] == _LONDON_LONG
    assert london["sides"]["short"] == _LONDON_SHORT
    assert london["sides"]["long"]["target_first_rate"] == "0.317865"
    assert london["sides"]["short"]["target_first_rate"] == "0.307602"
    assert london["sides"]["long"]["net_after_0_31_rt"] == "-0.172933"
    assert london["sides"]["short"]["net_after_0_31_rt"] == "-0.206679"
    assert mid["verdict"] == "FAIL"
    assert mid["family"] == "prior_utc_day_mid_cross"
    assert mid["clock"] == _MID_CLOCK
    assert mid["thresholds_label"] == _MID_LABEL
    assert mid["green_year_note"] is None
    assert mid["sides"]["long"] == _MID_LONG
    assert mid["sides"]["short"] == _MID_SHORT
    assert mid["sides"]["long"]["target_first_rate"] == "0.307918"
    assert mid["sides"]["short"]["target_first_rate"] == "0.302806"
    assert mid["sides"]["long"]["net_after_0_31_rt"] == "-0.199198"
    assert mid["sides"]["short"]["net_after_0_31_rt"] == "-0.207597"
    assert eth["verdict"] == "FAIL"
    assert eth["family"] == "eth_btc_return_agree"
    assert eth["clock"] == _ETH_CLOCK
    assert eth["thresholds_label"] == _ETH_LABEL
    assert eth["green_year_note"] is None
    assert eth["sides"]["long"] == _ETH_LONG
    assert eth["sides"]["short"] == _ETH_SHORT
    assert eth["sides"]["long"]["target_first_rate"] == "0.307624"
    assert eth["sides"]["short"]["target_first_rate"] == "0.324032"
    assert eth["sides"]["long"]["net_after_0_31_rt"] == "-0.195263"
    assert eth["sides"]["short"]["net_after_0_31_rt"] == "-0.154463"
    assert oi["verdict"] == "FAIL"
    assert oi["family"] == "oi_delta_agree"
    assert oi["clock"] == _OI_CLOCK
    assert oi["thresholds_label"] == _OI_LABEL
    assert oi["green_year_note"] is None
    assert oi["sides"]["long"] == _OI_LONG
    assert oi["sides"]["short"] == _OI_SHORT
    assert oi["sides"]["long"]["target_first_rate"] == "0.316123"
    assert oi["sides"]["short"]["target_first_rate"] == "0.280732"
    assert oi["sides"]["long"]["net_after_0_31_rt"] == "-0.176818"
    assert oi["sides"]["short"]["net_after_0_31_rt"] == "-0.283949"


def test_zero_cells_stay_empty(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps({"note": SEALED_TABLE_NOTE, "sealed": False, "cells": []}),
        encoding="utf-8",
    )
    loaded = load_path2_findings(path)
    assert loaded["cells"] == []
    assert loaded["sealed"] is False


def test_schema_lists_both_sides_and_metric_columns() -> None:
    schema = json.loads(
        (PROJECT_ROOT / "data" / "research" / "path2_findings.schema.json").read_text(
            encoding="utf-8"
        )
    )
    side = schema["$defs"]["side"]["properties"]
    assert tuple(side) == METRIC_KEYS
    sides = schema["$defs"]["cell"]["properties"]["sides"]
    assert list(sides["properties"]) == ["long", "short"]
    assert sides["required"] == ["long", "short"]
    assert "green_year_note" in schema["$defs"]["cell"]["properties"]
    assert schema["$defs"]["cell"]["properties"]["verdict"]["enum"] == ["PASS", "FAIL", None]


def test_research_page_lists_findings_columns_in_order() -> None:
    html = (PROJECT_ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    labels = [
        "Family",
        "Clock",
        "Side",
        "Frozen thresholds",
        "n",
        "Target-first count",
        "Target-first rate",
        "Gross",
        "Net after 0.31% round trip",
        "Same-shell H=18 base net",
        "Stress stop 2% net",
        "PASS or FAIL",
        "Green year note",
    ]
    start = html.index("const PATH2_FINDING_HEADERS")
    end = html.index("];", start)
    block = html[start:end]
    cursor = 0
    for label in labels:
        found = block.index(f'"{label}"', cursor)
        assert found > cursor or cursor == 0
        cursor = found + 1
    assert "No sealed cells" in html
    assert "does not set PASS or FAIL" in html
    assert "renderPath2Findings()" in html


def test_green_year_note_does_not_set_verdict(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "note": SEALED_TABLE_NOTE,
                "sealed": True,
                "cells": [
                    {
                        "family": "example_family",
                        "clock": "4h",
                        "thresholds": {"label": "frozen line"},
                        "green_year_note": "one green year",
                        "verdict": "one green year",
                        "sides": {"long": {"n": 4}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cell = load_path2_findings(path)["cells"][0]
    assert cell["verdict"] is None
    assert cell["green_year_note"] == "one green year"
    assert cell["thresholds_label"] == "frozen line"
    assert cell["sides"]["long"]["n"] == 4
    # The short side stays on the cell, with every figure marked absent.
    assert cell["sides"]["short"] == {key: None for key in METRIC_KEYS}
    assert cell["sides"]["long"]["gross"] is None


def test_only_pass_or_fail_tokens_survive(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "note": SEALED_TABLE_NOTE,
                "sealed": True,
                "cells": [
                    {"verdict": "PASS", "sides": {"long": {}, "short": {}}},
                    {"verdict": "FAIL", "sides": {"long": {}, "short": {}}},
                    {"verdict": "pass", "sides": {"long": {}, "short": {}}},
                    {"verdict": True, "sides": {"long": {}, "short": {}}},
                ],
            }
        ),
        encoding="utf-8",
    )
    verdicts = [cell["verdict"] for cell in load_path2_findings(path)["cells"]]
    assert verdicts == ["PASS", "FAIL", None, None]


def test_bool_and_objects_are_not_metrics(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "note": SEALED_TABLE_NOTE,
                "sealed": False,
                "cells": [
                    {
                        "sides": {
                            "long": {"n": True, "gross": {"made_up": 1}, "target_first_rate": "kept"},
                            "short": {"n": False},
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cell = load_path2_findings(path)["cells"][0]
    assert cell["sides"]["long"]["n"] is None
    assert cell["sides"]["long"]["gross"] is None
    assert cell["sides"]["long"]["target_first_rate"] == "kept"
    assert cell["sides"]["short"]["n"] is None


def test_floor_helper_returns_the_sealed_rows() -> None:
    from firm.orchestrator import _safe_path2_findings

    loaded = _safe_path2_findings()
    assert loaded["sealed"] is True
    assert [cell["thresholds_label"] for cell in loaded["cells"]] == _LABELS + [_FUNDING_LABEL, _LONDON_LABEL, _MID_LABEL, _ETH_LABEL, _OI_LABEL]
    assert [cell["verdict"] for cell in loaded["cells"]] == ["FAIL"] * 15
    assert loaded["cells"][-1]["clock"] == _OI_CLOCK
    assert loaded["cells"][-1]["family"] == "oi_delta_agree"
    assert loaded["cells"][-2]["family"] == "eth_btc_return_agree"
    assert all(cell["green_year_note"] is None for cell in loaded["cells"])
