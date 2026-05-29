"""小米MiMo语音聊天机器人 - Web面板"""

import os
import json
import uuid
import base64
import tempfile
from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
from xiaomi_tts import XiaomiTTS
from chat_bot import ChatBot, SimpleChatBot
import config

app = Flask(__name__)

# 全局实例
tts = None
chat_bot = None

VOICES_DIR = os.path.join(os.path.dirname(__file__), "voices")
VOICES_META = os.path.join(VOICES_DIR, "voices.json")
os.makedirs(VOICES_DIR, exist_ok=True)

BUILTIN_VOICES = [
    {"id": "冰糖", "name": "冰糖", "lang": "中文", "gender": "女", "type": "builtin"},
    {"id": "茉莉", "name": "茉莉", "lang": "中文", "gender": "女", "type": "builtin"},
    {"id": "苏打", "name": "苏打", "lang": "中文", "gender": "男", "type": "builtin"},
    {"id": "白桦", "name": "白桦", "lang": "中文", "gender": "男", "type": "builtin"},
    {"id": "Mia", "name": "Mia", "lang": "英文", "gender": "女", "type": "builtin"},
    {"id": "Chloe", "name": "Chloe", "lang": "英文", "gender": "女", "type": "builtin"},
    {"id": "Milo", "name": "Milo", "lang": "英文", "gender": "男", "type": "builtin"},
    {"id": "Dean", "name": "Dean", "lang": "英文", "gender": "男", "type": "builtin"},
]


def _load_clone_voices():
    """加载已保存的克隆音色"""
    if not os.path.exists(VOICES_META):
        return []
    with open(VOICES_META, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_clone_voices(voices):
    """保存克隆音色列表"""
    with open(VOICES_META, "w", encoding="utf-8") as f:
        json.dump(voices, f, ensure_ascii=False, indent=2)


def _get_all_voices():
    """获取所有音色 (内置 + 克隆 + 声音设计)"""
    clones = _load_clone_voices()
    result = list(BUILTIN_VOICES)
    for v in clones:
        if v.get("type") == "design":
            result.append({"id": v["id"], "name": v["name"], "lang": "设计", "gender": "-", "type": "design"})
        else:
            result.append({"id": v["id"], "name": v["name"], "lang": "克隆", "gender": "-", "type": "clone"})
    return result


def _get_default_voice():
    """获取默认音色ID"""
    meta_path = os.path.join(VOICES_DIR, "default.txt")
    if os.path.exists(meta_path):
        return open(meta_path, "r", encoding="utf-8").read().strip()
    return "冰糖"


def _set_default_voice(voice_id):
    """设置默认音色"""
    meta_path = os.path.join(VOICES_DIR, "default.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(voice_id)


def init_api():
    global tts, chat_bot
    if config.MIMO_API_KEY != "your_api_key_here":
        tts = XiaomiTTS()
        chat_bot = ChatBot()
    else:
        tts = None
        chat_bot = SimpleChatBot()


@app.route("/")
def index():
    api_ready = tts is not None
    all_voices = _get_all_voices()
    default_voice = _get_default_voice()
    return render_template("index.html", api_ready=api_ready, voices=all_voices, default_voice=default_voice)


@app.route("/voices")
def voices_page():
    all_voices = _get_all_voices()
    default_voice = _get_default_voice()
    return render_template("voices.html", voices=all_voices, default_voice=default_voice)


@app.route("/api/voices")
def get_voices():
    return jsonify({"voices": _get_all_voices(), "default": _get_default_voice()})


@app.route("/api/voices/default", methods=["POST"])
def set_default_voice():
    data = request.get_json()
    voice_id = data.get("voice_id", "")
    all_ids = [v["id"] for v in _get_all_voices()]
    if voice_id not in all_ids:
        return jsonify({"error": "无效的音色ID"}), 400
    _set_default_voice(voice_id)
    return jsonify({"ok": True, "default": voice_id})


@app.route("/api/voices/clone", methods=["POST"])
def save_clone_voice():
    """上传并保存一个克隆音色"""
    name = request.form.get("name", "").strip()
    voice_file = request.files.get("voice_file")

    if not name:
        return jsonify({"error": "请输入音色名称"}), 400
    if not voice_file:
        return jsonify({"error": "请上传参考音频"}), 400

    ext = os.path.splitext(voice_file.filename)[1].lower()
    if ext not in (".mp3", ".wav"):
        return jsonify({"error": "仅支持 mp3 和 wav 格式"}), 400

    voice_id = "clone_" + uuid.uuid4().hex[:8]
    file_path = os.path.join(VOICES_DIR, voice_id + ext)
    voice_file.save(file_path)

    clones = _load_clone_voices()
    clones.append({"id": voice_id, "name": name, "file": file_path})
    _save_clone_voices(clones)

    return jsonify({"ok": True, "id": voice_id, "name": name})


@app.route("/api/voices/clone/<voice_id>", methods=["DELETE"])
def delete_clone_voice(voice_id):
    """删除一个克隆音色"""
    clones = _load_clone_voices()
    target = None
    for v in clones:
        if v["id"] == voice_id:
            target = v
            break
    if not target:
        return jsonify({"error": "音色不存在"}), 404

    if os.path.exists(target["file"]):
        os.remove(target["file"])

    clones = [v for v in clones if v["id"] != voice_id]
    _save_clone_voices(clones)

    return jsonify({"ok": True})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    voice_context = data.get("voice_context", "").strip() or None
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    reply = chat_bot.chat(message, voice_context=voice_context)
    if reply is None:
        return jsonify({"error": "对话请求失败"}), 500

    return jsonify({"reply": reply})


@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json()
    text = data.get("text", "").strip()
    voice = data.get("voice")
    style = data.get("style", "").strip() or None

    if not text:
        return jsonify({"error": "文本不能为空"}), 400
    if not tts:
        return jsonify({"error": "API未配置"}), 500

    # 如果没有指定风格，使用默认的自然人声风格
    if not style:
        style = "用自然真实的语气说话，像朋友聊天一样轻松，语速适中，有适当的呼吸感和停顿"

    # 判断音色类型
    if voice and voice.startswith("clone_"):
        clones = _load_clone_voices()
        clone = next((v for v in clones if v["id"] == voice), None)
        if not clone or "file" not in clone or not os.path.exists(clone.get("file", "")):
            return jsonify({"error": "克隆音色不存在"}), 400
        audio = tts.clone_synthesize(text, clone["file"], style=style)
    elif voice and voice.startswith("design_"):
        clones = _load_clone_voices()
        design = next((v for v in clones if v["id"] == voice), None)
        if not design or "description" not in design:
            return jsonify({"error": "声音设计音色不存在"}), 400
        audio = tts.design_synthesize(text, design["description"])
    else:
        if voice:
            tts.set_voice(voice)
        audio = tts.synthesize(text, style=style)

    if not audio:
        return jsonify({"error": "语音合成失败"}), 500

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(audio)
    tmp.close()
    return send_file(tmp.name, mimetype="audio/wav", as_attachment=False, download_name="tts.wav")


@app.route("/api/tts/clone", methods=["POST"])
def api_tts_clone():
    """临时克隆 (不保存)"""
    text = request.form.get("text", "").strip()
    style = request.form.get("style", "").strip() or None
    voice_file = request.files.get("voice_file")

    if not text:
        return jsonify({"error": "文本不能为空"}), 400
    if not voice_file:
        return jsonify({"error": "请上传参考音频文件"}), 400
    if not tts:
        return jsonify({"error": "API未配置"}), 500

    ext = os.path.splitext(voice_file.filename)[1].lower()
    if ext not in (".mp3", ".wav"):
        return jsonify({"error": "仅支持 mp3 和 wav 格式"}), 400

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    voice_file.save(tmp)
    tmp.close()

    try:
        audio = tts.clone_synthesize(text, tmp.name, style=style)
    finally:
        os.remove(tmp.name)

    if not audio:
        return jsonify({"error": "声音克隆合成失败"}), 500

    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out.write(audio)
    out.close()
    return send_file(out.name, mimetype="audio/wav", as_attachment=False, download_name="clone.wav")


@app.route("/api/tts/design", methods=["POST"])
def api_tts_design():
    """声音设计: 通过文字描述生成声音"""
    data = request.get_json()
    text = data.get("text", "").strip()
    description = data.get("description", "").strip()

    if not text:
        return jsonify({"error": "文本不能为空"}), 400
    if not description:
        return jsonify({"error": "请描述你想要的声音"}), 400
    if not tts:
        return jsonify({"error": "API未配置"}), 500

    audio = tts.design_synthesize(text, description)
    if not audio:
        return jsonify({"error": "声音设计合成失败"}), 500

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(audio)
    tmp.close()
    return send_file(tmp.name, mimetype="audio/wav", as_attachment=False, download_name="design.wav")


@app.route("/api/voices/design", methods=["POST"])
def save_design_voice():
    """保存声音设计为可复用音色"""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        return jsonify({"error": "请输入音色名称"}), 400
    if not description:
        return jsonify({"error": "请描述声音"}), 400

    voice_id = "design_" + uuid.uuid4().hex[:8]
    clones = _load_clone_voices()
    clones.append({"id": voice_id, "name": name, "description": description, "type": "design"})
    _save_clone_voices(clones)

    return jsonify({"ok": True, "id": voice_id, "name": name})


@app.route("/api/asr", methods=["POST"])
def api_asr():
    """语音识别: 将录音转为文字 (使用 mimo-v2.5 音频理解)"""
    if not tts:
        return jsonify({"error": "API未配置"}), 500

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "未提供音频"}), 400

    # 读取音频并转为 base64
    audio_bytes = audio_file.read()
    ext = os.path.splitext(audio_file.filename)[1].lower() if audio_file.filename else ".webm"
    mime_map = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".webm": "audio/webm", ".ogg": "audio/ogg"}
    mime = mime_map.get(ext, "audio/webm")
    b64 = base64.b64encode(audio_bytes).decode("utf-8")

    try:
        client = OpenAI(
            api_key=config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        completion = client.chat.completions.create(
            model="mimo-v2.5",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": f"data:{mime};base64,{b64}"}
                        },
                        {
                            "type": "text",
                            "text": (
                                "请分析这段语音，输出以下信息：\n"
                                "1. 转录文字：原样转录语音内容\n"
                                "2. 情绪描述：说话人的情绪状态（如开心、悲伤、生气、平静、紧张等）\n"
                                "3. 语速节奏：语速快慢、是否有停顿（如语速较快、语速缓慢、有明显停顿等）\n"
                                "4. 语气风格：说话的语气特点（如温柔、严肃、轻松、急促、低沉等）\n\n"
                                "请严格按以下格式输出，不要添加其他内容：\n"
                                "[情绪:XX, 语速:XX, 语气:XX]转录文字"
                            )
                        }
                    ]
                }
            ],
            max_tokens=500,
        )
        text = completion.choices[0].message.content
        if not text and hasattr(completion.choices[0].message, "reasoning_content"):
            text = completion.choices[0].message.reasoning_content
        return jsonify({"text": text or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
def api_clear():
    chat_bot.clear_history()
    return jsonify({"ok": True})


@app.route("/api/skill/reload", methods=["POST"])
def api_reload_skill():
    """强制重新加载 skill 文件"""
    length = chat_bot.reload_skill()
    return jsonify({"ok": True, "length": length})


@app.route("/api/skill", methods=["GET"])
def api_get_skill():
    """查看当前系统提示词状态"""
    base_len = len(chat_bot._base_prompt)
    skill_len = len(chat_bot._last_skill_content)
    sections = chat_bot._loader._all_names
    return jsonify({
        "base_length": base_len,
        "skill_length": skill_len,
        "total_length": base_len + skill_len,
        "available_sections": sections,
    })


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ssl", action="store_true", help="启用HTTPS (自签名证书)")
    parser.add_argument("--port", type=int, default=5000, help="端口号")
    args = parser.parse_args()

    init_api()

    ssl_context = None
    protocol = "http"
    if args.ssl:
        cert_path = os.path.join(os.path.dirname(__file__), "cert.pem")
        key_path = os.path.join(os.path.dirname(__file__), "key.pem")
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = (cert_path, key_path)
            protocol = "https"
        else:
            print("[!] SSL证书文件不存在，请先生成: openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes")

    print("=" * 50)
    print("  小米MiMo语音聊天机器人 Web面板")
    print(f"  {protocol}://0.0.0.0:{args.port}")
    if args.ssl:
        print("  (HTTPS已启用，麦克风功能可用)")
    else:
        print("  (HTTP模式，麦克风需要HTTPS或localhost)")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=args.port, ssl_context=ssl_context)
