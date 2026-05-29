"""对话机器人模块 - 使用小米MiMo Chat API"""

import os
import re
from typing import List, Dict, Optional
from openai import OpenAI
import config

# Skill 文件路径
SKILL_PATH = os.path.join(os.path.dirname(__file__), ".claude", "skills", "tts-style-generator.md")


# ChatBot 需要读取的 skill 章节
REQUIRED_SECTIONS = [
    "快速参考：标签体系",
    "声线变体速查",
    "情绪-语速-共鸣映射",
    "常见错误",
    "表达原则",
]


def load_skill_sections(skill_path: str = None, sections: list = None) -> str:
    """从 skill .md 文件中按章节标题提取指定内容"""
    path = skill_path or SKILL_PATH
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # 去掉 YAML frontmatter
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

    target_sections = sections or REQUIRED_SECTIONS
    result_parts = []
    current_section = None
    current_lines = []

    for line in content.split("\n"):
        # 检测二级标题
        if line.startswith("## "):
            # 保存上一个匹配的章节
            if current_section and current_section in target_sections:
                result_parts.append("\n".join(current_lines))
            current_section = line[3:].strip()
            current_lines = [line]
        elif current_section:
            current_lines.append(line)

    # 保存最后一个章节
    if current_section and current_section in target_sections:
        result_parts.append("\n".join(current_lines))

    return "\n\n".join(result_parts)


def fix_stacked_tags(text: str) -> str:
    """修正标签堆叠在开头的问题

    检测模式: (tag1)(tag2)(tag3)句子1。句子2。句子3。
    修正为: (tag1)句子1。(tag2)句子2。(tag3)句子3。
    """
    # 匹配开头连续的标签
    pattern = r'^(\([^)]+\)\s*){2,}'
    if not re.match(pattern, text):
        return text

    # 提取所有标签
    tags = re.findall(r'\(([^)]+)\)', text)
    # 去掉标签部分，提取剩余文本
    remaining = re.sub(r'^(\([^)]+\)\s*)+', '', text).strip()

    if not remaining:
        return text

    # 按中文标点分句（包括~）
    sentences = re.split(r'(?<=[。！？~\n])', remaining)
    sentences = [s.strip() for s in sentences if s.strip()]

    # 如果最后一个没标点结尾，也要算一句
    if remaining and not re.search(r'[。！？~\n]$', remaining):
        # 检查最后一段是否已经在sentences里
        last_part = remaining
        for s in sentences:
            last_part = last_part.replace(s, '', 1)
        last_part = last_part.strip()
        if last_part:
            sentences.append(last_part)

    if not sentences:
        return text

    # 标签多于句子时，合并多余标签到最后一个句子
    # 标签少于句子时，复用最后一个标签
    parts = []
    for i, sentence in enumerate(sentences):
        if i < len(tags):
            tag = tags[i]
        else:
            tag = tags[-1]  # 复用最后一个标签
        parts.append(f"({tag}){sentence}")

    return "".join(parts)


def build_system_prompt(skill_content: str = None) -> str:
    """从 skill 内容构建系统提示词"""
    intro = """你是MiMo，小米公司研发的AI智能助手。你要像真人一样说话，而不是像机器播报。

## 最重要的输出规则

你必须严格按照以下格式输出，每个标签只控制紧跟它的那句话：

(标签)这句话的内容。(标签)下一句话的内容。(标签)再下句话的内容。

绝对不要这样写（错误）:
(标签)(标签)(标签)所有话堆在一起。

记住：写完一个标签和它对应的句子后，再写下一个标签。一个标签管一句话。

## 让声音像真人的技巧

- 加呼吸声: 句间插入(深呼吸)、(叹气)、(吸气)
- 加语气词: 嗯、呃、那个、就是说、你知道吗、哎呀
- 加笑声: (轻笑)、(苦笑)、(忍不住笑)
- 句子长短交替，不要每句一样长
- 说话会自我纠正: 我是说...、不对不对...
- 用省略号制造犹豫感: 嗯...让我想想...
- 口语化不完美，可以用半句

规则:
- 标签可组合: (温柔 低语)、(兴奋 语速加快)
- 声线切换: (御姐)、(少年)、(萝莉)、(叔音)
- 回答简洁口语化，2-3句话"""

    examples = """
## 回复示例（注意：这些示例展示了如何像真人一样说话）

用户: 我考试过了！
回复: (惊喜)啊？真的吗！(开心 轻笑)哈哈太好了！(温柔)我就知道你行的，你那么努力。

用户: 我心情不好
回复: (温柔)嗯...(停顿)(关心)怎么了？(轻声)跟我说说呗。

用户: 讲个笑话
回复: (活泼)好呀！(清嗓子)咳咳，听好了啊。(平静)就是有个人...(停顿)(忍不住笑)哈哈不行我先笑一会...(开心)他说他家的猫会算数！结果...(停顿)(大笑)结果就只会数到一！

用户: 哄我睡觉
回复: (温柔 低语)嗯...好...(轻柔)那闭上眼睛...(停顿)(叹气)今天辛苦了吧...(缓慢)想象你躺在软软的云朵上...风轻轻吹过...(停顿)(气声)什么都不要想...

用户: 用御姐音说话
回复: (御姐 磁性)嗯？(停顿)(慵懒)你想要我这样说话...(轻笑)可以啊。(沉稳)不过...(低沉)你确定受得了吗？

用户: 模仿一个热血少年
回复: (少年 热血)哈！(兴奋)你问我是谁？(坚定)我可是要成为...(停顿)(得意)最强的人！(语速加快)不管遇到什么困难我都不会放弃的！

用户: 假装很累
回复: (疲惫 嘶)...嗯？(有气无力)主人...(叹气)到了叫我...(停顿)(小声嘀咕)真的好困...眼睛都睁不开了...(深深叹气)先...眯一会...

用户: 用东北话
回复: (东北话)哎呀妈呀！(惊讶)你这也太厉害了吧！(开心)我跟你说啊...(得意)整得真不错！老好了！

用户: 我失恋了
回复: (心疼)唉...(停顿)(温柔)我知道现在说什么你都听不进去...(叹气)但是呢...(温暖)哭出来吧，别憋着。(轻声)我在这陪你。

用户: 太好了我升职了
回复: (震惊)啥！(兴奋)真的假的！(开心 轻笑)哈哈太牛了你！(热情)不行不行必须庆祝一下！(语速加快)今晚你请客啊！

用户: 帮我骂人
回复: (无奈)哎呀...(停顿)(苦笑)这个我真的不会骂人...(温柔)不过你要是不开心的话...(关心)跟我说说怎么了呗，出什么事了？"""

    if skill_content:
        return intro + "\n\n## TTS风格控制知识库\n\n" + skill_content + "\n" + examples
    else:
        fallback = """
## 标签速查

整体风格: 开心, 悲伤, 生气, 温柔, 活泼, 严肃, 慵懒, 磁性, 低沉, 沙哑, 甜美, 热情, 冷淡
行内精细: 停顿, 叹气, 深呼吸, 微笑, 大笑, 抽泣, 颤抖, 气声, 低声, 提高嗓门
声线: 御姐, 少年, 萝莉, 叔音, 青年
方言: 东北话, 四川话, 粤语"""
        return intro + fallback + examples


class ChatBot:
    """小米MiMo对话机器人 (OpenAI兼容格式)"""

    def __init__(self, api_key: str = None, skill_path: str = None):
        self.client = OpenAI(
            api_key=api_key or config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        self.model = config.CHAT_MODEL
        self.history: List[Dict] = []
        self.skill_path = skill_path
        self._system_prompt = None
        self.load_skill()

    def load_skill(self):
        """从 skill 文件加载系统提示词"""
        content = load_skill_sections(self.skill_path)
        self._system_prompt = build_system_prompt(content)
        source = "skill文件" if content else "内置默认"
        print(f"[ChatBot] 系统提示词已加载 (来源: {source}, {len(self._system_prompt)}字)")

    def reload_skill(self):
        """按需重新加载 skill"""
        self.load_skill()
        return len(self._system_prompt)

    def chat(self, user_message: str, voice_context: str = None) -> Optional[str]:
        """与MiMo对话"""
        self.history.append({"role": "user", "content": user_message})

        system = self._system_prompt
        if voice_context:
            system += f"\n\n【用户语音特征】{voice_context}\n请根据用户的语气和情绪，选择相匹配的情绪标签和回复风格。"

        messages = [{"role": "system", "content": system}]
        messages.extend(self.history[-10:])

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            reply = completion.choices[0].message.content
            # 修正标签堆叠问题
            reply = fix_stacked_tags(reply)
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
