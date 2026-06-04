import argparse
import json
import re
from pathlib import Path


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".ogg", ".mov", ".m4v")
URL_RE = re.compile(r"https?://[^\s)>\"]+")


def strip_url_tail(url):
    return url.split("?", 1)[0].split("#", 1)[0].lower()


def media_refs(text, label):
    refs = []
    for index, url in enumerate(URL_RE.findall(str(text or "")), start=1):
        clean_url = strip_url_tail(url)
        media_label = f"{label}{index}"
        if clean_url.endswith(IMAGE_EXTENSIONS):
            refs.append(f"![{media_label}]({url})")
        elif clean_url.endswith(VIDEO_EXTENSIONS):
            refs.append(f'<video controls src="{url}" title="{media_label}"></video>')
        else:
            refs.append(f"[{media_label}]({url})")
    return refs


def question_type_label(question_type):
    return "多选" if question_type == 2 else "单选"


def normalize_entry(entry):
    options = entry.get("option_texts") or entry.get("options") or []
    answer = str(entry.get("answer", ""))
    answer_texts = entry.get("answer_texts")
    if not answer_texts:
        answer_texts = []
        for part in answer.split("|"):
            try:
                option_index = int(part) - 1
            except ValueError:
                continue
            if 0 <= option_index < len(options):
                answer_texts.append(options[option_index])
    option_map = entry.get("option_map") or {
        str(index): option for index, option in enumerate(options, start=1)
    }
    return options, answer, answer_texts, option_map


def render_entry(index, entry):
    title = entry.get("question_title", "").strip() or f"未命名题目 {index}"
    question_type = question_type_label(entry.get("question_type", 1))
    options, answer, answer_texts, option_map = normalize_entry(entry)

    lines = [
        f"## {index}. {title}",
        "",
        f"**题型：{question_type}**",
    ]

    question_media = media_refs(title, f"题目媒体{index}-")
    if question_media:
        lines.extend(["", "### 题目媒体", ""])
        lines.extend(question_media)

    lines.extend(["", "### 选项", ""])
    for option_index, option_text in option_map.items():
        lines.append(f"{option_index}. {option_text}")
        for media in media_refs(option_text, f"选项{index}-{option_index}-"):
            lines.append(f"   {media}")

    lines.extend([
        "",
        "### 答案",
        "",
        f"{', '.join(answer_texts) if answer_texts else '未解析'}",
        "",
    ])
    return "\n".join(lines)


def render_markdown(cache, limit=None):
    entries = list(cache.values())
    if limit:
        entries = entries[:limit]

    lines = [
        "# 王者荣耀答题题库模板",
        "",
    ]

    for index, entry in enumerate(entries, start=1):
        lines.append(render_entry(index, entry))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate Markdown question bank from answer_cache.json")
    parser.add_argument("--cache", default="answer_cache.json", help="答案缓存 JSON 路径")
    parser.add_argument("--output", default="question_bank_template.md", help="输出 Markdown 路径")
    parser.add_argument("--limit", type=int, default=10, help="模板展示题目数量，0 表示全量")
    args = parser.parse_args()

    cache_path = Path(args.cache)
    output_path = Path(args.output)
    with cache_path.open("r", encoding="utf-8") as file:
        cache = json.load(file)

    limit = args.limit if args.limit > 0 else None
    output_path.write_text(render_markdown(cache, limit=limit), encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
