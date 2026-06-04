import argparse
import json
import re
from pathlib import Path


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".ogg", ".mov", ".m4v")
URL_RE = re.compile(r"https?://[^\s)>\"]+")


def strip_url_tail(url):
    return url.split("?", 1)[0].split("#", 1)[0].lower()


def is_image_url(url):
    return strip_url_tail(url).endswith(IMAGE_EXTENSIONS)


def is_video_url(url):
    return strip_url_tail(url).endswith(VIDEO_EXTENSIONS)


def render_value(text, label):
    text = str(text or "").strip()
    urls = URL_RE.findall(text)
    if not urls:
        return [text] if text else []

    rendered = []
    remaining_text = URL_RE.sub("", text).strip()
    if remaining_text:
        rendered.append(remaining_text)

    for index, url in enumerate(urls, start=1):
        media_label = f"{label}{index}"
        if is_image_url(url):
            rendered.append(f"![{media_label}]({url})")
        elif is_video_url(url):
            rendered.append(f'<video controls src="{url}" title="{media_label}"></video>')
        else:
            rendered.append(f"[{media_label}]({url})")

    return rendered


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
    return answer_texts, option_map


def append_rendered_block(lines, rendered_items, indent=""):
    if not rendered_items:
        return
    lines.extend(f"{indent}{item}" for item in rendered_items)


def render_entry(index, entry):
    title = entry.get("question_title", "").strip() or f"未命名题目 {index}"
    question_type = question_type_label(entry.get("question_type", 1))
    answer_texts, option_map = normalize_entry(entry)

    lines = [
        f"## {index}. {title}",
        "",
        f"**题型：{question_type}**",
    ]

    title_media = render_value(title, f"题目媒体{index}-")
    if len(title_media) > 1 or (title_media and title_media[0] != title):
        lines.extend(["", "### 题目媒体", ""])
        append_rendered_block(lines, title_media)

    lines.extend(["", "### 选项", ""])
    for option_index, option_text in option_map.items():
        rendered_option = render_value(option_text, f"选项{index}-{option_index}-")
        if len(rendered_option) == 1:
            lines.append(f"{option_index}. {rendered_option[0]}")
        else:
            lines.append(f"{option_index}.")
            append_rendered_block(lines, rendered_option, indent="   ")

    lines.extend(["", "### 答案", ""])
    rendered_answers = []
    for answer_index, answer_text in enumerate(answer_texts, start=1):
        rendered_answers.extend(render_value(answer_text, f"答案{index}-{answer_index}-"))
    if rendered_answers:
        append_rendered_block(lines, rendered_answers)
    else:
        lines.append("未解析")

    lines.append("")
    return "\n".join(lines)


def render_markdown(cache, limit=None):
    entries = list(cache.values())
    if limit:
        entries = entries[:limit]

    single_count = sum(1 for entry in entries if entry.get("question_type", 1) != 2)
    multiple_count = sum(1 for entry in entries if entry.get("question_type", 1) == 2)

    lines = [
        "# 王者荣耀答题题库模板",
        "",
        f"- 题目总数: {len(entries)}",
        f"- 单选: {single_count}",
        f"- 多选: {multiple_count}",
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
