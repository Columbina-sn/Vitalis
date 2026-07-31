# ai/llm.py
"""LangChain ChatOpenAI 工厂函数，为各 AI 模块提供预配置的 LLM 实例。"""
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


def get_empathy_llm() -> ChatOpenAI:
    """共情 AI 专用，温度 0.55（需要一定发散度）"""
    return ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_BASE,
        temperature=0.55,
        max_tokens=2000,
    )


def get_productivity_llm() -> ChatOpenAI:
    """工作 AI 专用，温度 0.2（需要精确结构化输出）"""
    return ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_BASE,
        temperature=0.2,
        max_tokens=2000,
    )


def get_shadow_llm() -> ChatOpenAI:
    """影子 AI（上下文压缩 / 每日摘要），低温度确保精确总结"""
    return ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_BASE,
        temperature=0.2,
        max_tokens=1000,
    )
