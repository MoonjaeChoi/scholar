#!/usr/bin/env python3.9
# Generated: 2025-10-02 18:42:00 KST
"""
PaddleOCR Detection 모델 학습 래퍼 스크립트
RecursionError 방지를 위해 Python recursion limit을 대폭 증가시킴

문제: shapely.geometry.Polygon() 생성 시 RecursionError 발생
해결: sys.setrecursionlimit()을 100000으로 설정
"""

import sys
import os

# ⚠️ RecursionError 방지: Python recursion limit을 대폭 증가
# 기본값: 1000
# 새 값: 100000 (100배 증가)
# Shapely Polygon 생성 시 깊은 재귀 호출이 발생하는 문제 해결
OLD_LIMIT = sys.getrecursionlimit()
NEW_LIMIT = 100000
sys.setrecursionlimit(NEW_LIMIT)

print(f"=" * 60)
print(f"[RECURSION FIX] Recursion limit increased")
print(f"  Old limit: {OLD_LIMIT}")
print(f"  New limit: {NEW_LIMIT}")
print(f"=" * 60)

# PaddleOCR 디렉토리로 이동
os.chdir("/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR")

# sys.argv 설정
sys.argv = [
    "tools/train.py",
    "-c",
    "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/data_new_training.yml"
]

# PaddleOCR train.py 실행
import runpy
runpy.run_path("tools/train.py", run_name="__main__")
