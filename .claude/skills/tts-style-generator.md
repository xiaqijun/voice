---
name: tts-style-generator
description: Use when generating TTS voice output, writing voice style tags, designing voice personas, cloning voices, or describing voice characteristics for MiMo-V2.5-TTS
---

# TTS Style Generator

## Overview

Three-layer knowledge for MiMo TTS voice control: **tag system** (what to write) → **voice design** (how to describe) → **text craft** (how to write for speech).

## When to Use

- Writing emotion/style tags for TTS synthesis
- Designing voice descriptions for VoiceDesign model
- Optimizing text for natural speech output
- Switching between voice personas (御姐/少年/萝莉/叔音)

## Quick Reference: Tag System

### Overall Style Tags (beginning of text)

| Category | Tags |
|----------|------|
| Basic Emotion | 开心, 悲伤, 生气, 害怕, 惊讶, 兴奋, 委屈, 平静, 冷淡 |
| Complex Emotion | 忧郁, 释然, 无奈, 愧疚, 嫉妒, 疲惫, 不安, 感性 |
| Tone | 温柔, 冷淡, 活泼, 严肃, 慵懒, 调皮, 低沉, 干练, 尖锐 |
| Timbre | 磁性, 醇厚, 清亮, 空灵, 稚嫩, 苍老, 甜美, 沙哑, 优雅 |
| Character | 夹子音, 大姐姐音, 正太音, 大叔音, 台湾腔 |
| Dialect | 东北话, 四川话, 河南话, 粤语 |
| Role-play | Any character name (孙悟空, 林黛玉, etc.) |
| Singing | 唱歌, sing, singing |

### Inline Tags (middle of text)

| Category | Tags |
|----------|------|
| Pace | 深吸一口气, 深呼吸, 叹气, 长叹一声, 喘气, 屏息, 停顿, 语速加快, 语速放慢, 急促 |
| Emotion | 紧张, 害怕, 兴奋, 疲惫, 委屈, 撒娇, 愧疚, 震惊, 不耐烦, 无奈, 担心 |
| Voice | 颤抖, 声音发颤, 声调变化, 破音, 鼻音, 气声, 沙哑, 提高嗓门, 低声, 轻声 |
| Laugh/Cry | 微笑, 轻笑, 大笑, 冷笑, 抽泣, 呜咽, 哽咽, 嚎啕大哭, 苦笑, 强颜欢笑 |

### Tag Format

```text
(标签)文本内容。
(标签1 标签2)多标签组合。
(标签)第一句。(标签)第二句。每句独立标签。
```

## Voice Persona Quick Map

| Persona | Spectrum | Key Tags |
|---------|----------|----------|
| 御姐 | Low freq full + mid-high sharp | (磁性) (沉稳) (大姐姐音) |
| 少年 | Low cut + mid-high strong | (活泼) (清脆) (正太音) |
| 萝莉 | Nasal 800Hz-1.5kHz | (可爱) (撒娇) (夹子音) |
| 叔音 | Chest 80-150Hz + air | (低沉) (沧桑) (大叔音) |
| 青年 | Balanced | (自然) (阳光) (自信) |

## Emotion-Pace-Resonance Map

| Emotion | Pace | Pitch | Power | Resonance | Tags |
|---------|------|-------|-------|-----------|------|
| Happy | Fast | High | Hard | Mouth front | 兴奋, 开心, 活泼 |
| Sad | Slow | Low | Breath | Chest | 悲伤, 叹气, 低沉 |
| Angry | Fast | High | Strong | Mouth+Nasal | 生气, 愤怒, 严肃 |
| Gentle | Slow | Mid-low | Soft | Chest | 温柔, 轻柔, 温暖 |
| Nervous | Fast | High | Tremble | Nasal | 紧张, 害怕, 颤抖 |
| Cold | Mid-slow | Mid-low | Weak | Mouth | 冷淡, 平静, 无所谓 |
| Lazy | Slow | Low | Weak | Chest | 慵懒, 随意, 有气无力 |
| Playful | Fast | High | Bouncy | Mouth front | 活泼, 俏皮, 调皮 |
| Serious | Slow | Mid-low | Steady | Chest | 严肃, 郑重, 干练 |
| Magnetic | Slow | Low | Breath | Chest | 磁性, 低语, 气声 |

## Voice Design Description

For `mimo-v2.5-tts-voicedesign` model, describe voice in 1-4 sentences covering:

| Dimension | Example |
|-----------|---------|
| Gender/Age | 年轻女性、中年男性 |
| Timbre | 温柔甜美、低沉磁性、沙哑沧桑 |
| Emotion | 温暖亲切、冷淡疏离 |
| Pace | 语速稍慢、说话很快 |
| Role | 温柔的护士、深夜电台主播 |
| Style | 轻声细语、字正腔圆 |

Good examples:
- `年轻女性，温柔甜美的声音，语速稍慢，像朋友在耳边轻声聊天`
- `中年男性，低沉磁性的嗓音，带有轻微颗粒感，像深夜电台主播`

## Voice Clone Tips

- Reference audio: 10-30s, clear, no noise, mp3/wav
- Style tags still work after cloning: `(温柔)晚安。`
- Background noise in reference will be cloned too

## Text Craft for TTS

### Punctuation Effects

| Mark | Effect |
|------|--------|
| `。` | Normal pause, falling tone |
| `！` | Emphasis, rising tone |
| `？` | Question, rising end |
| `...` | Hesitation, trailing off |
| `——` | Emphasis, elongation |
| `～` | Playful, cute, elongated |

### Writing Rules

1. **Short sentences, spoken style** — 大家多穿点，别感冒了 (not 请各位同事注意添衣保暖)
2. **Concrete words** — 又甜又脆 (not 非常好)
3. **Filler words** — 嗯、呀、哎、哈哈 for naturalness
4. **Punctuation rhythm** — 省略号 for hesitation, 破折号 for emphasis
5. **Numbers to text** — 100 → 一百, 2024 → 二零二四
6. **Break long sentences** — Max ~30 chars per sentence

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Same emotion for every sentence | Vary tags per sentence |
| All fast or all slow pace | Alternate fast/slow for rhythm |
| No breathing/pauses | Add (停顿) or (叹气) at transitions |
| Formal written style | Use spoken, casual language |
| Contradicting voice description | Don't pair childish voice + CEO aura |
| Nested tags | Keep tags flat, no nesting |
| Vague descriptions | Avoid "普通", "正常", "外国口音" |

## Expression Principles

1. **Match emotion to content** — comfort = gentle, congratulations = excited
2. **Rhythm variation** — key info slow, transitions normal, excitement fast
3. **Breathing space** — add (深呼吸) or (停顿) at emotional transitions
4. **Punchline timing** — (停顿) before joke punchline, then (大笑)
5. **Mixed emotions** — try "温柔但疲惫", "带泪的微笑"
6. **Director mode** — complex scenes use Character + Scene + Guidance
