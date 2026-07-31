#!/usr/bin/env python3
"""生圖 prompt 的單一來源。pipeline 與人工重跑共用同一份,別各寫一份。

規則的完整說明在 story/README.md。這裡是那些規則的可執行版本。
"""

# 參考圖。image 1 永遠是第一話成品頁,鎖畫風、上墨感與手寫黑體字;
# 之後接該頁出場角色的設定圖。光靠文字描述角色會漂——寫「圓形金牌」
# 模型會畫成肉球牌,所以設定圖一定要傳。
REF = {
    'style':    ('images/ep1/07.webp',
                 'the finished page 1 art style, inking and hand-lettered bold Chinese type'),
    'xiaoniao': ('story/refs/xiaoniao.webp', 'MAGE CAT model sheet'),
    'xiaobai':  ('story/refs/xiaobai.webp',  'SWORDSMAN CAT model sheet'),
    'uncle':    ('story/refs/uncle.webp',    'SAMURAI CAT model sheet'),
    'leo':      ('story/refs/leo.webp',      'ROGUE CAT model sheet'),
    'kojiro':   ('story/refs/kojiro.webp',   'DEMON KING CAT model sheet'),
    'past':     ('story/refs/past-four.webp',
                 'model sheet of the four heroes FORMER HUMAN SELVES, '
                 'left to right: mage / swordsman / samurai / rogue'),
}

SHAPES = {'SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON', 'CAPTION'}

BASE = """Same art style as reference image 1: richly detailed vibrant anime fantasy illustration, painterly digital art, glowing magic particles, floating islands and crystal spires in the sky, saturated blues purples and golds. Vertical manga page, THREE horizontal panels stacked top to bottom, separated by thin white gutters, portrait aspect ratio 2:3."""

SHEET = """CHARACTER SHEET - the model sheets provided as reference images are the authority. Copy every listed feature; a character is wrong if any of these is missing.
- MAGE CAT: long-haired brown-grey Maine Coon. Round thin gold-rimmed glasses, ALWAYS clearly visible on her face. Deep blue robe with gold trim. Tall golden staff topped with a large blue orb. Amber eyes. TWO SMALL BIRDS ARE ALWAYS WITH HER: one plump songbird perched on the head of her staff, and one tiny chick perched on the upper-left of her head like a hair clip. Their species, colour and accessories may differ from panel to panel - birds simply come to her; that is why she is called 小鳥不啾. Neither bird ever opens its beak.
- SWORDSMAN CAT: young brown tabby. Silver plate armour with leather straps and buckles, a red scarf-cape, bare head with NO headband and NO hat of any kind. Big amber eyes, fangs showing, energetic. (His 必勝 headband belongs to his former human self only - never draw it on the cat.)
- SAMURAI CAT: white tiger-striped cat. Dark navy lacquered samurai armour, red cord sash, and a round gold medallion hanging on his chest with the single Chinese character 貓 engraved on it. Blue eyes, stern middle-aged look.
- ROGUE CAT: orange tabby. Black hooded cloak covered in gold paw-print buckles. Brown eyes, sly smirk.
- DEMON KING CAT: enormous dark chocolate-brown long-haired cat. Glowing red eyes, black-and-crimson cape, heavy gold chain across the chest, and a round red crest of a tree above a paw."""

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
- The ONLY text allowed in the whole image is: the dialogue listed below, plus the single character 貓 engraved on the samurai cat's gold medallion. No sound effects, no signature, no watermark, no page numbers, no English captions.
- Keep balloons clear of the characters' faces."""

REMINDER = ("FINAL CHECK before you draw: the balloons on this page must NOT all be the same shape. "
            "Each balloon above is labelled SHOUT / OVAL / WEAK / TREMBLE / THOUGHT / DEMON / CAPTION - "
            "draw exactly that shape for each one. A page where every balloon is a rounded rectangle is wrong.")


# 這些頁面沒有對白,也不該有任何文字:角色卡與封面。
# 封面刻意不烤標題進去——文字烤進圖裡,改一個字就是整張重生。
NO_TEXT = {'kojiro', 'cover'}


def build_prompt(name, keys, body):
    """組一頁的完整 prompt。name 在 NO_TEXT 裡的頁面沒有對白也沒有對話框。"""
    manifest = "REFERENCE IMAGES:\n" + "\n".join(
        f"- image {i + 1}: {REF[k][1]}" for i, k in enumerate(keys))
    sheet = SHEET + PAST if 'past' in keys else SHEET
    parts = [BASE, manifest, sheet]
    if name not in NO_TEXT:
        parts += [SHAPES_BLOCK, RULES]
    out = "\n\n".join(parts) + "\n\n" + body
    if name not in NO_TEXT:
        out += "\n\n" + REMINDER
    return out
