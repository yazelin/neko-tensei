#!/usr/bin/env python3
"""生圖 prompt 的單一來源。pipeline 與人工重跑共用同一份,別各寫一份。

規則的完整說明在 story/README.md。這裡是那些規則的可執行版本。

**設定資料本身不寫在這裡,一律讀 story/cast.json。** 這個檔只負責組裝。
分成兩份手寫的下場已經發生過一次:cast.json 寫「樹在爪上」,這裡的 SHEET
跟著寫 tree above a paw,而正典上那個紋章既不是樹也沒有肉球——模型很聽話
地照錯的描述畫,通行證就漂成了掛著繩子的金懷錶。
"""
import json
import pathlib

CAST_PATH = pathlib.Path(__file__).parent.parent / 'story' / 'cast.json'
_CAST = json.loads(CAST_PATH.read_text('utf-8'))

# cast.json 的圖片路徑以 root 為基準(root 相對於 cast.json 自己的位置),
# 這個專案裡等於 repo 根目錄,跟 REF 一直以來的慣例相同。
_BASE = (CAST_PATH.parent / _CAST.get('root', '.')).resolve()

# 參考圖。image 1 永遠是第一話成品頁,鎖畫風、上墨感與手寫黑體字;
# 之後接這一格要鎖的道具/場景,再接出場角色的設定圖。光靠文字描述會漂——
# 寫「圓形金牌」模型會畫成肉球牌,所以設定圖一定要傳。
REF = {'style': (_CAST['style_ref']['path'], _CAST['style_ref']['desc']),
       'cover_style': (_CAST['cover_ref']['path'], _CAST['cover_ref']['desc'])}
for _k, _v in list(_CAST['cast'].items()) + list(_CAST.get('world', {}).items()):
    REF[_k] = (_v['ref'], _v['desc'])

# 哪些 key 是道具/場景(而不是角色)。page_refs 與道具段都靠這個分流。
WORLD_KEYS = tuple(_CAST.get('world', {}))

SHAPES = {'SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON', 'CAPTION'}

BASE = """Same art style as reference image 1: richly detailed vibrant anime fantasy illustration, painterly digital art, glowing magic particles, floating islands and crystal spires in the sky, saturated blues purples and golds. Vertical manga page, THREE horizontal panels stacked top to bottom, separated by thin white gutters, portrait aspect ratio 2:3."""

SHEET = "\n".join(
    ["CHARACTER SHEET - the model sheets provided as reference images are the authority."
     " Copy every listed feature; a character is wrong if any of these is missing."]
    + [f"- {v['sheet']}" for v in _CAST['cast'].values() if v.get('sheet')])

PAST = """

FORMER HUMAN SELVES - only used inside memory bubbles. Copy them from the model sheet exactly; they are NOT generic office workers.
- MAGE's past self: young woman, long straight black hair in a low ponytail, round glasses, a small WHITE BIRD HAIR CLIP above her left ear, cardigan over a tee, an office lanyard round her neck.
- SWORDSMAN's past self: young man, spiky black hair, a WHITE HEADBAND with the two red Chinese characters 必勝 on it, hoodie, mouth open mid-shout, sweating.
- SAMURAI's past self: solidly built middle-aged man, short black hair, stubble, plain black tee, a thick GOLD CHAIN, arms folded. He is muscular and heavy-set, NOT fat and NOT bald.
- ROGUE's past self: young man with LIGHT BLOND hair, black shirt, holding a steaming coffee mug, cool and bored.
THE PAST IS ALWAYS BLACK AND WHITE: render every memory bubble in greyscale with a faint neon-blue glow, exactly like the model sheet. The cat world stays in full colour. This contrast is the whole point."""

SHAPES_BLOCK = """BALLOON SHAPES - each line below names its own balloon shape. Draw that exact shape; do NOT default every balloon to a rounded rectangle. Hand-inked manga feel, slightly irregular outlines, never a perfect geometric shape.
- SHOUT BALLOON: spiky explosion burst with sharp jagged points all around, thick black outline, large bold text.
- OVAL BALLOON: soft hand-drawn organic oval, thin black outline, with a short curved tail pointing at the speaker.
- WEAK BALLOON: small squashed oval with a thin wobbly or dashed outline, small text, deflated feeling.
- TREMBLE BALLOON: oval whose outline shivers in a wavy zigzag, for shock or fear.
- THOUGHT BALLOON: fluffy cloud shape with scalloped edges, tail made of three shrinking circles.
- DEMON BALLOON: black-filled balloon with white text and a ragged spiked edge, heavy and oppressive.
- CAPTION BOX: plain straight-cornered rectangle, the only right-angled box on the page."""

RULES = """DIALOGUE RULES - the most important part, follow exactly:
- All text is TRADITIONAL CHINESE (zh-TW, Taiwan). Copy each string CHARACTER BY CHARACTER exactly as given. Never simplify a character, never substitute a similar-looking character, never invent extra characters, never leave a character out.
- The text allowed in the whole image is exactly these three things: (1) the dialogue listed below; (2) the single character 貓 engraved on the samurai cat's gold medallion; (3) in-world English UI text that a PANEL description explicitly asks for - screens, holographic displays, progress bars, banners, signboards. Draw (3) exactly as the panel description spells it, in plain Latin letters, as part of the scenery.
- Nothing else: no sound effects, no signature, no watermark, no page numbers, and never an English translation or transcription of the Chinese dialogue.
- Keep balloons clear of the characters' faces."""

REMINDER = ("FINAL CHECK before you draw: the balloons on this page must NOT all be the same shape. "
            "Each balloon above is labelled SHOUT / OVAL / WEAK / TREMBLE / THOUGHT / DEMON / CAPTION - "
            "draw exactly that shape for each one. A page where every balloon is a rounded rectangle is wrong.")


COVER_RULES = """COVER TEXT RULES - the cover carries lettering, follow exactly:
- All text is TRADITIONAL CHINESE (zh-TW, Taiwan). Copy each string CHARACTER BY CHARACTER exactly as given. Never simplify a character, never substitute a similar-looking character, never invent extra characters, never leave a character out.
- The ONLY text on the cover is the title lockup, the character name tags and the bottom episode band described below, plus the single character 貓 on the samurai cat's medallion. No tagline, no author name, no watermark, no signature, no English.
- Lettering style follows reference image 2: chunky hand-drawn brush-gothic Chinese display type with a thick gold outline and a dark drop shadow, sitting on top of the artwork."""


# 角色卡完全沒有文字。封面有文字,但沒有對話框——那是兩件事,別混在一起。
NO_TEXT = {'kojiro'}
NO_BALLOONS = {'kojiro', 'cover'}


def world_block(keys):
    """這一格要鎖的道具/場景。沒有就回 None。

    順序上排在 CHARACTER SHEET 之前:場景與道具決定這一格長什麼樣,角色是
    放進去的東西(照 comic-studio 的 world 庫慣例)。
    """
    items = [_CAST['world'][k]['sheet'] for k in keys if k in WORLD_KEYS]
    if not items:
        return None
    return ("PROPS AND PLACES - the reference images are the authority for these."
            " Copy them exactly; they must look the same in every panel and every episode.\n"
            + "\n".join(f"- {s}" for s in items))


def build_prompt(name, keys, body):
    """組一頁的完整 prompt。name 在 NO_TEXT 裡的頁面沒有對白也沒有對話框。"""
    manifest = "REFERENCE IMAGES:\n" + "\n".join(
        f"- image {i + 1}: {REF[k][1]}" for i, k in enumerate(keys))
    sheet = SHEET + PAST if 'past' in keys else SHEET
    parts = [BASE, manifest]
    world = world_block(keys)
    if world:
        parts.append(world)
    parts.append(sheet)
    if name not in NO_BALLOONS:
        parts += [SHAPES_BLOCK, RULES]
    elif name not in NO_TEXT:
        parts.append(COVER_RULES)          # 有字、沒有對話框
    out = "\n\n".join(parts) + "\n\n" + body
    if name not in NO_BALLOONS:
        out += "\n\n" + REMINDER
    return out
