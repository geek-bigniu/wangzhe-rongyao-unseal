import time

import requests
from itertools import combinations
import urllib.parse
import json
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from env_utils import load_env, require_env

load_env()

ANSWER_CACHE_PATH = Path(__file__).with_name("answer_cache.json")
CACHE_LOCK = threading.Lock()
REQUEST_TIMEOUT = 15
MAX_REQUEST_RETRIES = 3
RETRY_DELAY_SECONDS = 1.5
TRY_ANSWER_DELAY_SECONDS = 0.3

BASE_TASK_URL = "https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks"
GAME_ID = "2577"
TASK_ID = "9"
AGREE_TASK_ID = "10"
SCENE_INFO = require_env("scene_info")
COOKIE = require_env("cookie")


def get_cookie_value(name):
    for item in COOKIE.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return urllib.parse.unquote(value.strip())
    return ""


USER_ID = get_cookie_value("openid")
if not USER_ID:
    raise RuntimeError("cookie missing openid")


headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.71(0x18004730) NetType/WIFI Language/zh_CN miniProgram/wx39542b01b40b6909",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Mode": "cors",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Sec-Fetch-Site": "same-origin",
    "Referer": f"https://wx.gamesafe.qq.com/static/proxy/intervention/index.html?gameId={GAME_ID}&sceneInfo={SCENE_INFO}&taskId={TASK_ID}&op_type=get_question",
    "Sec-Fetch-Dest": "empty",
}


def request_with_retry(method, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)

    for attempt in range(1, MAX_REQUEST_RETRIES + 1):
        try:
            return method(url, **kwargs)
        except requests.exceptions.RequestException as exc:
            print(f"请求异常，第 {attempt}/{MAX_REQUEST_RETRIES} 次: {exc}")
            if attempt >= MAX_REQUEST_RETRIES:
                return None
            time.sleep(RETRY_DELAY_SECONDS * attempt)


def getInfo(seed, answer=""):
    """
    根据种子获取题目信息
    :param seed:  题目种子
    :param answer:  答案
    :return:
    """
    url = f"{BASE_TASK_URL}/get_seed_info"
    params = {
        "user_id": USER_ID,
        "game_id": GAME_ID,
        "scene_info": SCENE_INFO,
        "task_id": TASK_ID,
        "seed": seed
        # "answer": str(answer)
    }
    if answer:
        # 如果答案不为空，进行 URL 编码
        params['answer'] = str(answer)

    response = request_with_retry(requests.get, url, params=params, headers=headers)
    return response


def generate_answers(is_multiple_choice, option_count=4):
    """生成所有可能的答案组合"""
    options = list(range(1, option_count + 1))
    if not is_multiple_choice:
        # 单选题：返回 1, 2, 3, 4
        return [str(i) for i in options]
    else:
        # 多选题：返回所有组合，例如 1, 1|2, 1|2|3, 1|2|3|4 等
        answers = []
        for r in range(2, len(options) + 1):
            for combo in combinations(options, r):
                answers.append("|".join(str(i) for i in combo))
        return answers


def normalize_text(text):
    """Normalize question and option text for stable local matching."""
    return " ".join(str(text or "").split())


def extract_options(page_cfg):
    """Best-effort extraction of option labels from page_cfg."""
    option_keys = (
        "question_answers",
        "options",
        "option_list",
        "question_options",
        "answer_options",
        "items",
    )
    text_keys = ("title", "text", "content", "name", "desc", "label", "value")

    for key in option_keys:
        value = page_cfg.get(key)
        if not isinstance(value, list):
            continue

        options = []
        for item in value:
            if isinstance(item, dict):
                option_text = ""
                for text_key in text_keys:
                    if item.get(text_key):
                        option_text = item.get(text_key)
                        break
                if not option_text:
                    option_text = json.dumps(item, ensure_ascii=False, sort_keys=True)
            else:
                option_text = item

            option_text = normalize_text(option_text)
            if option_text:
                options.append(option_text)

        if options:
            return options

    return []


def build_question_key(page_cfg):
    question_title = normalize_text(page_cfg.get("question_title", ""))
    options = extract_options(page_cfg)
    if options:
        return question_title + "\n" + "\n".join(options)
    return question_title


def get_answer_texts(page_cfg, answer):
    return get_answer_texts_from_options(extract_options(page_cfg), answer)


def get_answer_texts_from_options(options, answer):
    answer_texts = []
    for index_text in str(answer).split("|"):
        try:
            option_index = int(index_text) - 1
        except ValueError:
            continue
        if 0 <= option_index < len(options):
            answer_texts.append(options[option_index])
    return answer_texts


def build_option_map(page_cfg):
    return build_option_map_from_options(extract_options(page_cfg))


def build_option_map_from_options(options):
    return {
        str(index): option_text
        for index, option_text in enumerate(options, start=1)
    }


def migrate_answer_cache(cache):
    changed = False
    for entry in cache.values():
        if not isinstance(entry, dict):
            continue

        options = entry.get("option_texts") or entry.get("options") or []
        answer = str(entry.get("answer", ""))
        if not isinstance(options, list):
            continue

        if "option_texts" not in entry:
            entry["option_texts"] = options
            changed = True
        if "option_map" not in entry:
            entry["option_map"] = build_option_map_from_options(options)
            changed = True
        if "answer_texts" not in entry:
            entry["answer_texts"] = get_answer_texts_from_options(options, answer)
            changed = True

    return changed


def migrate_answer_cache_file():
    with CACHE_LOCK:
        cache = load_answer_cache()
        if migrate_answer_cache(cache):
            save_answer_cache(cache)
            print("已迁移旧题库缓存，补全 answer_texts / option_texts / option_map")


def load_answer_cache():
    if not ANSWER_CACHE_PATH.exists():
        return {}

    try:
        with ANSWER_CACHE_PATH.open("r", encoding="utf-8") as file:
            cache = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取答案缓存失败，将临时使用空缓存: {exc}")
        return {}

    if not isinstance(cache, dict):
        print("答案缓存格式不是对象，将临时使用空缓存")
        return {}

    return cache


def save_answer_cache(cache):
    tmp_path = ANSWER_CACHE_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_path.replace(ANSWER_CACHE_PATH)


def get_cached_answer(cache, page_cfg, valid_answers):
    key = build_question_key(page_cfg)
    entry = cache.get(key)
    if not entry:
        return None

    answer = str(entry.get("answer", ""))
    if answer not in valid_answers:
        print(f"命中缓存但答案不适用于当前题型，忽略: {answer}")
        return None

    return answer


def record_answer(cache, page_cfg, answer):
    key = build_question_key(page_cfg)
    if not key:
        return False

    option_texts = extract_options(page_cfg)
    entry = {
        "answer": str(answer),
        "answer_texts": get_answer_texts(page_cfg, answer),
        "question_title": normalize_text(page_cfg.get("question_title", "")),
        "question_type": page_cfg.get("question_type", 1),
        "options": option_texts,
        "option_texts": option_texts,
        "option_map": build_option_map(page_cfg),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with CACHE_LOCK:
        latest_cache = load_answer_cache()
        old_answer = str(latest_cache.get(key, {}).get("answer", ""))
        changed = old_answer != str(answer)
        latest_cache[key] = entry
        save_answer_cache(latest_cache)
        cache.clear()
        cache.update(latest_cache)

    if old_answer and old_answer != str(answer):
        print(f"已更新本地答案缓存: {old_answer} -> {answer}")
    else:
        print(f"已记录本地答案缓存: {answer}")


    return changed


def main(submit_final=True):
    answer_cache = load_answer_cache()
    learned_count = 0
    res = getTaskInfo()
    if not res:
        print("获取任务信息失败，退出")
        return
    print(res)
    if res.get("err") != 0 or not isinstance(res.get("data"), dict) or not res["data"].get("seed"):
        print(f"get_task_info returned invalid data, stop: {res}")
        return
    origin_seed = res['data']['seed']
    seed = origin_seed
    # 获取当前题目信息（使用默认答案 0 以获取题目）
    response = getInfo(seed)
    if response is None:
        print("获取题目信息失败，退出")
        return
    if response.status_code != 200:
        print(f"请求失败，状态码: {response.status_code}")
        return

    res = response.json()

    while True:
        print(res)
        data = res.get("data", {})
        print(res.get("err", 1))
        if res.get("err", 1) != 0:
            print(f"请求错误: {res}")
            return

        # 获取题目信息
        if not isinstance(data, dict):
            print(f"get_seed_info returned invalid data, stop: {res}")
            return
        page_cfg = data.get("page_cfg", {})
        question_no = page_cfg.get("question_no", 0)
        question_total = page_cfg.get("question_total", 0)
        question_type = page_cfg.get("question_type", 1)
        question_title = page_cfg.get("question_title", "")
        print(f"第 {question_no}/{question_total} 题: {question_title}")
        # 判断是否为多选题
        is_multiple_choice = question_type == 2
        option_count = len(page_cfg.get("question_answers", [])) or 4

        # 生成答案组合
        answers = generate_answers(is_multiple_choice, option_count)
        print(f"答案组合: {answers}")
        last_answer = ""

        cached_answer = get_cached_answer(answer_cache, page_cfg, answers)
        if cached_answer:
            print(f"命中本地答案缓存，直接提交: {cached_answer}")
            response = getInfo(seed, cached_answer)
            if response is None:
                print("提交缓存答案请求失败，回退枚举")
            elif response.status_code == 200:
                res = response.json()
                if 'data' in res and res['data']['seed'] != seed:
                    last_answer = cached_answer
                    print(f"第 {question_no} 题缓存答案正确: {cached_answer}")
                    seed = res['data']['seed']
                    if question_no + 1 == question_total:
                        print("最后一题的seed:", res['data']['seed'])
                        origin_seed = res['data']['seed']
                    if question_no >= question_total:
                        print("已完成所有题目！")
                        break
                    continue
                print(f"缓存答案 {cached_answer} 未通过，回退枚举")
            else:
                print(f"提交缓存答案失败，状态码: {response.status_code}，回退枚举")

        # 枚举答案
        for answer in answers:
            print(f"尝试答案: {answer}")
            response = getInfo(seed, answer)
            time.sleep(TRY_ANSWER_DELAY_SECONDS)
            if response is None:
                print(f"提交答案 {answer} 请求失败，继续尝试下一个")
                continue
            if response.status_code != 200:
                print(f"提交答案失败，状态码: {response.status_code}")
                continue

            res = response.json()
            # print(res)
            if 'data' in res and res['data']['seed'] != seed:
                last_answer = answer
                print(f"第 {question_no} 题答对了，答案: {answer}")
                if record_answer(answer_cache, page_cfg, answer):
                    learned_count += 1
                seed = res['data']['seed']  # 更新 seed
                break
            else:
                print(f"答案 {answer} 错误")
        else:
            print(f"第 {question_no} 题无正确答案，退出")
            break
        if question_no+1 == question_total:
            print("最后一题的seed:", res['data']['seed'])
            origin_seed= res['data']['seed']
        # 检查是否到达最后一题
        if question_no >= question_total:
            print("已完成所有题目！")
            break
    if not submit_final:
        return learned_count
    res = verify_task(origin_seed, TASK_ID, last_answer)
    print(res.json() if res is not None else "verify task 9 request failed")
    res = verify_task(origin_seed, AGREE_TASK_ID, last_answer)
    print(res.json() if res is not None else "verify task 10 request failed")
    res = finishTask(GAME_ID)
    print(res)
    return learned_count


def build_bank(rounds=10, round_delay=2.0, submit_final=False):
    total_learned = 0
    for round_no in range(1, rounds + 1):
        print(f"\n=== 批量爆破题库 {round_no}/{rounds} ===")
        learned_count = main(submit_final=submit_final) or 0
        total_learned += learned_count
        print(f"本轮新增或更新: {learned_count}，累计新增或更新: {total_learned}")
        if round_no < rounds and round_delay > 0:
            time.sleep(round_delay)
    print(f"批量爆破结束，累计新增或更新: {total_learned}")


def run_bank_round(round_no, rounds, submit_final):
    print(f"\n=== 批量爆破题库 {round_no}/{rounds} ===")
    learned_count = main(submit_final=submit_final) or 0
    print(f"第 {round_no} 轮新增或更新: {learned_count}")
    return learned_count


def build_bank(rounds=10, round_delay=2.0, submit_final=False, workers=1):
    total_learned = 0
    workers = max(1, min(workers, rounds))

    if workers == 1:
        for round_no in range(1, rounds + 1):
            learned_count = run_bank_round(round_no, rounds, submit_final)
            total_learned += learned_count
            print(f"累计新增或更新: {total_learned}")
            if round_no < rounds and round_delay > 0:
                time.sleep(round_delay)
    else:
        print(f"启动多线程批量爆破: rounds={rounds}, workers={workers}")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for round_no in range(1, rounds + 1):
                futures.append(executor.submit(run_bank_round, round_no, rounds, submit_final))
                if round_no < rounds and round_delay > 0:
                    time.sleep(round_delay)
            for future in as_completed(futures):
                total_learned += future.result()
                print(f"累计新增或更新: {total_learned}")

    print(f"批量爆破结束，累计新增或更新: {total_learned}")


def parse_args():
    parser = argparse.ArgumentParser(description="王者荣耀答题脚本")
    parser.add_argument("--build-bank", action="store_true", help="批量爆破题库并写入 answer_cache.json")
    parser.add_argument("--rounds", type=int, default=10, help="批量爆破轮数，默认 10")
    parser.add_argument("--round-delay", type=float, default=2.0, help="每轮之间的等待秒数，默认 2")
    parser.add_argument("--workers", type=int, default=1, help="批量爆破线程数，默认 1")
    parser.add_argument("--submit-final", action="store_true", help="批量模式下每轮也提交 verify/finish")
    return parser.parse_args()

def verify_task(seed, task_id=TASK_ID, answer="1"):
    """
    提交答案
    :param seed:
    :param task_id: 9 验证答题任务， 10 验证同意协议任务
    :param answer: 1 正确答案， 0 错误答案
    :return:
    """
    url = f"{BASE_TASK_URL}/verify_task"
    data = {
        "user_id": USER_ID,
        "game_id": GAME_ID,
        "scene_info": SCENE_INFO,
        "task_id": task_id,
        "seed": seed,
        "answer": answer
    }
    print(data)
    response = request_with_retry(requests.post, url, data=data, headers=headers)
    time.sleep(1)  # 添加延时
    return response


def getTaskInfo():
    """
    获取题目种子信息
    :return:
    """
    url = f"{BASE_TASK_URL}/get_task_info"
    params = {
        "user_id": USER_ID,
        "game_id": GAME_ID,
        "task_id": TASK_ID,
        "scene_info": SCENE_INFO,
        "op_type": "get_question"
    }
    response = request_with_retry(requests.get, url, params=params, headers=headers)
    if response is None:
        return None
    if response.status_code == 200:
        return response.json()
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None


def finishTask(game_id):
    """
    完成任务
    :param game_id:
    :return:
    """
    url = f"{BASE_TASK_URL}/finish_task?user_id={USER_ID}"
    data = {
        "scene_info": SCENE_INFO,
        "auth_login": "1",
        "game_id": game_id
    }
    response = request_with_retry(requests.post, url, data=data, headers=headers)
    if response is None:
        return None
    if response.status_code == 200:
        return response.json()
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None


if __name__ == "__main__":
    args = parse_args()
    migrate_answer_cache_file()
    if args.build_bank:
        build_bank(
            rounds=args.rounds,
            round_delay=args.round_delay,
            submit_final=args.submit_final,
            workers=args.workers,
        )
    else:
        main()
