# ai/deepseek_client.py
import os
import json
import re
import httpx

# ---------- 配置 ----------
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

MAX_JSON_FIX_RETRIES = 2      # JSON 解析失败时最多自动修正次数
TEMPERATURE_DEFAULT = 0.2     # 工作/总结 AI 用
TEMPERATURE_EMPATHY = 0.5     # 情感 AI 用（需要一定发散度）
MAX_TOKENS = 2000

if not API_KEY:
    raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，无法初始化 DeepSeek 客户端")


# ---------- 工具 ----------
def extract_json_from_text(text: str) -> dict:
    """从模型回复中提取 JSON（支持多种包裹格式）"""
    text = text.strip()
    # 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 匹配 ```json ... ```
    m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 从第一个 { 到最后一个 }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从回复中提取 JSON，片段: {text[:200]}")


async def _call_api(messages: list[dict[str, str]],
                    temperature: float,
                    max_tokens: int = MAX_TOKENS,
                    timeout: float = 60.0) -> httpx.Response:
    """底层 API 调用"""
    url = f"{API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, headers=headers, json=payload)


# ---------- 新版核心：标准 messages 列表，JSON 解析 ----------
async def deepseek_chat_messages(
        messages: list[dict[str, str]],
        temperature: float = TEMPERATURE_DEFAULT,
        max_tokens: int = MAX_TOKENS,
        retry_on_json_fail: bool = True
) -> dict:
    """工作 / 总结 AI 专用，返回解析后的 JSON 对象"""
    msgs = messages.copy()
    for attempt in range(1 + MAX_JSON_FIX_RETRIES):
        resp = await _call_api(msgs, temperature, max_tokens)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices")
        if not choices:
            raise RuntimeError("API 返回缺少 choices")
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("API 返回内容为空")

        try:
            return extract_json_from_text(content)
        except ValueError as e:
            if attempt < MAX_JSON_FIX_RETRIES and retry_on_json_fail:
                # 追加修正消息
                msgs.append({"role": "assistant", "content": content})
                msgs.append({"role": "user", "content":
                    f"上一次回复未能包含合法 JSON。错误信息: {e}\n"
                    f"请严格按照要求的 JSON 格式输出，不要添加任何无关文字。"
                    f"原始回复: {content[:500]}"})
                continue
            raise RuntimeError(
                f"AI 回复非合法 JSON 且重试已耗尽，最后内容: {content[:200]}"
            ) from e
    raise RuntimeError("调用因未知原因失败")


# ---------- 情感 AI 专用：纯文本回复 ----------
async def deepseek_chat_text(
        messages: list[dict[str, str]],
        temperature: float = TEMPERATURE_EMPATHY,
        max_tokens: int = MAX_TOKENS,
        timeout: float = 60.0
) -> str:
    resp = await _call_api(messages, temperature, max_tokens, timeout)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices")
    if not choices:
        raise RuntimeError("AI 返回缺少 choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("AI 返回内容为空")
    return content