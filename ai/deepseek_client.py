# ai/deepseek_client.py
import os
import json
import re
import httpx

# ---------- 配置 ----------
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# 重试设置
MAX_JSON_FIX_RETRIES = 2  # 当返回不是合法 JSON 时，最多重试次数
TEMPERATURE = 0.3  # 降低至 0.3，确保 JSON 输出稳定
MAX_TOKENS = 2000  # 默认最大 token

if not API_KEY:
    raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，无法初始化 DeepSeek 客户端")


# ---------- 工具函数 ----------
def extract_json_from_text(text: str) -> dict:
    """
    尝试从文本中提取 JSON 对象。
    支持纯 JSON 文本、被 ```json ... ``` 包裹、以及字符串内嵌的 JSON。
    """
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试匹配 ```json 代码块
    json_code_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    match = re.search(json_code_pattern, text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试用正则找第一个 { 和最后一个 } 之间的内容
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        possible_json = text[brace_start:brace_end + 1]
        try:
            return json.loads(possible_json)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 AI 回复中提取 JSON: {text[:200]}...")


async def _call_deepseek_api(
        messages: list[dict[str, str]],
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
        timeout: float = 60.0
) -> httpx.Response:
    """单次 API 调用，返回原始 httpx.Response"""
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
        resp = await client.post(url, headers=headers, json=payload)
        return resp


# ---------- 核心函数（旧版，保留兼容性，新流程不再使用） ----------
async def deepseek_chat(
        prompt: str,
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
        retry_on_json_fail: bool = True
) -> dict:
    """
    发送提示词给 DeepSeek，期望返回一个 JSON 对象。
    旧版接口，不推荐，仅保留兼容。
    """
    messages = [{"role": "user", "content": prompt}]
    return await _deepseek_chat_inner(messages, temperature, max_tokens, retry_on_json_fail)


# ---------- 新版核心函数：直接接收 messages 列表 ----------
async def deepseek_chat_messages(
        messages: list[dict[str, str]],
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
        retry_on_json_fail: bool = True
) -> dict:
    """
    使用标准的 messages 列表调用 DeepSeek，期望返回一个 JSON 对象。
    参数:
        messages: 完整对话历史，第一条应是 system 消息
        temperature: 生成温度
        max_tokens: 最大 token
        retry_on_json_fail: JSON 解析失败时是否重试
    返回:
        解析后的 JSON 字典
    """
    return await _deepseek_chat_inner(messages, temperature, max_tokens, retry_on_json_fail)


async def _deepseek_chat_inner(
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        retry_on_json_fail: bool
) -> dict:
    """内部实现：支持重试的 JSON 解析与修正"""
    # 为防止影响原始列表，做浅拷贝
    msgs = messages.copy()

    for attempt in range(1 + MAX_JSON_FIX_RETRIES):
        try:
            resp = await _call_deepseek_api(msgs, temperature, max_tokens)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"DeepSeek API 返回错误状态码 {e.response.status_code}: {e.response.text[:200]}") from e

        data = resp.json()
        choices = data.get("choices")
        if not choices:
            raise RuntimeError("DeepSeek API 返回内容缺少 choices 字段")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("DeepSeek API 返回的消息内容为空")

        try:
            result = extract_json_from_text(content)
            return result
        except ValueError as e:
            if attempt < MAX_JSON_FIX_RETRIES and retry_on_json_fail:
                fix_prompt = (
                    f"你的上一次回复没有包含合法的 JSON 对象。错误信息: {e}\n"
                    f"请严格按照我要求的 JSON 格式输出，不要添加任何无关文字。\n"
                    f"原始回复内容: {content[:500]}"
                )
                # 追加错误修正历史
                msgs.append({"role": "assistant", "content": content})
                msgs.append({"role": "user", "content": fix_prompt})
                continue
            else:
                raise RuntimeError(f"AI 回复内容不是合法 JSON，且重试已耗尽。最后内容: {content[:200]}") from e

    raise RuntimeError("DeepSeek 调用因未知原因失败")