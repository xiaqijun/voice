"""小米MiMo语音聊天机器人 - Web面板"""

import os
import json
import uuid
import tempfile
from flask import Flask, render_template, request, jsonify, send_file
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
    """获取所有音色 (内置 + 克隆)"""
    clones = _load_clone_voices()
    clone_list = [{"id": v["id"], "name": v["name"], "lang": "克隆", "gender": "-", "type": "clone"} for v in clones]
    return BUILTIN_VOICES + clone_list


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
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    reply = chat_bot.chat(message)
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

    # 判断是内置音色还是克隆音色
    if voice and voice.startswith("clone_"):
        clones = _load_clone_voices()
        clone = next((v for v in clones if v["id"] == voice), None)
        if not clone or not os.path.exists(clone["file"]):
            return jsonify({"error": "克隆音色不存在"}), 400
        audio = tts.clone_synthesize(text, clone["file"], style=style)
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


@app.route("/api/clear", methods=["POST"])
def api_clear():
    chat_bot.clear_history()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_api()
    print("=" * 50)
    print("  小米MiMo语音聊天机器人 Web面板")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
