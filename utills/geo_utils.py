# utills/geo_utils.py
from typing import Optional
import requests


def get_city_from_ip(ip: str) -> Optional[str]:
    """
    使用太平洋电脑网在线IP接口解析地理位置，返回 "中国–江西–南昌" 之类的格式。
    如果请求失败或IP无效，返回 None。
    """
    if ip in ("127.0.0.1", "::1"):
        return None

    try:
        url = f"https://whois.pconline.com.cn/ipJson.jsp?ip={ip}&json=true"
        # 注意：该接口返回的是 GBK 编码的 JSON，设置正确的 encoding
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        # 手动设置响应编码为 GBK
        resp.encoding = 'gbk'
        data = resp.json()

        pro = data.get("pro", "")
        # city = data.get("city", "")
        addr = data.get("addr", "")

        # 优先用省份+城市拼接
        if pro:
            return f"中国–{pro}"
        # 如果addr存在且有效，直接使用
        if addr and addr.strip():
            return addr
        return None
    except Exception as e:
        print(f"在线IP解析失败: {e}")
        return None