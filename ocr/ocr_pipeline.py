# -*- coding: utf-8 -*-
"""概念验证：截图 → OCR → 结构化 UI 描述。

目标：将截图转换为 Agent 可直接理解的结构化数据，
替代当前的 AccessibilityService UI 树 dump。

用法:
  python ocr/ocr_pipeline.py ocr/screenshot_test.png
  python ocr/ocr_pipeline.py ocr/quark_ready.png
"""
import sys
import os
import json
import time
from rapidocr_onnxruntime import RapidOCR


# ─────────────── 工具函数 ───────────────

def box_to_rect(box):
    """将 OCR 的 4 点 box 转为 (x, y, w, h) 矩形。"""
    x1 = min(p[0] for p in box)
    y1 = min(p[1] for p in box)
    x2 = max(p[0] for p in box)
    y2 = max(p[1] for p in box)
    return {
        "x": round(x1),
        "y": round(y1),
        "w": round(x2 - x1),
        "h": round(y2 - y1),
        "cx": round((x1 + x2) / 2),
        "cy": round((y1 + y2) / 2),
    }


def classify_element(rect, text):
    """根据位置和大小粗略分类 UI 元素类型。

    这只是概念验证的启发式分类，后续用 YOLO 替换。
    """
    w, h = rect["w"], rect["h"]
    x, y = rect["x"], rect["y"]
    cx, cy = rect["cx"], rect["cy"]

    # 时间/日期（右上角）
    if x > 1000 and y < 80 and text and any(c.isdigit() for c in text):
        return "status_time"

    # 状态栏图标区
    if y < 80 and x > 600:
        return "status_bar"

    # 底部导航栏（y > 680）
    if y > 680:
        if w < 100 and h < 50:
            return "nav_icon_label"  # 底部导航的文字标签
        return "nav_area"

    # 按钮（中等大小矩形，短文本）
    if 30 < w < 200 and 20 < h < 60 and len(text) <= 6:
        return "button"

    # 标题（较大字体）
    if h > 40 or w > 300:
        return "title"

    # 普通文本
    return "text"


def ocr_screenshot(img_path, min_score=0.3):
    """对截图执行 OCR，返回结构化 UI 描述。

    Args:
        img_path: 截图文件路径
        min_score: 最低置信度阈值

    Returns:
        dict: 结构化的 UI 描述
    """
    engine = RapidOCR()

    t0 = time.time()
    result, _ = engine(img_path)
    elapsed = time.time() - t0

    # 过滤低置信度结果
    items = [item for item in result if float(item[2]) >= min_score]

    # 分类和整理
    elements = []
    for i, item in enumerate(items):
        box = item[0]
        text = item[1].strip()
        score = float(item[2])

        if not text:
            continue

        rect = box_to_rect(box)
        elem_type = classify_element(rect, text)

        elements.append({
            "id": i,
            "type": elem_type,
            "text": text,
            "score": round(score, 3),
            "rect": rect,
        })

    # 按区域分组
    zones = {
        "status_bar": [],       # 顶部状态栏
        "main_content": [],     # 主要内容区
        "nav_bar": [],          # 底部导航栏
    }

    for elem in elements:
        y = elem["rect"]["y"]
        if y < 80:
            zones["status_bar"].append(elem)
        elif y > 680:
            zones["nav_bar"].append(elem)
        else:
            zones["main_content"].append(elem)

    return {
        "image": os.path.basename(img_path),
        "resolution": "1280x800",  # 可从实际图片读取
        "ocr_time_ms": round(elapsed * 1000),
        "total_elements": len(elements),
        "zones": zones,
    }


# ─────────────── 输出可读摘要 ───────────────

def print_summary(data):
    """打印可读的 UI 摘要。"""
    print(f"\n {data['image']} ({data['resolution']})")
    print(f"   OCR 耗时: {data['ocr_time_ms']:.0f}ms")
    print(f"   识别到 {data['total_elements']} 个 UI 元素\n")

    zone_names = {
        "status_bar": " 顶部状态栏",
        "main_content": "🎬 主要内容区",
        "nav_bar": " 底部导航栏",
    }

    for zone_key, zone_label in zone_names.items():
        elems = data["zones"].get(zone_key, [])
        if not elems:
            continue
        print(f"  {zone_label} ({len(elems)} 个):")
        for e in elems:
            r = e["rect"]
            print(f"    [{e['type']:20s}] \"{e['text']}\" @ ({r['cx']},{r['cy']})")
    print()


# ─────────────── 入口 ───────────────

def main():
    if len(sys.argv) < 2:
        # 默认测试所有截图
        ocr_dir = os.path.dirname(os.path.abspath(__file__))
        images = [
            os.path.join(ocr_dir, f)
            for f in sorted(os.listdir(ocr_dir))
            if f.endswith((".png", ".jpg", ".jpeg"))
        ]
    else:
        images = sys.argv[1:]

    for img_path in images:
        if not os.path.exists(img_path):
            print(f"❌ 文件不存在: {img_path}")
            continue

        data = ocr_screenshot(img_path)
        print_summary(data)

        # 同时输出 JSON（供 Agent 消费）
        json_path = img_path.rsplit(".", 1)[0] + "_ui.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   → JSON 已保存: {json_path}")


if __name__ == "__main__":
    main()
