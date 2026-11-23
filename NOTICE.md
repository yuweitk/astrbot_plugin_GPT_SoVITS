# 来源与修改说明 / Attribution & Modifications

本项目是第三方插件的**二次修改版本**，基于原作者的公开作品修改而来。

## 原项目

| 项目 | 信息 |
| --- | --- |
| 名称 | `astrbot_plugin_GPT_SoVITS` |
| 原作者 | **Zhalslar** |
| 原始版本 | **v3.1.1** |
| 原仓库 | https://github.com/Zhalslar/astrbot_plugin_GPT_SoVITS |
| 原许可证 | **AGPL-3.0**（GNU Affero General Public License v3.0） |

原作者版权归 Zhalslar 所有。本仓库完整保留原始 `LICENSE` 文件，未作任何改动。

## 本修改版

| 项目 | 信息 |
| --- | --- |
| 修改者 | yuweiEX（GitHub: [yuweitk](https://github.com/yuweitk)） |
| 维护仓库 | https://github.com/yuweitk/astrbot_plugin_GPT_SoVITS |
| 镜像仓库 | https://gitee.com/yuweiEX/astrbot_plugin_GPT_SoVITS |
| 版本号 | `v3.1.1-yuweiEX.2` |

## 修改内容

仅涉及以下五处，**未改动**原作者的音频合成、情绪参数、缓存等核心逻辑。

### 0. 空文本拦截（`core/service.py`）

原版 `inference()` 仅在 `text` 非空时覆盖 `params["text"]`，文本为空时会沿用 `default_params.text` 的模板值，把模板内容合成后发出。现已改为空文本直接返回失败结果并记录 warning。

### 1. 日语原文补中文译文（`core/translator.py`）

原版 `Translator.prepare()` 只处理「中文 → 翻成日语」这一条路径，日语原文直接送去合成，语音发出后没有任何附带文本。

修改后按语言分三条分支：

| 原文语言 | 用于合成的文本 | 语音发出后补发 |
| --- | --- | --- |
| 中文 | 翻译成日语 | 中文原文 |
| 日语 | 日语原文 | **中文译文（新增）** |
| 其他（纯英文等） | 原样 | 不补发 |

配套新增 `to_chinese()` 方法，与原有 `to_japanese()` 对称。语言判定仍沿用原有的字符正则（先看假名，再看汉字），未做改动。

### 2. 翻译失败时回退原文（`core/translator.py`）

翻译调用异常或返回空时，捕获并记 `warning`，回退为原文继续合成，不中断语音发送流程。原版在翻译失败时链路会直接异常。

### 3. 连接超时 5 秒（`core/client.py`）

```python
timeout=ClientTimeout(total=self.cfg.timeout, sock_connect=5)
```

为 `sock_connect` 显式设置 5 秒。原版仅设置总超时，本地 GPT-SoVITS 服务未启动时，连接阶段会一直挂起到总超时才失败。

### 4. 配置项文案调整（`_conf_schema.json`）

`translate` 段的 `hint` 文案同步更新，说明「中文补原文、日语补译文」的新行为。字段结构未变。

## 许可证义务说明

原项目以 **AGPL-3.0** 授权。本修改版同样以 AGPL-3.0 发布，并履行以下义务：

- 保留原始版权声明与 `LICENSE` 文件；
- 明确标注修改内容与修改者（即本文件）；
- 以相同许可证（AGPL-3.0）分发本修改版；
- 提供完整源代码（本仓库即为完整源码）。

若你需要**商用**或**闭源分发**，请先联系原作者 Zhalslar 获取授权。AGPL-3.0 的网络使用条款同样适用：若你将本插件作为网络服务对外提供，需向使用者提供本源码。

## 反馈

- 本修改版的问题请提给本仓库。
- 原版逻辑的问题请提给原作者仓库。
