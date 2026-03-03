# Generated: 2025-10-02 12:45:00 KST
# Analyze bounding box distribution in training data

import json

def analyze_bbox_distribution():
    """Analyze bounding box count distribution in train_list.txt"""

    # Read train_list.txt
    with open("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    box_counts = []
    for line in lines:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            labels = json.loads(parts[1])
            box_counts.append(len(labels))

    print(f"총 학습 샘플 수: {len(box_counts)}")
    print(f"\nBounding Box 개수 통계:")
    print(f"  최소: {min(box_counts)}")
    print(f"  최대: {max(box_counts)}")
    print(f"  평균: {sum(box_counts)/len(box_counts):.1f}")
    print(f"  중간값: {sorted(box_counts)[len(box_counts)//2]}")

    print(f"\n분포:")
    print(f"  0-10 boxes: {sum(1 for x in box_counts if x <= 10)}")
    print(f"  11-50 boxes: {sum(1 for x in box_counts if 10 < x <= 50)}")
    print(f"  51-100 boxes: {sum(1 for x in box_counts if 50 < x <= 100)}")
    print(f"  100+ boxes: {sum(1 for x in box_counts if x > 100)}")

if __name__ == "__main__":
    analyze_bbox_distribution()
