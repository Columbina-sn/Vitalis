# utills/ip_utils.py
from fastapi import Request
import os


def get_client_ip(request: Request) -> str:
    """
    从请求中获取真实客户端 IP 地址。
    支持直接连接、X-Forwarded-For、X-Real-IP。
    可通过环境变量 TRUST_PROXY_HEADERS 控制是否信任代理头。
    """
    trust_headers = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"

    if trust_headers:
        # 1. 尝试从 X-Forwarded-For 获取
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # 取第一个 IP（最左边），去掉空格
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip

        # 2. 降级到 X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    # 3. 回退到直接连接 IP（无代理或未信任代理头）
    return request.client.host