import time

import requests
from itertools import combinations
import urllib.parse
import json
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ANSWER_CACHE_PATH = Path(__file__).with_name("answer_cache.json")
CACHE_LOCK = threading.Lock()
REQUEST_TIMEOUT = 15
MAX_REQUEST_RETRIES = 3
RETRY_DELAY_SECONDS = 1.5
TRY_ANSWER_DELAY_SECONDS = 0.3

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.56(0x1800383b) NetType/WIFI Language/zh_CN miniProgram/wx39542b01b40b6909",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Mode": "cors",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Sec-Fetch-Site": "same-origin",
    "Referer": "https://wx.gamesafe.qq.com/static/proxy/intervention/index.html?gameId=2577&sceneInfo=6611B2FE4FA0F8DEF788CD8A958CDFEA99ACC5EDE0588093469D79EFD4DD3FBF1155277FCC65A28E5EE3219DD9A7C6D2F2EFAEDB10F9F50627ABE9E2A701F3CE153D29449483512991B7732A40DB3722867B6297E6BF0F22497D2518FB01A890936ABCAD78836B24E65AA5B0B585B9C65B0DBCF99615EC6B7FC87F5C9E43AA31&taskId=9&op_type=get_question",
    "Sec-Fetch-Dest": "empty",
    "Cookie": "access_token=104_QcrpBCo6x5PGyKyR2qHxVZd-h07CkAemD0KeQgPHR4VDbZE9kIIg8Hi7pSg4fFZ-WS5mCMPpPyp3gOhJPoGyt4tvqJdXNv3iR_dmtyfsXig; active_uin=%E5%BD%93%E5%89%8D%E5%BE%AE%E4%BF%A1%E5%8F%B7; applet_code=99B61FC7AADACF1101B8D4BEF477A56E4346B06AA313E874CA4B586491E634A9B1CA6CB983D1C5933CB30F40C19DE5D2E7CF65406B5F2D1A6BEF73839A30D68A; openid=ob1lCuAzW0raz9y2wYlsgZIONFoU"
}

scene_info = "E29F655B9B0A7FAED50DEFA6D7B3CFDA712A1C46A27D92E014B33A42AFA29AFB559F80D24AAAB29B58044911665E24D6F765049E0F66A9F7F555AE13918C0A0294CEF2B33CFD84E47C32CF6463E762BBBC91B571C0B2F06F44264ABED45DC60C61FCB8A24984AC18859BB0683B908FA536564B69BD943D1CCFE6908C607D3E1B"


# cookies = {
#     "active_uin": urllib.parse.quote("实际微信号"),  # 替换为实际微信号
#     "access_token": "92_s5w-hpHR4g2DBt8UrGiOU1XK2oucRspm-oIloFVuB0PgFmiHfr_eM28RLjzX5REBRVDz9E-Oz6ZH41LlDm_YrBWHha23sddL9sRsbBFtzJ4",
#     "applet_code": "72AB15F0D9644BFFAB9508189225BC656365BB540E07A1DE45FFE17983093147AC88C699C40B5A74A3D790EBCD116377C69D03C885FE3581A0D8F780F34D93DB",
#     "openid": "ob1lCuAzW0raz9y2wYlsgZIONFoU"
# }
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
    url = "https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/get_seed_info"
    params = {
        "user_id": "ob1lCuAzW0raz9y2wYlsgZIONFoU",
        "game_id": "2577",
        "scene_info": scene_info,
        "task_id": "9",
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
    options = extract_options(page_cfg)
    answer_texts = []
    for index_text in str(answer).split("|"):
        try:
            option_index = int(index_text) - 1
        except ValueError:
            continue
        if 0 <= option_index < len(options):
            answer_texts.append(options[option_index])
    return answer_texts


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

    entry = {
        "answer": str(answer),
        "answer_texts": get_answer_texts(page_cfg, answer),
        "question_title": normalize_text(page_cfg.get("question_title", "")),
        "question_type": page_cfg.get("question_type", 1),
        "options": extract_options(page_cfg),
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
    res = verify_task(origin_seed, 9, last_answer)
    print(res.json() if res is not None else "verify task 9 request failed")
    res = verify_task(origin_seed, 10, last_answer)
    print(res.json() if res is not None else "verify task 10 request failed")
    res = finishTask(2577)
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

# F04E3AEC17E8E132D2DCD2F8FC558C53ACE2B401169AF2609FC9D6E58AFD07B710665408F82E37DAE035B150CDA1964850E363C7F8A827DBC419D7C2E976AC2F17F533BD4B1845070B9F7FCA49000F60A471A1C9B36DE00EF9F5ABC7C76DAFF0365015DB5C06FD153DC16755D258BA8A97B49112AB259F7E0EEA5F7F10FE92393F3C44EC69256C65DB7764C850D5FA20BF3257F355754E17E89F190F45D95D8A17E4768B4AD98EFB71A3721D3D5E2196DE757D73349DBCF64FD4564170CCA8C8D054767D16BA97EE4E94D7C477B2B15F86CF850B83645E025F31B47F8A15D8C1DD0B47CB5884AB3A7A21FBFF43932F660B4B08CEC3C64693E00C6D79B207474F541F5377413043A3F2A49CE4FB8431A20385210F76A2C8B340BF834470A9E3836FBBF1D42A4362FD10128CB68C0E46422E7420F55E1AE2B973825B43C2D7DF01DEC82079620C2D175F87EA7C9D063FB2031BC491F0884077330D9F859227721E8CD5B6B40211FACC09A94F220D4A4C9E0366C31E40F12E362C4D99B1C14FEC2AE3E67322BA0AF78CB8642DF741C05249734F43E55792866A29AC807C19DF19E7A1051706886C20F9B9E8AD29A359B9D9FF4204419AB5FF501A5CC48DFC7A0180F9DE301E632A0A28F7E55494EE183890C39F0DA95DB52FD8C9C5A5710A770D3C55D1FC7FBF0ED03687E82697A9449C4521ED82B5CEC7AE1181249F7B77FAC241117CF3DA366525802C09FBFB57E5B98DD197353F4232588CDF6DA8FDA953A17FD2176A43801786AA0AB67EED142CE1A8086B45B3A37E1428E4C5BEEEC72BA382B1B4239562F4B61DCECE8957910BB2A7602051C509C63630B5AE0FA5549BA0A4BF67B77A434C3BFBAD5D2C17D82128BFC59B08CE66C2FD28B6514067B242FC93AEB6680FB07B0D4C9B63FD0F84A83AB91E5E43A5E64FF77A05D8A004583D76518677007A90A379BF2038BAFFE59E597A9D7758F62A1441819D2685C231D22F42286F4A6A999452168F43526CC491047A
# F04E3AEC17E8E132D2DCD2F8FC558C53ACE2B401169AF2609FC9D6E58AFD07B710665408F82E37DAE035B150CDA1964850E363C7F8A827DBC419D7C2E976AC2F17F533BD4B1845070B9F7FCA49000F60A471A1C9B36DE00EF9F5ABC7C76DAFF0365015DB5C06FD153DC16755D258BA8A97B49112AB259F7E0EEA5F7F10FE92393F3C44EC69256C65DB7764C850D5FA20BF3257F355754E17E89F190F45D95D8A17E4768B4AD98EFB71A3721D3D5E2196DE757D73349DBCF64FD4564170CCA8C8D054767D16BA97EE4E94D7C477B2B15F86CF850B83645E025F31B47F8A15D8C1DD0B47CB5884AB3A7A21FBFF43932F660B4B08CEC3C64693E00C6D79B207474F541F5377413043A3F2A49CE4FB8431A20385210F76A2C8B340BF834470A9E3836FBBF1D42A4362FD10128CB68C0E46422E7420F55E1AE2B973825B43C2D7DF01DEC82079620C2D175F87EA7C9D063FB2031BC491F0884077330D9F859227721E8CD5B6B40211FACC09A94F220D4A4C9E0366C31E40F12E362C4D99B1C14FEC2AE3E67322BA0AF78CB8642DF741C05249734F43E55792866A29AC807C19DF19E7A1051706886C20F9B9E8AD29A359B9D9FF4204419AB5FF501A5CC48DFC7A0180F9DE301E632A0A28F7E55494EE183890C39F0DA95DB52FD8C9C5A5710A770D3C55D1FC7FBF0ED03687E82697A9449C4521ED82B5CEC7AE1181249F7B77FAC241117CF3DA366525802C09FBFB57E5B98DD197353F4232588CDF6DA8FDA953A17FD2176A43801786AA0AB67EED142CE1A8086B45B3A37E1428E4C5BEEEC72BA382B1B4239562F4B61DCECE8957910BB2A7602051C509C63630B5AE0FA5549BA0A4BF67B77A434C3BFBAD5D2C17D82128BFC59B08CE66C2FD28B6514067B242FC93AEB6680FB07B0D4C9B63FD0F84A83AB91E5E43A5E64FF77A05D8A004583D76511FB2A1F447A15AB27B85E46D808978685AA3BF32A786693B4DAB63A793B232FC094392EE972108F2599C8685C14208B4
# https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/get_seed_info?user_id=ob1lCuAzW0raz9y2wYlsgZIONFoU&game_id=2577&scene_info=145624F756415076C11E9770E155B4E7DBBAB53A60EF3037BF9A112C9B20219B0B0DAE5099DD554EC1CD016D7723B9F4CC97544986C1DED1D7BF171727B39C9302DB0759F570461636F57EFAFB8201C22AB37A45905457E1B590E48B4D0D6EAAC182F4290D59976525A0555549E009B9A3A0BAD39B2D98DF6B3DD57466B27F25&task_id=9&seed=FABA2B00AE8698C7E081F987329BB5427240BEAA70EEFBF632E70411B79EAA308FFF4141FAADF2BEBF674943DE92FB574E29E4098346E9D0321CAAB96D54FB76567704818D1E7242BB64382F4735A278A66E080784DAF7EB53F0B5C41B0FDB21AC0FB974B2DB190FBC45F8C5E22035BD26297CD8327D0459BA4E8FEFD6F2DE59476E86043C17C5F063F541693157894A21E3A4EB045CC079440492846324F3ADA502625BF8BB0E80B649DF53713AE7A3D34E1B4DFE227C43A0589D0CCD21ABACB78AF72240539A20CED0DCB98E73A4CE762939CE2EE5A7A6896BD40BF2D78AF81C1EE886A1D90F6C41156718E51E4EFFB9FA18113BA839F7E473DC83694E31E5FA94917FD7E8E6CACE3F7D0E91B30D425AAE3EBBD9EAAF1394BA40DA6659EA78FF25F001CC67947B497B12F4E54FF3589F51DCE858622C3172A98079220C33B3440E02DF2FC95686AE2209D6272FEE8D9F85E40F9013864E6B2F51C3438C0B92BD8EC66642DD8564CEB9467EB54BEDA83EDD2166B042B4C463384FA4701DBC2BFE22E1D579B271CF3964F8A69C85CD4B70F8D1D369FBDC46D81CFB2238A655675F5F2BAA038764561A327A3B5FEE647D097632C8AC78E8D3CF65E1601BF34881AB05850F2A652842B778EB6798A306C6A736E82352873E5FA39D76388315790B4D37B297FAF89388CC3B597A8F43E0D0
def verify_task(seed, task_id=9, answer="1"):
    """
    提交答案
    :param seed:
    :param task_id: 9 验证答题任务， 10 验证同意协议任务
    :param answer: 1 正确答案， 0 错误答案
    :return:
    """
    url = "https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/verify_task"
    data = {
        "user_id": "ob1lCuAzW0raz9y2wYlsgZIONFoU",
        "game_id": "2577",
        "scene_info": scene_info,
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
    # https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/get_task_info?user_id=ob1lCuAzW0raz9y2wYlsgZIONFoU&game_id=2577&task_id=9&scene_info=145624F756415076C11E9770E155B4E7DBBAB53A60EF3037BF9A112C9B20219B0B0DAE5099DD554EC1CD016D7723B9F4CC97544986C1DED1D7BF171727B39C9302DB0759F570461636F57EFAFB8201C22AB37A45905457E1B590E48B4D0D6EAAC182F4290D59976525A0555549E009B9A3A0BAD39B2D98DF6B3DD57466B27F25&op_type=get_question
    url = "https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/get_task_info"
    params = {
        "user_id": "ob1lCuAzW0raz9y2wYlsgZIONFoU",
        "game_id": "2577",
        "task_id": "9",
        "scene_info": scene_info,
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
    # https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/finish_task?user_id=ob1lCuAzW0raz9y2wYlsgZIONFoU POST
    url = "https://wx.gamesafe.qq.com/cgi/proxy/user_guide/limit_tasks/finish_task?user_id=ob1lCuAzW0raz9y2wYlsgZIONFoU"
    data = {
        "scene_info": scene_info,
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
    if args.build_bank:
        build_bank(
            rounds=args.rounds,
            round_delay=args.round_delay,
            submit_final=args.submit_final,
            workers=args.workers,
        )
    else:
        main()
