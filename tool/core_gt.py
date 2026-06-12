def analyze_gt(gt_path):
    """Parse gt.txt → (labels, char_counts, length_counts)."""
    from collections import Counter
    labels = []
    try:
        with open(gt_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t") if "\t" in line else line.split(" ", 1)
                labels.append(parts[1] if len(parts) >= 2 else "")
    except Exception:
        pass
    char_counts = Counter()
    for lbl in labels:
        for c in lbl.upper():
            if c.isalnum():
                char_counts[c] += 1
    length_counts = Counter(len(lbl) for lbl in labels)
    return labels, dict(char_counts), dict(length_counts)


def _heat_color(count, max_count):
    """Interpolate #252540 → #F05922 (sqrt scale) for heatmap cells."""
    if max_count == 0 or count == 0:
        return "#252540"
    t = (count / max_count) ** 0.5
    r = int(0x25 + (0xF0 - 0x25) * t)
    g = int(0x25 + (0x59 - 0x25) * t)
    b = int(0x40 + (0x22 - 0x40) * t)
    return f"#{r:02x}{g:02x}{b:02x}"
