# Generated: 2025-10-01 15:30:00 KST
# Fix train_list.txt and val_list.txt paths to relative format

import os

def fix_paths(input_file, output_file):
    """Convert absolute paths to relative paths (images/xxx.jpg format)"""
    fixed_lines = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                # Extract filename from absolute path
                img_path = parts[0]
                img_name = os.path.basename(img_path)
                # Convert to relative path: images/image_10.jpg
                relative_path = f"images/{img_name}"
                parts[0] = relative_path
                fixed_lines.append('\t'.join(parts) + '\n')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

    print(f"Fixed {input_file} -> {output_file}: {len(fixed_lines)} lines")

# Fix both train and val lists
fix_paths('data/train_list.txt', 'data/train_list.txt')
fix_paths('data/val_list.txt', 'data/val_list.txt')

print("\nSample from train_list.txt:")
with open('data/train_list.txt', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i < 3:
            print(line.strip())
        else:
            break
