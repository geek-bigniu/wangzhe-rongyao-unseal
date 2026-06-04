# 王者荣耀答题题库工具

用于王者荣耀答题任务的本地题库缓存、答案枚举尝试、批量构建题库，以及根据缓存生成 Markdown 题库文档。

## 功能

- 从接口读取当前题目和选项。
- 本地缓存已命中的答案，后续遇到相同题目可直接使用缓存答案。
- 支持单选题和多选题答案组合枚举。
- 支持批量、多线程构建题库缓存。
- 支持将 `answer_cache.json` 生成 Markdown 题库文档，图片和视频会按 Markdown/HTML 媒体引用展示。

## 环境要求

- Python 3.8+
- 依赖库：`requests`

安装依赖：

```bash
pip install requests
```

## 配置

复制 `.env.example` 为 `.env`，然后填写完整 Cookie。

```env
scene_info=E29F655B9B0A7FAED50DEFA6D7B3CFDA712A1C46A27D92E014B33A42AFA29AFB559F80D24AAAB29B58044911665E24D6F765049E0F66A9F7F555AE13918C0A0294CEF2B33CFD84E47C32CF6463E762BBBC91B571C0B2F06F44264ABED45DC60C61FCB8A24984AC18859BB0683B908FA536564B69BD943D1CCFE6908C607D3E1B
cookie=access_token=...; active_uin=...; applet_code=...; openid=...
```

说明：

- `scene_info`：任务页面请求里的 `scene_info` 参数。
- `cookie`：完整 Cookie 字符串，必须包含 `openid`，脚本会自动从 Cookie 中解析 `user_id`。
- `.env` 已加入 `.gitignore`，不会提交到仓库。

## 使用方式

运行一次答题流程：

```bash
python main.py
```

批量构建题库缓存：

```bash
python main.py --build-bank --rounds 100
```

多线程批量构建题库缓存：

```bash
python main.py --build-bank --rounds 1000 --workers 5 --round-delay 0.5
```

批量模式默认不在每轮结束时提交最终任务。如果需要每轮也提交 `verify/finish`：

```bash
python main.py --build-bank --rounds 100 --submit-final
```

## 参数说明

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--build-bank` | 启用批量构建题库模式 | 关闭 |
| `--rounds` | 批量轮数 | `10` |
| `--round-delay` | 每轮之间等待秒数 | `2.0` |
| `--workers` | 批量线程数 | `1` |
| `--submit-final` | 批量模式每轮也提交最终任务 | 关闭 |

## 题库缓存

答案缓存文件为 `answer_cache.json`，脚本会自动维护。缓存内容包含：

- 题目标题
- 题型
- 选项列表
- 答案序号
- 答案文字列表
- 选项映射

`answer_cache.json` 已加入 `.gitignore`，默认不会提交。

## 生成 Markdown 题库

根据本地缓存生成题库文档：

```bash
python generate_question_bank_md.py
```

生成全量题库：

```bash
python generate_question_bank_md.py --limit 0
```

指定输入和输出：

```bash
python generate_question_bank_md.py --cache answer_cache.json --output question_bank_template.md --limit 0
```

生成的文档会在标题下方展示统计数据，并按以下顺序展示内容：

1. 题目
2. 题型
3. 选项
4. 答案文字

如果题目、选项或答案中包含图片/视频链接，会渲染为图片或视频引用。

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `main.py` | 答题、爆破和缓存主脚本 |
| `env_utils.py` | `.env` 读取工具 |
| `.env.example` | 配置模板 |
| `generate_question_bank_md.py` | 题库 Markdown 生成脚本 |
| `question_bank_template.md` | 题库 Markdown 示例输出 |
| `营地自动签到.py` | 王者营地签到脚本 |
| `run_signin_script.bat` | 签到脚本批处理入口 |

## 注意事项

- Cookie 有有效期，失效后需要重新抓取并更新 `.env`。
- 批量构建题库会频繁请求接口，建议合理设置 `--round-delay` 和 `--workers`。
- 运行前确认 `.env` 中的 `cookie` 包含 `openid`，否则脚本会提示 `cookie missing openid`。
