"""
数据层单元测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from scripts.fetch_data import normalize_ohlcv


def test_normalize_close_only_fund_data_to_ohlcv():
    """测试只有净值/收盘价的数据会被补齐为标准 OHLCV"""
    raw = pd.DataFrame({
        "date": ["2023-01-01", "2023-01-02"],
        "close": [1.01, 1.02],
    })

    df = normalize_ohlcv(raw)

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["open"].tolist() == [1.01, 1.02]
    assert df["high"].tolist() == [1.01, 1.02]
    assert df["low"].tolist() == [1.01, 1.02]
    assert df["volume"].tolist() == [0, 0]
    print("✅ test_normalize_close_only_fund_data_to_ohlcv PASS")


def test_normalize_renamed_chinese_columns_to_ohlcv():
    """测试中文行情字段可以被标准化为英文 OHLCV"""
    raw = pd.DataFrame({
        "日期": ["2023-01-01"],
        "开盘": [10.0],
        "最高": [11.0],
        "最低": [9.5],
        "收盘": [10.5],
        "成交量": [10000],
    })

    df = normalize_ohlcv(raw)

    assert df.loc[0, "open"] == 10.0
    assert df.loc[0, "high"] == 11.0
    assert df.loc[0, "low"] == 9.5
    assert df.loc[0, "close"] == 10.5
    assert df.loc[0, "volume"] == 10000
    print("✅ test_normalize_renamed_chinese_columns_to_ohlcv PASS")


def run_tests():
    tests = [
        test_normalize_close_only_fund_data_to_ohlcv,
        test_normalize_renamed_chinese_columns_to_ohlcv,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAIL: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    print(f"结果: {passed} 通过, {failed} 失败 / {passed + failed} 总")
    sys.exit(1 if failed else 0)
