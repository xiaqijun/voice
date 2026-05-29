# 声音克隆优化设计

## 背景

当前声音克隆流程存在以下问题：
- 上传的参考音频没有做任何预处理（音量归一化、格式统一）
- 每次合成都重新读取文件并 base64 编码，无缓存
- 试听文本写死在前端，无法自定义
- 没有音频时长校验，过长或过短的音频会影响克隆质量

## 目标

1. 提高克隆音质：音量归一化 + 格式统一
2. 减少合成延迟：base64 缓存，避免重复编码
3. 改善试听体验：自定义试听文本 + 时长提示

## 设计

### 模块 1：智能音频预处理

**文件**: `xiaomi_tts.py`

新增 `_preprocess_audio(voice_path: str) -> str` 方法，在 `_load_voice_sample()` 调用前执行：

1. **读取音频**：通过 soundfile 读取（MP3 需要 ffmpeg backend）
2. **时长校验**：
   - < 3 秒：打印警告 `[clone] 参考音频仅 {n}s，建议 10-30s`
   - > 60 秒：触发智能裁剪流程
   - 3-30 秒：直接进入归一化步骤（最佳范围）
   - 30-60 秒：可选裁剪，打印提示
3. **智能裁剪**（仅音频 > 30 秒时触发）：
   - 将音频发送给 MiMo-v2.5（音频理解模型），提示词：
     ```
     请分析这段语音音频，找出音质最好、最清晰、情绪最稳定的连续片段。
     输出格式：start_seconds-end_seconds（如 15.2-42.8）
     要求：片段时长 15-30 秒，避开开头和结尾的杂音/停顿/背景噪音。
     ```
   - 模型返回时间戳区间，系统按此裁剪
   - 模型调用失败时 fallback 到取中间 25 秒
4. **音量归一化**：peak normalize 到 -1dB（避免音量太小导致克隆效果差）
5. **格式统一**：转为 16kHz 单声道 WAV，保存到临时文件返回路径

**依赖**：服务器安装 ffmpeg（`apt install ffmpeg`），soundfile 通过 ffmpeg backend 读 MP3。
**API 开销**：智能裁剪仅在音频 > 30 秒时触发一次，增加约 2-3 秒延迟，后续合成不再调用。

### 模块 2：base64 缓存

**文件**: `xiaomi_tts.py`

在 `XiaomiTTS` 类中新增缓存：

```python
self._voice_cache: Dict[str, tuple] = {}  # {voice_path: (mtime, base64_str)}
```

`_load_voice_sample()` 改为：
1. 检查缓存中是否存在且 mtime 未变
2. 命中缓存直接返回
3. 未命中则读取 → 预处理 → 缓存 base64 → 返回

### 模块 3：试听体验

**前端** (`voices.html`):
- 试听文本输入框：将固定的试听文字改为 `<input>` 可编辑，默认值保持原样
- 合成后显示音频时长

**后端** (`app.py`):
- `/api/tts/clone` 接口无需改动，已经支持自定义 `text` 参数
- 返回音频时长信息（在 header 或 response 中）

## 改动范围

| 文件 | 改动 |
|------|------|
| `xiaomi_tts.py` | 新增 `_preprocess_audio()`（含智能裁剪）、修改 `_load_voice_sample()` 加缓存 |
| `templates/voices.html` | 试听文本改为可编辑输入框 |
| `deploy.py` | 服务器安装 ffmpeg |

## 部署步骤

1. 服务器 `apt install -y ffmpeg`
2. 提交代码
3. 运行 deploy.py

## 不做的事

- 不做降噪（需要额外依赖，收益不确定）
- 不做前端波形编辑（方案 B 再做）
- 不做 A/B 对比功能（当前阶段不需要）
