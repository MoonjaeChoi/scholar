#!/usr/bin/env python3
# Generated: 2025-10-14 11:30:00 KST
"""
Simple test script for PathDiversityCrawler

Run without pytest dependency
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from crawler.path_diversity_crawler import PathDiversityCrawler


def test_path_fingerprinting():
    """Path fingerprinting 테스트"""
    print("\n" + "=" * 80)
    print("TEST: Path Fingerprinting")
    print("=" * 80)

    db_config = {
        'host': 'localhost',
        'port': '1521',
        'service_name': 'XEPDB1',
        'username': 'test',
        'password': 'test'
    }

    crawler = PathDiversityCrawler(db_config=db_config)

    test_cases = [
        ("/article/123/view", "/article/*/view"),
        ("/article/456/view", "/article/*/view"),
        ("/news/2025/10/14/story", "/news/*/*/story"),
        ("/post/550e8400-e29b-41d4-a716-446655440000", "/post/UUID"),
        ("/board/notice/12345", "/board/notice/*")
    ]

    passed = 0
    failed = 0

    for url, expected in test_cases:
        result = crawler.create_path_fingerprint(url)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {url:50s} → {result}")

        if result == expected:
            passed += 1
        else:
            print(f"    Expected: {expected}")
            failed += 1

    print(f"\n  Passed: {passed}/{len(test_cases)}")

    return failed == 0


def test_link_priority():
    """링크 우선순위 계산 테스트"""
    print("\n" + "=" * 80)
    print("TEST: Link Priority Calculation")
    print("=" * 80)

    db_config = {
        'host': 'localhost',
        'port': '1521',
        'service_name': 'XEPDB1',
        'username': 'test',
        'password': 'test'
    }

    crawler = PathDiversityCrawler(db_config=db_config)

    # 첫 방문 우선순위
    url = "/article/123"
    priority1 = crawler.calculate_link_priority(url, depth=2)
    print(f"  First visit:  {url:30s} priority={priority1:.2f}")

    # 방문 기록 추가
    pattern = crawler.create_path_fingerprint(url)
    crawler.path_history[pattern] = 5

    # 재방문 우선순위
    priority2 = crawler.calculate_link_priority(url, depth=2)
    print(f"  After visits: {url:30s} priority={priority2:.2f}")

    # 우선순위가 감소했는지 확인
    if priority2 < priority1:
        print(f"  ✓ Priority decreased correctly ({priority1:.2f} → {priority2:.2f})")
        return True
    else:
        print(f"  ✗ Priority should decrease after visits")
        return False


def test_diverse_link_selection():
    """다양성 링크 선택 테스트"""
    print("\n" + "=" * 80)
    print("TEST: Diverse Link Selection")
    print("=" * 80)

    db_config = {
        'host': 'localhost',
        'port': '1521',
        'service_name': 'XEPDB1',
        'username': 'test',
        'password': 'test'
    }

    crawler = PathDiversityCrawler(db_config=db_config)

    test_links = [
        "/article/1/view",
        "/article/2/view",
        "/article/3/view",
        "/board/100/read",
        "/board/101/read",
        "/news/20251014/story",
        "/news/20251013/story",
        "/blog/post-title-1",
        "/blog/post-title-2"
    ]

    print(f"  Input: {len(test_links)} links")

    selected = crawler.select_diverse_links(test_links, max_count=5)

    print(f"  Selected {len(selected)} links:")
    for link in selected:
        pattern = crawler.create_path_fingerprint(link)
        print(f"    - {link:30s} [{pattern}]")

    # 다양한 패턴이 포함되었는지 확인
    patterns = set(crawler.create_path_fingerprint(link) for link in selected)
    print(f"\n  Unique patterns: {len(patterns)}")

    if len(patterns) >= 3:
        print(f"  ✓ Good diversity ({len(patterns)} unique patterns)")
        return True
    else:
        print(f"  ✗ Poor diversity (only {len(patterns)} patterns)")
        return False


def test_diversity_report():
    """다양성 리포트 생성 테스트"""
    print("\n" + "=" * 80)
    print("TEST: Diversity Report")
    print("=" * 80)

    db_config = {
        'host': 'localhost',
        'port': '1521',
        'service_name': 'XEPDB1',
        'username': 'test',
        'password': 'test'
    }

    crawler = PathDiversityCrawler(db_config=db_config)

    # 방문 기록 추가
    crawler.path_history["/article/*/view"] = 10
    crawler.path_history["/board/*/read"] = 5
    crawler.path_history["/news/*/*/story"] = 3
    crawler.path_fingerprints.update([
        "/article/*/view",
        "/board/*/read",
        "/news/*/*/story"
    ])

    report = crawler.get_path_diversity_report()

    print(f"  Unique patterns: {report['unique_patterns']}")
    print(f"  Total visits: {report['total_visits']}")
    print(f"  Diversity score: {report['diversity_score']:.2%}")
    print(f"\n  Top patterns:")
    for item in report['top_patterns']:
        print(f"    - {item['pattern']:30s} {item['visits']:3d} visits")

    # 검증
    if (report['unique_patterns'] == 3 and
        report['total_visits'] == 18 and
        abs(report['diversity_score'] - (3/18)) < 0.01):
        print(f"\n  ✓ Report generated correctly")
        return True
    else:
        print(f"\n  ✗ Report values incorrect")
        return False


def main():
    """모든 테스트 실행"""
    print("\n" + "=" * 80)
    print("  PathDiversityCrawler Unit Tests")
    print("=" * 80)

    results = []

    # 테스트 실행
    results.append(("Path Fingerprinting", test_path_fingerprinting()))
    results.append(("Link Priority", test_link_priority()))
    results.append(("Diverse Link Selection", test_diverse_link_selection()))
    results.append(("Diversity Report", test_diversity_report()))

    # 결과 요약
    print("\n" + "=" * 80)
    print("  Test Results")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:10s} {name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  ✅ All tests PASSED!")
        return 0
    else:
        print(f"\n  ❌ {total - passed} test(s) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
