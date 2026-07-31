# ai/llm.py
"""LangChain ChatOpenAI 工厂函数，为各 AI 模块提供预配置的 LLM 实例。

DeepSeek API 与 OpenAI 兼容，但有一个关键差异：
ChatOpenAI._get_request_payload() 会把 max_tokens 重命名为 max_completion_tokens
（OpenAI 2024年9月起的参数名），但 DeepSeek 只认 max_tokens。
因此子类化 ChatOpenAI 覆盖该行为。
"""
import os

from langchain_openai import ChatOpenAI

from utills.logging_conf import get_logger

logger = get_logger(__name__)

# ---------- 配置 ----------
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

if not API_KEY:
    raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，无法初始化 LangChain LLM")


class DeepSeekChatOpenAI(ChatOpenAI):
    """ChatOpenAI 的 DeepSeek 适配子类。

    唯一覆盖点：_get_request_payload() 中不做 max_tokens → max_completion_tokens 的重命名，
    因为 DeepSeek API 使用的是旧参数名 max_tokens。
    """

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        # 还原 max_completion_tokens → max_tokens（DeepSeek 不认前者）
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        return payload


def get_empathy_llm() -> DeepSeekChatOpenAI:
    """共情 AI 专用，温度 0.55（需要一定发散度）"""
    return DeepSeekChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_BASE,
        temperature=0.55,
        max_tokens=2000,
    )


def get_productivity_llm() -> DeepSeekChatOpenAI:
    """工作 AI 专用，温度 0.2（需要精确结构化输出）"""
    return DeepSeekChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_BASE,
        temperature=0.2,
        max_tokens=2000,
    )


def get_shadow_llm() -> DeepSeekChatOpenAI:
    """影子 AI（上下文压缩 / 每日摘要），低温度确保精确总结"""
    return DeepSeekChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_BASE,
        temperature=0.2,
        max_tokens=1000,
    )
