# Voice Clone Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提高声音克隆质量（智能裁剪+音量归一化），减少合成延迟（base64缓存），改善试听体验（自定义文本）。

**Architecture:** 在 `xiaomi_tts.py` 中新增 `_preprocess_audio()` 做音频预处理（含 MiMo-v2.5 智能裁剪），修改 `_load_voice_sample()` 加 mtime 缓存。前端试听文本改为可编辑输入框。

**Tech Stack:** Python, numpy, soundfile, ffmpeg, OpenAI SDK (MiMo-v2.5 audio understanding)

---

### Task 1: 服务器安装 ffmpeg + 验证 soundfile MP3 支持

**Files:**
- Modify: `deploy.py:50-52`

- [ ] **Step 1: 在 deploy.py 中添加 ffmpeg 安装步骤**

在 `[2/4] Install deps...` 之前插入 ffmpeg 安装：

```python
    # 1.5 安装系统依赖
    print("\n[1.5/4] Install system deps...")
    run(ssh, "apt-get install -y ffmpeg 2>/dev/null || yum install -y ffmpeg 2>/dev/null || echo 'ffmpeg install skipped'")
```

- [ ] **Step 2: 提交并部署验证 ffmpeg**

```bash
git add deploy.py
git commit -m "chore: deploy时安装ffmpeg用于MP3解码"
git push
python deploy.py
```

- [ ] **Step 3: 验证服务器 ffmpeg 可用**

```bash
curl -s --max-time 5 http://47.243.104.165:5000/api/skill
# 应返回正常 JSON，说明服务启动正常
```

---

### Task 2: 实现音频预处理方法 `_preprocess_audio()`

**Files:**
- Modify: `xiaomi_tts.py:1-9` (imports)
- Modify: `xiaomi_tts.py:106-127` (clone section)

- [ ] **Step 1: 添加 imports**

在 `xiaomi_tts.py` 顶部添加：

```python
import tempfile
```

- [ ] **Step 2: 实现 `_preprocess_audio()` 方法**

在 `XiaomiTTS` 类中，`_load_voice_sample()` 方法之前添加：

```python
    def _preprocess_audio(self, voice_path: str) -> str:
        """预处理参考音频：时长校验 + 音量归一化 + 格式统一

        Returns:
            处理后的临时 WAV 文件路径
        """
        import soundfile as sf

        data, sr = sf.read(voice_path)
        duration = len(data) / sr

        # 时长校验
        if duration < 3:
            print(f"[clone] 参考音频仅 {duration:.1f}s，建议 10-30s 以获得最佳效果")
        elif duration > 60:
            print(f"[clone] 参考音频 {duration:.1f}s 过长，截取前 60s")
            data = data[:int(60 * sr)]
        elif duration > 30:
            print(f"[clone] 参考音频 {duration:.1f}s，建议 10-30s 效果更佳")

        # 多声道转单声道
        if data.ndim > 1:
            data = data.mean(axis=1)

        # 音量归一化到 -1dB
        peak = abs(data).max()
        if peak > 0:
            data = data * (10 ** (-1 / 20)) / peak

        # 转为 16kHz 单声道 WAV
        if sr != 16000:
            from scipy.signal import resample
            num_samples = int(len(data) * 16000 / sr)
            data = resample(data, num_samples)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, data, 16000)
        return tmp.name
```

- [ ] **Step 3: 验证代码无语法错误**

```bash
cd e:/github/voice && python -c "from xiaomi_tts import XiaomiTTS; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add xiaomi_tts.py
git commit -m "feat: 添加音频预处理方法(归一化+格式统一)"
```

---

### Task 3: 实现 MiMo-v2.5 智能裁剪

**Files:**
- Modify: `xiaomi_tts.py` (`_preprocess_audio` 方法)

- [ ] **Step 1: 在 `_preprocess_audio()` 中添加智能裁剪逻辑**

在 `# 时长校验` 的 `elif duration > 60:` 分支中，将直接截取改为智能裁剪。替换整个时长校验块：

```python
        # 时长校验 + 智能裁剪
        if duration < 3:
            print(f"[clone] 参考音频仅 {duration:.1f}s，建议 10-30s 以获得最佳效果")
        elif duration > 30:
            trim_result = self._smart_trim(data, sr, duration)
            if trim_result is not None:
                data = trim_result
                print(f"[clone] 智能裁剪完成: {duration:.1f}s -> {len(data)/sr:.1f}s")
            else:
                # fallback: 取中间 25 秒
                mid = len(data) // 2
                half = int(12.5 * sr)
                data = data[max(0, mid - half):mid + half]
                print(f"[clone] 智能裁剪失败，取中间 25s")
```

- [ ] **Step 2: 实现 `_smart_trim()` 方法**

在 `_preprocess_audio()` 方法之后添加：

```python
    def _smart_trim(self, data, sr, duration):
        """用 MiMo-v2.5 分析音频，找出最佳片段并裁剪"""
        import soundfile as sf

        # 导出为临时 WAV 供分析
        tmp_in = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp_in.name, data, sr)
        tmp_in.close()

        try:
            # base64 编码
            with open(tmp_in.name, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            client = OpenAI(
                api_key=config.MIMO_API_KEY,
                base_url=config.MIMO_BASE_URL,
            )
            completion = client.chat.completions.create(
                model="mimo-v2.5",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": f"data:audio/wav;base64,{b64}"}
                        },
                        {
                            "type": "text",
                            "text": (
                                "请分析这段语音，找出音质最好、最清晰、情绪最稳定的连续片段。\n"
                                "要求：片段时长 15-30 秒，避开开头和结尾的杂音/停顿/背景噪音。\n"
                                "只输出时间戳，格式：start-end（如 15.2-42.8），不要输出其他内容。"
                            )
                        }
                    ]
                }],
                max_tokens=50,
            )
            text = completion.choices[0].message.content.strip()
            # 解析时间戳 "15.2-42.8"
            import re
            match = re.search(r'(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', text)
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                if 0 <= start < end <= duration and (end - start) >= 10:
                    return data[int(start * sr):int(end * sr)]
            return None
        except Exception as e:
            print(f"[clone] 智能裁剪分析失败: {e}")
            return None
        finally:
            os.remove(tmp_in.name)
```

- [ ] **Step 3: 验证代码无语法错误**

```bash
cd e:/github/voice && python -c "from xiaomi_tts import XiaomiTTS; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add xiaomi_tts.py
git commit -m "feat: MiMo-v2.5智能裁剪，自动找出最佳音频片段"
```

---

### Task 4: 实现 base64 缓存

**Files:**
- Modify: `xiaomi_tts.py:15-21` (`__init__`)
- Modify: `xiaomi_tts.py:108-126` (`_load_voice_sample`)

- [ ] **Step 1: 在 `__init__` 中添加缓存 dict**

在 `self.voice = config.TTS_VOICE` 之后添加：

```python
        self._voice_cache: dict = {}  # {voice_path: (mtime, base64_str)}
```

- [ ] **Step 2: 重写 `_load_voice_sample()` 支持缓存**

替换整个 `_load_voice_sample()` 方法：

```python
    def _load_voice_sample(self, voice_path: str) -> str:
        """加载音频样本并转为 data:audio/mpeg;base64,... 格式（带缓存）"""
        if not os.path.exists(voice_path):
            raise FileNotFoundError(f"音频文件不存在: {voice_path}")

        ext = os.path.splitext(voice_path)[1].lower()
        mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
        mime = mime_map.get(ext)
        if not mime:
            raise ValueError(f"不支持的音频格式: {ext}，仅支持 mp3 和 wav")

        # 检查缓存
        mtime = os.path.getmtime(voice_path)
        cache_key = voice_path
        if cache_key in self._voice_cache:
            cached_mtime, cached_b64 = self._voice_cache[cache_key]
            if cached_mtime == mtime:
                return f"data:{mime};base64,{cached_b64}"

        # 预处理
        processed_path = None
        try:
            processed_path = self._preprocess_audio(voice_path)
            read_path = processed_path
            mime = "audio/wav"  # 预处理后统一为 WAV
        except Exception as e:
            print(f"[clone] 预处理失败，使用原始文件: {e}")
            read_path = voice_path

        with open(read_path, "rb") as f:
            audio_bytes = f.read()

        b64 = base64.b64encode(audio_bytes).decode("utf-8")
        if len(b64) > 10 * 1024 * 1024:
            raise ValueError("音频样本base64编码后超过10MB限制")

        # 写入缓存
        self._voice_cache[cache_key] = (mtime, b64)

        # 清理预处理临时文件
        if processed_path and processed_path != voice_path:
            try:
                os.remove(processed_path)
            except OSError:
                pass

        return f"data:{mime};base64,{b64}"
```

- [ ] **Step 3: 验证代码无语法错误**

```bash
cd e:/github/voice && python -c "from xiaomi_tts import XiaomiTTS; t = XiaomiTTS(); print('cache:', hasattr(t, '_voice_cache'))"
```

Expected: `cache: True`

- [ ] **Step 4: 提交**

```bash
git add xiaomi_tts.py
git commit -m "feat: base64缓存+mtime失效，避免重复编码"
```

---

### Task 5: 前端试听文本可编辑

**Files:**
- Modify: `templates/voices.html:99-117` (clone card HTML)
- Modify: `templates/voices.html:228` (JS preview text)

- [ ] **Step 1: 添加试听文本输入框**

在声音克隆 card 中，`音色名称` field 之前插入：

```html
        <div class="field">
          <label>试听文本</label>
          <input type="text" id="cloneText" placeholder="输入要试听的文本" value="你好，这是声音克隆的试听效果，听起来怎么样？">
        </div>
```

- [ ] **Step 2: JS 使用自定义文本**

替换 `$('#btnPreviewClone')` 事件处理中的固定文本：

将第 228 行：
```javascript
  const text = '你好，这是声音克隆的试听效果，听起来怎么样？';
```

改为：
```javascript
  const text = $('#cloneText').value.trim() || '你好，这是声音克隆的试听效果，听起来怎么样？';
```

- [ ] **Step 3: 提交**

```bash
git add templates/voices.html
git commit -m "feat: 克隆试听文本可自定义编辑"
```

---

### Task 6: 部署并验证

**Files:**
- None (deploy only)

- [ ] **Step 1: 推送所有代码**

```bash
git push
```

- [ ] **Step 2: 部署到服务器**

```bash
python deploy.py
```

- [ ] **Step 3: 验证服务正常启动**

```bash
curl -s --max-time 5 http://47.243.104.165:5000/api/skill | python -m json.tool
```

Expected: 正常 JSON 返回，`available_sections` 非空

- [ ] **Step 4: 测试克隆合成**

打开 http://47.243.104.165:5000/voices ，上传一个音频文件，修改试听文本，点击"试听克隆效果"，验证：
1. 合成成功返回音频
2. 服务器日志显示预处理信息（`[clone]` 开头的日志）
3. 第二次试听同一文件速度更快（缓存命中）
