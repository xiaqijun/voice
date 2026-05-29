"""小米MiMo TTS语音合成模块 - 使用Token Plan API"""

import os
import base64
import tempfile
from typing import Optional
from openai import OpenAI
import numpy as np
import soundfile as sf
import config


class XiaomiTTS:
    """小米MiMo TTS客户端 (OpenAI兼容格式)"""

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        self.model = config.TTS_MODEL
        self.voice = config.TTS_VOICE
        self._voice_cache: dict = {}  # {voice_path: (mtime, base64_str)}

    def synthesize(self, text: str, style: str = None) -> Optional[bytes]:
        """
        将文本转换为语音

        Args:
            text: 要合成的文本 (放在assistant消息中)
            style: 语音风格描述 (放在user消息中，可选)

        Returns:
            WAV音频数据字节，失败返回None
        """
        messages = []
        if style:
            messages.append({"role": "user", "content": style})
        messages.append({"role": "assistant", "content": text})

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                audio={"format": "wav", "voice": self.voice},
            )
            message = completion.choices[0].message
            if hasattr(message, "audio") and message.audio:
                return base64.b64decode(message.audio.data)
            return None
        except Exception as e:
            print(f"TTS合成失败: {e}")
            return None

    def synthesize_to_file(self, text: str, output_path: str, style: str = None) -> bool:
        """合成语音并保存到文件"""
        audio_data = self.synthesize(text, style)
        if audio_data:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            return True
        return False

    def synthesize_stream(self, text: str, style: str = None) -> Optional[np.ndarray]:
        """
        流式合成语音 (返回numpy数组，可直接播放)

        Args:
            text: 要合成的文本
            style: 语音风格描述

        Returns:
            24kHz float32 numpy数组
        """
        messages = []
        if style:
            messages.append({"role": "user", "content": style})
        messages.append({"role": "assistant", "content": text})

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                audio={"format": "pcm16", "voice": self.voice},
                stream=True,
            )

            collected = np.array([], dtype=np.float32)
            for chunk in completion:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                audio = getattr(delta, "audio", None)
                if audio and isinstance(audio, dict):
                    pcm_bytes = base64.b64decode(audio["data"])
                    pcm_float = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    collected = np.concatenate((collected, pcm_float))

            return collected if len(collected) > 0 else None
        except Exception as e:
            print(f"TTS流式合成失败: {e}")
            return None

    def set_voice(self, voice: str):
        """设置音色 (mimo_default, 冰糖, 茉莉, 苏打, 白桦, Mia, Chloe, Milo, Dean)"""
        self.voice = voice

    # ---- 声音克隆 ----

    def _preprocess_audio(self, voice_path: str) -> str:
        """预处理参考音频：时长校验 + 音量归一化 + 格式统一

        Returns:
            处理后的临时 WAV 文件路径
        """
        data, sr = sf.read(voice_path)
        duration = len(data) / sr

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

    def clone_synthesize(self, text: str, voice_path: str, style: str = None) -> Optional[bytes]:
        """
        声音克隆合成: 使用音频样本克隆音色并合成语音

        Args:
            text: 要合成的文本
            voice_path: 参考音频文件路径 (mp3/wav)
            style: 风格控制描述 (可选，为空时使用默认自然风格)

        Returns:
            WAV音频数据字节
        """
        voice_data = self._load_voice_sample(voice_path)

        messages = []
        # 克隆模式下始终提供风格提示，让声音更自然
        if style:
            messages.append({"role": "user", "content": style})
        elif hasattr(config, 'CLONE_DEFAULT_STYLE'):
            messages.append({"role": "user", "content": config.CLONE_DEFAULT_STYLE})
        messages.append({"role": "assistant", "content": text})

        try:
            completion = self.client.chat.completions.create(
                model=config.TTS_CLONE_MODEL,
                messages=messages,
                audio={"format": "wav", "voice": voice_data},
            )
            message = completion.choices[0].message
            if hasattr(message, "audio") and message.audio:
                return base64.b64decode(message.audio.data)
            return None
        except Exception as e:
            print(f"声音克隆合成失败: {e}")
            return None

    def clone_synthesize_to_file(self, text: str, voice_path: str, output_path: str, style: str = None) -> bool:
        """声音克隆合成并保存到文件"""
        audio_data = self.clone_synthesize(text, voice_path, style)
        if audio_data:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            return True
        return False

    # ---- 声音设计 (文字描述生成声音) ----

    def design_synthesize(self, text: str, voice_description: str) -> Optional[bytes]:
        """
        声音设计合成: 通过文字描述自定义声音，无需音频样本

        Args:
            text: 要合成的文本
            voice_description: 声音描述 (如 "年轻女性，温柔甜美的声音，语速稍慢")

        Returns:
            WAV音频数据字节
        """
        messages = [
            {"role": "user", "content": voice_description},
            {"role": "assistant", "content": text},
        ]
        try:
            completion = self.client.chat.completions.create(
                model=config.TTS_DESIGN_MODEL,
                messages=messages,
                audio={"format": "wav", "optimize_text_preview": True},
            )
            message = completion.choices[0].message
            if hasattr(message, "audio") and message.audio:
                return base64.b64decode(message.audio.data)
            return None
        except Exception as e:
            print(f"声音设计合成失败: {e}")
            return None

    def design_synthesize_to_file(self, text: str, voice_description: str, output_path: str) -> bool:
        """声音设计合成并保存到文件"""
        audio_data = self.design_synthesize(text, voice_description)
        if audio_data:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            return True
        return False


if __name__ == "__main__":
    tts = XiaomiTTS()
    text = "你好，我是小米MiMo语音助手，很高兴为你服务！"
    print(f"正在合成: {text}")
    if tts.synthesize_to_file(text, "output.wav"):
        print("语音已保存到 output.wav")
    else:
        print("合成失败，请检查API密钥配置")
