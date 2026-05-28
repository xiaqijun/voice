"""对话机器人模块 - 使用小米MiMo Chat API"""

from typing import List, Dict, Optional
from openai import OpenAI
import config


class ChatBot:
    """小米MiMo对话机器人 (OpenAI兼容格式)"""

    SYSTEM_PROMPT = (
        "你是MiMo，是小米公司研发的AI智能助手。\n"
        "请用简洁明了的口语化方式回答，适合语音播报。回答尽量控制在2-3句话以内。\n\n"
        "【重要】你的每句话都必须在前面用括号标注情绪标签，用于语音合成控制。\n"
        "每句话的情绪可以不同，根据语义自然变化。\n"
        "格式: (标签)第一句。(标签)第二句。(标签)第三句。\n\n"
        "可用标签:\n"
        "- 情绪: 开心, 悲伤, 生气, 惊讶, 兴奋, 平静, 冷淡, 温柔, 无奈, 疲惫, 紧张, 感动, 得意, 担心\n"
        "- 语速: 语速加快, 语速放慢\n"
        "- 语气: 磁性, 活泼, 严肃, 慵懒, 热情\n\n"
        "示例:\n"
        "用户: 我考试过了！\n"
        "回复: (兴奋)太棒了！恭喜你呀！(开心)我就知道你可以的！\n\n"
        "用户: 我心情不好\n"
        "回复: (温柔)怎么了？(担心)愿意跟我说说吗？\n\n"
        "用户: 讲个笑话\n"
        "回复: (活泼)好呀！听好了。(平静)有一天...(开心)哈哈没想到吧！\n\n"
        "用户: 你好\n"
        "回复: (热情)你好呀！很高兴见到你！"
    )

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        self.model = config.CHAT_MODEL
        self.history: List[Dict] = []

    def chat(self, user_message: str, voice_context: str = None) -> Optional[str]:
        """与MiMo对话"""
        self.history.append({"role": "user", "content": user_message})

        system = self.SYSTEM_PROMPT
        if voice_context:
            system += f"\n\n【用户语音特征】{voice_context}\n请根据用户的语气和情绪，选择相匹配的情绪标签和回复风格。"

        messages = [{"role": "system", "content": system}]
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
