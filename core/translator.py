import re

from astrbot.api import logger
from astrbot.core.platform.astr_message_event import AstrMessageEvent

from .config import PluginConfig

# 匹配假名（平假名 + 片假名）
_KANA = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
# 匹配中日韩统一表意文字
_CJK = re.compile(r"[\u4E00-\u9FFF]")


def detect_lang(text: str) -> str:
    """粗判文本语言：'ja' / 'zh' / 'other'"""
    if not text or not text.strip():
        return "other"
    if _KANA.search(text):
        return "ja"
    if _CJK.search(text):
        return "zh"
    return "other"


class Translator:
    """日中互译，供 TTS 合成与附带文本使用。"""

    SYSTEM_PROMPT = (
        "你是一名专业的日中翻译。请把用户给出的文本翻译成{target}。\n"
        "要求：\n"
        "1. 只输出译文本身，不要输出解释、原文、引号或任何多余内容。\n"
        "2. 保持原意与语气（亲昵、吐槽、生气等情绪要保留）。\n"
        "3. 使用日常口语表达，不要用书面语或敬语堆砌。\n"
        "4. 不要添加原文没有的内容。"
    )

    def __init__(self, config: PluginConfig):
        self.cfg = config

    async def _translate(
        self, event: AstrMessageEvent, text: str, target: str
    ) -> str | None:
        try:
            provider = self.cfg.get_translate_provider(event.unified_msg_origin)
            resp = await provider.text_chat(
                system_prompt=self.SYSTEM_PROMPT.format(target=target),
                prompt=text,
            )
            result = (resp.completion_text or "").strip()
            result = result.strip("\"“”「」『』' \n\t")
            if not result:
                logger.warning("[GSV] 翻译结果为空，回退原文")
                return None
            return result
        except Exception as e:
            logger.warning(f"[GSV] 翻译失败，回退原文: {e}")
            return None

    async def to_japanese(self, event: AstrMessageEvent, text: str) -> str | None:
        return await self._translate(event, text, "自然的口语化日语")

    async def to_chinese(self, event: AstrMessageEvent, text: str) -> str | None:
        return await self._translate(event, text, "简体中文")

    async def prepare(
        self, event: AstrMessageEvent, text: str
    ) -> tuple[str, str | None]:
        """返回 (用于合成的文本, 用于附带显示的中文文本)。

        - 中文原文 → 合成用日语，附带中文原文
        - 日语原文 → 合成用日语原文，附带中文译文
        - 其他（纯英文等）→ 原样使用，不附带
        """
        lang = detect_lang(text)

        if lang == "zh":
            ja = await self.to_japanese(event, text)
            return (ja or text, text)

        if lang == "ja":
            zh = await self.to_chinese(event, text)
            return (text, zh)

        return (text, None)

