"""小米MiMo TTS语音合成模块 - 使用Token Plan API"""

import os
import base64
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

    def _load_voice_sample(self, voice_path: str) -> str:
        """加载音频样本并转为 data:audio/mpeg;base64,... 格式"""
        if not os.path.exists(voice_path):
            raise FileNotFoundError(f"音频文件不存在: {voice_path}")

        ext = os.path.splitext(voice_path)[1].lower()
        mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
        mime = mime_map.get(ext)
        if not mime:
            raise ValueError(f"不支持的音频格式: {ext}，仅支持 mp3 和 wav")

        with open(voice_path, "rb") as f:
            audio_bytes = f.read()

        b64 = base64.b64encode(audio_bytes).decode("utf-8")
        if len(b64) > 10 * 1024 * 1024:
            raise ValueError("音频样本base64编码后超过10MB限制")

        return f"data:{mime};base64,{b64}"

    def clone_synthesize(self, text: str, voice_path: str, style: str = None) -> Optional[bytes]:
        """
        声音克隆合成: 使用音频样本克隆音色并合成语音

        Args:
            text: 要合成的文本
            voice_path: 参考音频文件路径 (mp3/wav)
            style: 风格控制描述 (可选)

        Returns:
            WAV音频数据字节
        """
        voice_data = self._load_voice_sample(voice_path)

        messages = []
        if style:
            messages.append({"role": "user", "content": style})
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


if __name__ == "__main__":
    tts = XiaomiTTS()
    text = "你好，我是小米MiMo语音助手，很高兴为你服务！"
    print(f"正在合成: {text}")
    if tts.synthesize_to_file(text, "output.wav"):
        print("语音已保存到 output.wav")
    else:
        print("合成失败，请检查API密钥配置")
