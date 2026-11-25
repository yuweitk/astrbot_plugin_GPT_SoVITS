from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from astrbot.api import logger

from .config import ConfigNode, PluginConfig


class ScopeEntry(ConfigNode):
    """单条会话范围配置。"""

    umo: str
    note: str
    enabled: bool

    def __init__(self, data: dict[str, Any]):
        super().__init__(data)
        self.umo = (getattr(self, "umo", "") or "").strip()
        self.note = getattr(self, "note", "") or ""
        self.enabled = bool(getattr(self, "enabled", False))

    @property
    def patterns(self) -> list[str]:
        """把 UMO 拆成若干可匹配的模式。

        - 完整 UMO，如 `aiocqhttp:GroupMessage:123456`
        - 群号本身，如 `123456`（方便只记得群号时填写）
        """
        umo = self.umo
        if not umo:
            return []
        pats = [umo]
        if ":" in umo:
            tail = umo.rsplit(":", 1)[-1].strip()
            if tail and tail != umo:
                pats.append(tail)
        return pats


class ScopeManager:
    """按 UMO 判断当前会话是否允许使用 TTS。"""

    MODE_BLACKLIST = "blacklist"
    MODE_WHITELIST = "whitelist"
    MODE_ALL = "all"

    def __init__(self, config: PluginConfig):
        self.cfg = config.scope
        self._sig: tuple | None = None
        self.entries: list[ScopeEntry] = []
        self._reload()

    @staticmethod
    def _signature(raw: Any) -> tuple:
        """用于判断名单是否发生变化，避免每条消息都重复解析与告警。"""
        try:
            return tuple(
                sorted(
                    (
                        str(item.get("umo", "")),
                        bool(item.get("enabled")),
                        str(item.get("note", "")),
                    )
                    for item in raw
                    if isinstance(item, dict)
                )
            )
        except Exception:
            return ("<invalid>",)

    def _reload(self, force: bool = False) -> None:
        raw = self.cfg.sessions or []
        sig = self._signature(raw)
        if not force and sig == self._sig:
            return
        self._sig = sig

        self.entries = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                entry = ScopeEntry(dict(item))
            except Exception:
                logger.warning(f"[GSV] 跳过无法解析的范围条目: {item}")
                continue
            if not entry.umo:
                logger.warning("[GSV] 跳过 UMO 为空的范围条目")
                continue
            self.entries.append(entry)

    @property
    def mode(self) -> str:
        mode = (self.cfg.mode or self.MODE_BLACKLIST).strip().lower()
        if mode not in {self.MODE_BLACKLIST, self.MODE_WHITELIST, self.MODE_ALL}:
            logger.warning(f"[GSV] 未知的范围模式 {mode!r}，按黑名单处理")
            mode = self.MODE_BLACKLIST
        return mode

    def _match(self, umo: str) -> ScopeEntry | None:
        """返回命中的条目；多条命中时取列表中最后一条（便于覆盖）。"""
        if not umo:
            return None
        tail = umo.rsplit(":", 1)[-1].strip() if ":" in umo else umo
        hit: ScopeEntry | None = None
        for entry in self.entries:
            for pat in entry.patterns:
                if fnmatch(umo, pat) or fnmatch(tail, pat):
                    hit = entry
                    break
        return hit

    def is_allowed(self, umo: str) -> bool:
        """当前会话是否允许使用 TTS。"""
        # 面板修改配置后无需重载插件，这里每次读取最新名单
        self._reload()
        mode = self.mode
        if mode == self.MODE_ALL:
            return True

        hit = self._match(umo)

        if mode == self.MODE_WHITELIST:
            # 白名单：只放行显式启用的会话
            return bool(hit and hit.enabled)

        # 黑名单：列表内 enabled=False 表示禁用；其余（含未列出的会话）放行
        if hit is None:
            return True
        return bool(hit.enabled)

    def describe(self, umo: str) -> str:
        """给用户看的判定说明。"""
        self._reload()
        mode = self.mode
        hit = self._match(umo)
        mode_text = {
            self.MODE_ALL: "全部会话启用",
            self.MODE_WHITELIST: "白名单模式",
            self.MODE_BLACKLIST: "黑名单模式",
        }.get(mode, mode)

        if hit is None:
            state = "未在列表中"
        else:
            state = f"命中条目 {hit.umo}" + (f"（{hit.note}）" if hit.note else "")

        enabled_text = "放行" if self.is_allowed(umo) else "拦截"
        return f"当前模式：{mode_text}｜{state}｜结果：{enabled_text}"
