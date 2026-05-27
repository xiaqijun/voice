"""小米MiMo语音聊天机器人 - 主程序"""

import os
import sys
import wave
import tempfile
from xiaomi_tts import XiaomiTTS
from chat_bot import ChatBot, SimpleChatBot
import config


def play_wav(data: bytes):
    """播放WAV音频"""
    try:
        import pyaudio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(data)
            tmp_path = f.name

        wf = wave.open(tmp_path, "rb")
        p = pyaudio.PyAudio()
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )
        chunk = 1024
        audio_data = wf.readframes(chunk)
        while audio_data:
            stream.write(audio_data)
            audio_data = wf.readframes(chunk)
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()
        os.remove(tmp_path)
    except ImportError:
        print("[提示] 未安装pyaudio，无法播放语音。请运行: pip install pyaudio")
    except Exception as e:
        print(f"播放失败: {e}")


def record_audio(duration: float = 5.0) -> bytes:
    """录制麦克风音频"""
    try:
        import pyaudio
        import numpy as np
    except ImportError:
        print("[提示] 未安装pyaudio，无法录音。请运行: pip install pyaudio")
        return b""

    chunk = 1024
    fmt = pyaudio.paInt16
    channels = 1
    rate = 16000

    p = pyaudio.PyAudio()
    stream = p.open(format=fmt, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)

    print(f"正在录音 ({duration}秒)...")
    frames = []
    for _ in range(0, int(rate / chunk * duration)):
        data = stream.read(chunk, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    return b"".join(frames)


def recognize_speech(audio_data: bytes) -> str:
    """语音识别 (使用MiMo Chat API的音频理解能力，或回退到文本输入)"""
    # MiMo支持音频理解，但当前ASR需要额外处理
    # 这里提供文本输入作为回退
    return input("请输入你的问题 (语音识别待接入): ")


class VoiceChatBot:
    """语音聊天机器人"""

    def __init__(self, use_api: bool = False, clone_voice_path: str = None):
        self.use_api = use_api
        self.clone_voice_path = clone_voice_path
        if use_api:
            self.tts = XiaomiTTS()
            self.chat_bot = ChatBot()
        else:
            self.tts = None
            self.chat_bot = SimpleChatBot()

    def speak(self, text: str):
        """语音播报"""
        if self.tts:
            print("[正在合成语音...]")
            if self.clone_voice_path:
                audio = self.tts.clone_synthesize(text, self.clone_voice_path)
            else:
                audio = self.tts.synthesize(text)
            if audio:
                play_wav(audio)
            else:
                print(f"(语音合成失败，文本输出) 助手: {text}")
        else:
            print(f"助手: {text}")

    def run_text_mode(self):
        """文本对话模式"""
        print("=" * 50)
        print("  小米MiMo语音聊天机器人 - 文本模式")
        print("  输入 'quit' 退出 | 'clear' 清除历史")
        print("=" * 50)

        while True:
            try:
                user_input = input("\n你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "退出"):
                print("再见！")
                break
            if user_input.lower() == "clear":
                self.chat_bot.clear_history()
                print("[对话历史已清除]")
                continue

            reply = self.chat_bot.chat(user_input)
            if reply:
                self.speak(reply)

    def run_voice_mode(self):
        """语音对话模式"""
        print("=" * 50)
        print("  小米MiMo语音聊天机器人 - 语音模式")
        print("  按 Ctrl+C 退出")
        print("=" * 50)

        while True:
            try:
                audio_data = record_audio(duration=5.0)
                text = recognize_speech(audio_data)
                if not text:
                    continue
                print(f"你: {text}")

                if text.lower() in ("quit", "退出", "再见"):
                    self.speak("再见！祝你有美好的一天！")
                    break

                reply = self.chat_bot.chat(text)
                if reply:
                    print(f"助手: {reply}")
                    self.speak(reply)

            except KeyboardInterrupt:
                print("\n\n再见！")
                self.speak("再见！")
                break

    def run(self, mode: str = "text"):
        if mode == "voice":
            self.run_voice_mode()
        else:
            self.run_text_mode()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="小米MiMo语音聊天机器人")
    parser.add_argument("mode", nargs="?", default="text", choices=["text", "voice"],
                        help="运行模式: text (文本) 或 voice (语音)")
    parser.add_argument("--api", action="store_true", help="使用MiMo API (需要配置API密钥)")
    parser.add_argument("--voice", default=None, help="TTS音色 (冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean)")
    parser.add_argument("--clone", default=None, help="声音克隆: 传入参考音频文件路径 (mp3/wav)")
    args = parser.parse_args()

    if args.api and config.MIMO_API_KEY == "your_api_key_here":
        print("请先在 config.py 中配置 MIMO_API_KEY")
        print("获取密钥: https://platform.xiaomimimo.com/#/console/api-keys")
        return

    bot = VoiceChatBot(use_api=args.api, clone_voice_path=args.clone)

    if args.voice and bot.tts:
        bot.tts.set_voice(args.voice)
        print(f"[音色已设置为: {args.voice}]")

    bot.run(args.mode)


if __name__ == "__main__":
    main()
