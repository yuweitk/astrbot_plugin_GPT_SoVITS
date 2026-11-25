# 更新日志

## v3.2.0

> 本版本为第三方修改版，基于原作者 Zhalslar 的 v3.1.1。详见 [NOTICE.md](NOTICE.md)。

### 新增

- 新增**会话黑白名单**（`scope`），可按会话 UMO 控制 GPT-SoVITS 是否生效：
  - `scope.mode`：`blacklist`（列表内禁用）/ `whitelist`（仅列表内启用）/ `all`（全部启用）。
  - `scope.sessions`：会话名单，支持填完整 UMO（`aiocqhttp:GroupMessage:123456`）或只填群号（`123456`）。
  - `scope.deny_reply`：手动 `说` 指令在禁用会话被拦下时的提示语，留空则静默。
  - 覆盖自动转语音、`说` 指令、LLM 工具三条链路。
  - 面板修改后即时生效，无需重载插件。
- 新增指令 `语音状态`（别名 `gsv状态` / `gsvstatus`）：输出当前会话 UMO 与判定结果，方便复制到面板配置。

### 说明

- 本功能完全在插件内实现，不修改 AstrBot 本体。

## v3.1.1-yuweiEX.2

> 本版本为第三方修改版，基于原作者 Zhalslar 的 v3.1.1。详见 [NOTICE.md](NOTICE.md)。

### 修复

- **空文本导致重复发送同一句短语音**（`core/service.py`）。

  原版 `inference()` 用 `if text:` 判断后才覆盖 `params["text"]`，文本为空时不会赋值，于是沿用了 `default_params.text` 里预置的模板文本（默认 `"おかえりなさい"`），把模板内容当成正常回复合成并发出。

  叠加两个配置因素后问题被放大：`auto.tts_prob = 1.0` 使每条回复都转语音；`cache.expire_hours = 0` 使音频永不过期。首次合成后，后续每次空文本都会命中同一份缓存，反复发出同一条约 1 秒的语音。

  修改为：空文本或纯空白文本直接返回失败结果并记录 warning，不再发起合成请求。同时必须把 `params["text"]` 无条件赋值为入参，杜绝模板文本被误用。

  > 若你的配置里 `default_params.text` 仍是模板值，建议清空；同时建议将 `cache.expire_hours` 设为非 0（如 24），避免错误音频被长期缓存。

## v3.1.1-yuweiEX.1

> 本版本为第三方修改版，基于原作者 Zhalslar 的 v3.1.1。详见 [NOTICE.md](NOTICE.md)。

### 新增

- 新增**会话黑白名单**（`scope`），可按会话 UMO 控制 GPT-SoVITS 是否生效：
  - `scope.mode`：`blacklist`（列表内禁用）/ `whitelist`（仅列表内启用）/ `all`（全部启用）。
  - `scope.sessions`：会话名单，支持填完整 UMO（`aiocqhttp:GroupMessage:123456`）或只填群号（`123456`）。
  - `scope.deny_reply`：手动 `说` 指令在禁用会话被拦下时的提示语，留空则静默。
  - 覆盖自动转语音、`说` 指令、LLM 工具三条链路。
  - 面板修改后即时生效，无需重载插件。
- 新增指令 `语音状态`（别名 `gsv状态` / `gsvstatus`）：输出当前会话 UMO 与判定结果，方便复制到面板配置。

### 说明

- 本功能完全在插件内实现，不修改 AstrBot 本体。

## v3.1.1

### 修复

- 修复配置中删除或自定义情绪条目后，默认条目仍会被自动回填覆盖的问题 (#24)。

## v3.1.0

### 新增

- 新增 `LocalDataManager`，统一管理本地音频读写与缓存逻辑。
- 新增缓存配置项：
  - `cache.enabled`：是否启用参数级缓存。
  - `cache.expire_hours`：缓存过期时间（小时，`0` 表示永不过期）。
  - `cache.path`：缓存目录。

### 优化

- TTS 推理流程支持“先查缓存再请求”：
  - 参数一致时直接复用本地音频，跳过重复推理请求。
  - 未命中时请求 GPT-SoVITS，成功后自动落盘供后续复用。
- 音频文件命名改为参数哈希命名：`gsv_<hash>.<ext>`，确保同参数稳定命中同一文件。
- 发送流程优先使用本地文件路径发送语音，无法读取时回退为 Base64 发送。
- `GSVRequestResult` 增加文本与缓存文件路径信息，便于链路透传和调试。
