"""对话机器人模块 - 使用小米MiMo Chat API"""

from typing import List, Dict, Optional
from openai import OpenAI
import config


class ChatBot:
    """小米MiMo对话机器人 (OpenAI兼容格式)"""

    SYSTEM_PROMPT = (
        "你是MiMo，是小米公司研发的AI智能助手。"
        "请用简洁明了的口语化方式回答，适合语音播报。"
        "回答尽量控制在2-3句话以内。"
    )

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        self.model = config.CHAT_MODEL
        self.history: List[Dict] = []

    def chat(self, user_message: str) -> Optional[str]:
        """与MiMo对话"""
        self.history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(self.history[-10:])  # 保留最近10轮

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            reply = completion.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            print(f"对话请求失败: {e}")
            return None

    def clear_history(self):
        """清除对话历史"""
        self.history = []


class SimpleChatBot:
    """简单对话机器人 (无需API)"""

    RESPONSES = {
        "你好": "你好！很高兴见到你！",
        "嗨": "嗨！有什么可以帮你的吗？",
        "再见": "再见！祝你有美好的一天！",
        "谢谢": "不客气！很高兴能帮到你！",
        "你是谁": "我是小米MiMo语音助手，可以帮你回答问题和聊天。",
    }

    def chat(self, user_message: str) -> str:
        msg = user_message.strip()
        for key, reply in self.RESPONSES.items():
            if key in msg:
                return reply
        return f"你说的是：{msg}。我是一个简单的语音助手，还在学习中。"

    def clear_history(self):
        pass
