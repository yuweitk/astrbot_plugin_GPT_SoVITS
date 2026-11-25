import base64
import random

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Plain, Record
from astrbot.core.platform import AstrMessageEvent

from .core.client import GSVApiClient, GSVRequestResult
from .core.config import PluginConfig
from .core.emotion import EmotionJudger
from .core.entry import EntryManager
from .core.local_data import LocalDataManager
from .core.scope import ScopeManager
from .core.service import GPTSoVITSService
from .core.translator import Translator

class GPTSoVITSPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config, context)
        self.local_data = LocalDataManager(self.cfg)
        self.entry_mgr = EntryManager(self.cfg)
        self.client = GSVApiClient(self.cfg)
        self.judger = EmotionJudger(self.cfg)
        self.translator = Translator(self.cfg)
        self.service = GPTSoVITSService(self.cfg, self.client, self.local_data)
        self.scope = ScopeManager(self.cfg)

    async def initialize(self):
        if self.cfg.enabled:
            await self.service.load_model()

    async def terminate(self):
        await self.client.close()

    @staticmethod
    def _to_record(res: GSVRequestResult) -> Record:
        if res.file_path:
            try:
                return Record.fromFileSystem(res.file_path)
            except Exception:
                logger.warning(f"无法读取文件：{res.file_path}, 已忽略")
                pass

        if not res.data:
            raise ValueError("无法获取结果数据")

        b64 = base64.urlsafe_b64encode(res.data).decode()
        return Record.fromBase64(b64)


    async def _get_emotion_params(
        self, event: AstrMessageEvent, text: str
    ) -> dict | None:
        entry = None

        if self.cfg.judge.enabled_llm:
            labels = self.entry_mgr.get_names()
            emotion = await self.judger.judge_emotion(event, text=text, labels=labels)
            if emotion:
                entry = self.entry_mgr.get_entry(emotion)

        if entry is None:
            entry = self.entry_mgr.match_entry(text)

        return entry.to_params() if entry else None

    @filter.on_decorating_result(priority=14)
    async def on_decorating_result(self, event: AstrMessageEvent):
        """消息入口"""
        if not self.cfg.enabled:
            return
        if not self.scope.is_allowed(event.unified_msg_origin):
            return
        cfg = self.cfg.auto

        result = event.get_result()
        if not result:
            return
        chain = result.chain
        if not chain:
            return
        if cfg.only_llm_result and not result.is_llm_result():
            return
        if random.random() > cfg.tts_prob:
            return

        # 收集所有Plain文本片段
        plain_texts = []
        for seg in chain:
            if isinstance(seg, Plain):
                plain_texts.append(seg.text)

        # 仅允许只含有Plain的消息链通过
        if len(plain_texts) != len(chain):
            return

        # 合并所有Plain文本
        combined_text = "\n".join(plain_texts)

        # 仅允许一定长度以下的文本通过
        if len(combined_text) > cfg.max_msg_len:
            return

        params = await self._get_emotion_params(event, combined_text)

        # 合成文本 / 附带显示文本
        if self.cfg.translate.enabled:
            tts_text, display_text = await self.translator.prepare(event, combined_text)
        else:
            tts_text, display_text = combined_text, None

        res = await self.service.inference(tts_text, extra_params=params)
        if not bool(res):
            return

        chain.clear()

        # 先发音频，再补中文原文
        chain.append(self._to_record(res))

        if (
            self.cfg.translate.enabled
            and self.cfg.translate.keep_text
            and display_text
        ):
            template = self.cfg.translate.text_template or "{text}"
            try:
                note = template.format(text=display_text)
            except (KeyError, IndexError):
                note = display_text
            chain.append(Plain(note))

    @filter.command("说", alias={"gsv", "GSV"})
    async def on_command(self, event: AstrMessageEvent):
        """说 <内容>, 直接调用GSV合成语音"""
        if not self.cfg.enabled:
            return
        if not self.scope.is_allowed(event.unified_msg_origin):
            reply = (self.cfg.scope.deny_reply or "").strip()
            if reply:
                yield event.plain_result(reply)
            return

        text = event.message_str.partition(" ")[2]

        if self.cfg.translate.enabled:
            tts_text, display_text = await self.translator.prepare(event, text)
        else:
            tts_text, display_text = text, None

        res = await self.service.inference(tts_text)

        if not bool(res):
            yield event.plain_result(res.error)
            return

        chain = [self._to_record(res)]
        if (
            self.cfg.translate.enabled
            and self.cfg.translate.keep_text
            and display_text
        ):
            template = self.cfg.translate.text_template or "{text}"
            try:
                note = template.format(text=display_text)
            except (KeyError, IndexError):
                note = display_text
            chain.append(Plain(note))
        yield event.chain_result(chain)

    @filter.command("语音状态", alias={"gsv状态", "gsvstatus"})
    async def on_status(self, event: AstrMessageEvent):
        """查看当前会话的 UMO 与语音开关状态"""
        umo = event.unified_msg_origin
        yield event.plain_result(
            f"当前会话 UMO：{umo}\n{self.scope.describe(umo)}"
        )

    @filter.command("重启GSV", alias={"重启gsv"})
    async def tts_control(self, event: AstrMessageEvent):
        """重启GPT_SoVITS"""
        if not self.cfg.enabled:
            return
        yield event.plain_result("重启TTS中...(报错信息请忽略，等待一会即可完成重启)")
        await self.service.restart()

    @filter.llm_tool()
    async def gsv_tts(self, event: AstrMessageEvent, message: str = ""):
        """
        用语音输出要讲的话
        Args:
            message(string): 要讲的话
        """
        try:
            if not self.scope.is_allowed(event.unified_msg_origin):
                return "当前会话已禁用语音功能"
            params = await self._get_emotion_params(event, message)

            if self.cfg.translate.enabled:
                tts_text, display_text = await self.translator.prepare(event, message)
            else:
                tts_text, display_text = message, None

            res = await self.service.inference(tts_text, extra_params=params)
            if not bool(res):
                return res.error

            chain = [self._to_record(res)]
            if (
                self.cfg.translate.enabled
                and self.cfg.translate.keep_text
                and display_text
            ):
                template = self.cfg.translate.text_template or "{text}"
                try:
                    note = template.format(text=display_text)
                except (KeyError, IndexError):
                    note = display_text
                chain.append(Plain(note))
            await event.send(event.chain_result(chain))
        except Exception as e:
            return str(e)
