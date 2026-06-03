import requests
import json

def sign_in():
    url = 'https://kohcamp.qq.com/operation/action/newsignin'
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148;GameHelper;smobagamehelper,iphoneX',
        'Content-Type': 'application/json',
        'token': '2d7lUKDmpp_f2kQhbmdmIjhECR2St7hYs37HDRk1AUgXl_hnNFdx38aEG_wanDr41c6kUSbQwvOIrG95dTMqgq-altqMNkGf',
        'userId': '532640694'
    }
    data = {
        'cSystem': 'ios',
        'h5Get': 1,
        'gameId': '20001',
        'roleId': '2671621274'
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # 检查 HTTP 状态码
        result = response.json()

        # 处理响应
        if result.get('returnCode') == 0:
            print("签到成功！")
            data = result.get('data', {})
            print(f"签到日期: {data.get('signDate')}")
            print(f"累计签到天数: {data.get('totalSignDays')}")
            print(f"连续签到天数: {data.get('seqSignDays')}")
            print("奖励列表:")
            for gift in data.get('giftList', []):
                print(f"- {gift['giftText']} x{gift['giftNum']} ({gift['giftDesc']})")
        elif result.get('returnCode') == -105203:
            print("签到失败：请勿重复签到")
        else:
            print(f"签到失败：{result.get('returnMsg', '未知错误')} (Code: {result.get('returnCode')})")

    except requests.exceptions.RequestException as e:
        print(f"请求失败：{e}")
    except json.JSONDecodeError:
        print("响应格式错误：无法解析 JSON")
    except Exception as e:
        print(f"发生未知错误：{e}")

if __name__ == "__main__":
    sign_in()