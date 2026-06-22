"""
运行所有本地单元测试。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests import test_data, test_engine, test_portfolio, test_web


def main():
    suites = [
        ("数据层", test_data.run_tests),
        ("回测引擎", test_engine.run_tests),
        ("Web 层", test_web.run_tests),
        ("投资监控", test_portfolio.run_tests),
    ]
    total_passed = 0
    total_failed = 0

    for name, run in suites:
        print("=" * 50)
        print(f"🧪 {name}测试套件")
        print("=" * 50)
        passed, failed = run()
        total_passed += passed
        total_failed += failed

    print("\n" + "=" * 50)
    print(f"总结果: {total_passed} 通过, {total_failed} 失败 / {total_passed + total_failed} 总")
    print("=" * 50)
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
