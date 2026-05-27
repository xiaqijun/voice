# 小米MiMo语音聊天机器人

基于小米MiMo Token Plan API的语音聊天机器人，使用OpenAI兼容格式调用TTS和Chat API。

## 功能

- **语音合成 (TTS)**: MiMo-V2.5-TTS，支持8种内置音色、风格控制
- **声音克隆 (VoiceClone)**: 传入参考音频即可克隆任意音色
- **智能对话**: MiMo-V2.5-Pro大模型，口语化回答适合语音播报
- **两种模式**: 文本模式(无需麦克风) / 语音模式

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API密钥

编辑 `config.py`，填入你的API密钥:

```python
MIMO_API_KEY = "your_api_key_here"
```

获取密钥: https://platform.xiaomimimo.com/#/console/api-keys

### 3. 运行

```bash
# 文本模式 (使用MiMo API)
python main.py text --api

# 语音模式
python main.py voice --api

# 指定音色
python main.py text --api --voice 茉莉

# 简单模式 (无需API)
python main.py text
```

## 内置音色

| 音色 | ID | 语言 | 性别 |
|------|-----|------|------|
| 冰糖 | `冰糖` | 中文 | 女 |
| 茉莉 | `茉莉` | 中文 | 女 |
| 苏打 | `苏打` | 中文 | 男 |
| 白桦 | `白桦` | 中文 | 男 |
| Mia | `Mia` | 英文 | 女 |
| Chloe | `Chloe` | 英文 | 女 |
| Milo | `Milo` | 英文 | 男 |
| Dean | `Dean` | 英文 | 男 |

## 风格控制

在 `user` 消息中用自然语言描述风格，或在文本中插入标签:

```python
# 自然语言风格
tts.synthesize("你好！", style="温柔、慵懒的语气，语速稍慢")

# 标签风格 (写在文本中)
tts.synthesize("(开心)今天天气真好！")
tts.synthesize("(东北话)哎呀妈呀，这也太冷了吧！")
tts.synthesize("(唱歌)原谅我这一生不羁放纵爱自由")
```

## 声音克隆

通过传入一段参考音频 (mp3/wav)，克隆其音色进行语音合成:

```bash
# 使用声音克隆模式
python main.py text --api --clone sample.mp3

# 克隆 + 语音模式
python main.py voice --api --clone sample.mp3
```

```python
# 编程调用
from xiaomi_tts import XiaomiTTS

tts = XiaomiTTS()
tts.clone_synthesize_to_file("你好！", "sample.mp3", "cloned.wav")

# 带风格控制
tts.clone_synthesize_to_file("你好！", "sample.mp3", "cloned.wav", style="温柔、缓慢")
```

- 支持 mp3 和 wav 格式
- 音频 base64 编码后不超过 10MB
- 克隆模式下也支持风格控制 (自然语言或标签)

## 文件结构

```
voice/
├── config.py          # 配置 (API密钥、模型、音色)
├── xiaomi_tts.py      # TTS模块 (非流式 + 流式)
├── chat_bot.py        # 对话模块 (MiMo Chat API)
├── main.py            # 主程序入口
├── requirements.txt   # 依赖
└── README.md
```

## API说明

小米MiMo平台兼容OpenAI API格式:

- **Base URL**: `https://api.xiaomimimo.com/v1`
- **认证**: Header `api-key: <your_key>`
- **TTS端点**: `POST /v1/chat/completions` + `audio` 参数
- **Chat端点**: `POST /v1/chat/completions`
- **文档**: https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-synthesis-v2.5
