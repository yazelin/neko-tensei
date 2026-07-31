# 第二話：魔力不足，得加 Token！

先讀 [`story/README.md`](README.md) 的鐵律與框型表再動手。對白逐字寫在下面各頁，**同一份字、同一個框型直接進生圖 prompt**。

## 這一話在講什麼

第一話結尾那雙紅眼睛，是這一話的答案。四貓打贏史萊姆的隔一秒就發現：**這個世界的魔力是配給的**，而配給的人是荒坂小次郎。

三個轉折：

1. **魔力歸零** — 打贏了，但打光了。異世界原來也有額度。
2. **魔王現身，開出條件** — 想要魔力就得過審核。四貓認出這個流程，因為前世每天都在跑。
3. **看懂規則** — 小鳥不啾發現配給規則是「寫出來的」，不是「注定的」。她改了一行，魔力回流。魔王不但沒生氣，反而承認他們。

收尾埋第三話：遠方黑塔上另一個更大、更冷的魔法陣。**那個不是小次郎點的。**

## 幾條不能違反的設定

- 魔力＝配給的額度，不是體力。累不累跟有沒有魔力是兩件事。
- 額度歸零時能力不是消失，是**降級**：爪光會閃兩下、隱形只隱一半、真刀變木刀。降級比消失好笑，也比較好畫。
- 荒坂小次郎不是反派，是**管理員**。他從頭到尾沒出手打人。
- 「得加 Token」是里歐撿到的木牌，不是誰喊的口號。牌子先出現，笑點才成立。
- 小鳥不啾是第一個覺醒魔法的人（第一話設定），所以由她看懂符文，這條線要接得住。

## 這一話的框型節奏

框型本身就在說故事：**開場是爆炸框（贏了），中段整片垮成抖框與弱框（沒電了），魔王一出場全換成黑底尖刺框（壓過去），小鳥不啾看懂規則那一刻是雲朵思考框（腦內），最後一格才回到爆炸框（翻回來）。**

一頁裡不要出現兩個以上同型框，除非是刻意的對稱。

## 共用 prompt 前綴

每一頁的 prompt ＝ BASE ＋ REFERENCE IMAGES 清單 ＋ CHARACTER SHEET ＋ BALLOON SHAPES ＋ DIALOGUE RULES ＋ 該頁 PANEL 段落。參考圖見各頁標註，**image 1 一律是 `images/ep1/07.webp`**。

```
Same art style as reference image 1: richly detailed vibrant anime fantasy illustration,
painterly digital art, glowing magic particles, floating islands and crystal spires in the sky,
saturated blues purples and golds. Vertical manga page, THREE horizontal panels stacked top to
bottom, separated by thin white gutters, portrait aspect ratio 2:3.

REFERENCE IMAGES:
- image 1: the finished page 1 art style, inking and hand-lettered bold Chinese type
- image 2..n: <該頁出場角色的 model sheet,見各頁標註>

CHARACTER SHEET - the model sheets provided as reference images are the authority. Copy every
listed feature; a character is wrong if any of these is missing.
- MAGE CAT: long-haired brown-grey Maine Coon. Round thin gold-rimmed glasses, ALWAYS clearly
  visible on her face. Deep blue robe with gold trim. Tall golden staff topped with a large blue
  orb. Amber eyes. TWO SMALL BIRDS ARE ALWAYS WITH HER: one plump songbird perched on the head of
  her staff, and one tiny chick perched on the upper-left of her head like a hair clip. Their
  species, colour and accessories may differ from panel to panel - birds simply come to her; that
  is why she is called 小鳥不啾. Neither bird ever opens its beak.
- SWORDSMAN CAT: young brown tabby. Silver plate armour with leather straps and buckles, a red
  scarf-cape, bare head with NO headband and NO hat of any kind. Big amber eyes, fangs showing,
  energetic. (His 必勝 headband belongs to his former human self only - never draw it on the cat.)
- SAMURAI CAT: white tiger-striped cat. Dark navy lacquered samurai armour, red cord sash, and a
  round gold medallion hanging on his chest with the single Chinese character 貓 engraved on it.
  Blue eyes, stern middle-aged look.
- ROGUE CAT: orange tabby. Black hooded cloak covered in gold paw-print buckles. Brown eyes, sly
  smirk.
- DEMON KING CAT: enormous dark chocolate-brown long-haired cat. Glowing red eyes,
  black-and-crimson cape, heavy gold chain across the chest, and on that chain a round medallion
  crest: a gold rim, a black face, and a flat red three-balled emblem (one straight stem with a
  ball on top plus one short branch to each side, each ending in a ball).

BALLOON SHAPES - each line below names its own balloon shape. Draw that exact shape; do NOT
default every balloon to a rounded rectangle. Hand-inked manga feel, slightly irregular outlines,
never a perfect geometric shape.
- SHOUT BALLOON: spiky explosion burst with sharp jagged points all around, thick black outline,
  large bold text.
- OVAL BALLOON: soft hand-drawn organic oval, thin black outline, with a short curved tail
  pointing at the speaker.
- WEAK BALLOON: small squashed oval with a thin wobbly or dashed outline, small text, deflated
  feeling.
- TREMBLE BALLOON: oval whose outline shivers in a wavy zigzag, for shock or fear.
- THOUGHT BALLOON: fluffy cloud shape with scalloped edges, tail made of three shrinking circles.
- DEMON BALLOON: black-filled balloon with white text and a ragged spiked edge, heavy and
  oppressive.
- CAPTION BOX: plain straight-cornered rectangle, the only right-angled box on the page.

DIALOGUE RULES - the most important part, follow exactly:
- All text is TRADITIONAL CHINESE (zh-TW, Taiwan). Copy each string CHARACTER BY CHARACTER exactly
  as given. Never simplify a character, never substitute a similar-looking character, never invent
  extra characters, never leave a character out.
- The ONLY text allowed in the whole image is: the dialogue listed below, plus the single
  character 貓 engraved on the samurai cat's gold medallion. No sound effects, no signature, no
  watermark, no page numbers, no English captions.
- Keep balloons clear of the characters' faces.
```

---

## 00 封面

外稿。荒坂小次郎繪，四貓＋他自己（紅眼魔王）＋里歐舉著「得加 Token」木牌。

修過兩處：

- `中年攻城屎` → `中年攻城屍`（原稿誤字）
- 底部字幕 `第一話：我們怎麼變成貓了？！` → `第二話：魔力不足，得加 Token！`

做法是兩步：先像素級補字（只動那幾個字），再把補過的圖當參考圖重生一次。只補不重生，補丁那塊會糊——貼上去的字是另一種筆觸，跟荒坂小次郎的手繪對不上。重生的 prompt 要求忠實重現構圖、只把那兩塊重新畫乾淨，並把正確的字再寫一次。

---

## 01 打贏了，然後沒電了

參考圖：`images/ep1/07.webp`（畫風）＋ `story/refs/` 的小鳥不啾、小白++、中年攻城屍、里歐

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| 上 | 四貓在爆開的史萊姆殘骸旁歡呼，肉球高舉 | 小白++「贏啦——！我們打贏史萊姆了！」 | 爆炸框 |
| 上 | | 中年攻城屍「哼。還算堪用。」 | 橢圓框 |
| 中 | 小鳥不啾舉杖想放慶祝煙火，藍寶石只咳出一點火花就熄了 | 小鳥不啾「來，慶祝煙火一發——」 | 橢圓框 |
| 中 | | 火花旁「……噗。」 | 弱框 |
| 下 | 四貓面前浮出半透明藍色狀態面板，能量條見底，四貓面無表情 | 面板上印著「魔力餘額　0／本日配給已用盡」 | 印在面板上 |
| 下 | | 里歐「異世界……也有額度？」 | 弱框 |

用意：續第一話最後一格的情緒，再一秒打斷。框型從爆炸一路垮到弱框，「沒電」不用講的。

```
PANEL 1 (top): the four cat adventurers cheer beside the burst remains of a green slime on a
flowery meadow, paws in the air, joyful.
  SHOUT BALLOON from the SWORDSMAN CAT: 贏啦——！我們打贏史萊姆了！
  OVAL BALLOON from the SAMURAI CAT: 哼。還算堪用。
PANEL 2 (middle): close-up of the MAGE CAT raising her golden staff to fire a celebration firework
- but the blue orb only coughs out one tiny weak spark and dies. Her eyes go wide and blank.
  OVAL BALLOON from the MAGE CAT: 來，慶祝煙火一發——
  WEAK BALLOON beside the dying spark: ……噗。
PANEL 3 (bottom): a large semi-transparent glowing blue holographic status panel floats in the air
in front of all four cats, with one long completely drained energy bar. All four cats stare at it,
jaws slack, utterly deadpan.
  Text printed on the holographic panel itself (pale cyan glowing letters, not in a balloon), two
  lines: 魔力餘額　0 / 本日配給已用盡
  WEAK BALLOON from the ROGUE CAT: 異世界……也有額度？
```

---

## 02 全體降級，與一塊木牌

參考圖：`images/ep1/07.webp`（畫風）＋ `story/refs/` 的小白++、里歐、中年攻城屍、小鳥不啾

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| 上 | 小白++揮爪，爪光閃兩下就散成煙 | 小白++「爪光只閃兩下就沒了？」 | 抖框 |
| 中 | 里歐只隱形了一半：上半身透明，橘尾巴跟後腿還在 | 里歐「隱形只隱一半。這比沒隱還慘。」 | 弱框 |
| 下 | 中年攻城屍拔刀，刀身是素面木刀；旁邊插著一塊舊木牌 | 中年攻城屍「老夫的刀……變木頭了。」 | 弱框 |
| 下 | | 木牌上寫「得加 Token」 | 畫在木牌上 |
| 下 | | 小鳥不啾「誰立的牌子？」 | 橢圓框 |

用意：降級三連發，整頁沒有一個硬框。中格是全話最好笑的一格，要畫足。木牌先出現，笑點才成立。

第一次生出來里歐整隻是實心的，笑點沒了。「半透明」這種效果**要寫成「背後的花跟天空看得穿過去」**，不能只寫 transparent／ghostly——模型會理解成加一層光暈。透明與實心的分界也要指定在哪（腰部）。

```
PANEL 1 (top): the SWORDSMAN CAT swings his paw for a glowing claw strike, but the claw light
flickers twice and fizzles out into smoke. He looks at his own paw, confused.
  TREMBLE BALLOON from the SWORDSMAN CAT: 爪光只閃兩下就沒了？
PANEL 2 (middle): the ROGUE CAT's invisibility spell only half worked. His head, chest, arms and
hood are ALMOST COMPLETELY SEE-THROUGH - the flowers and the sky behind him are clearly visible
straight through his body, only a faint shimmering outline of him is left. From the waist down he
is still fully solid and opaque: a normal orange tabby tail and hind legs standing in the grass.
The cut between transparent and solid is sharp and obvious. He looks down at his own solid legs,
mortified.
  WEAK BALLOON from the ROGUE CAT: 隱形只隱一半。這比沒隱還慘。
PANEL 3 (bottom): the SAMURAI CAT draws his katana and the blade is now a plain unpainted wooden
practice sword. Beside him, stuck in the dirt, is an old weathered wooden signboard.
  WEAK BALLOON from the SAMURAI CAT: 老夫的刀……變木頭了。
  Text painted on the wooden signboard itself (dark brush strokes on wood, not in a balloon):
  得加 Token
  OVAL BALLOON from the MAGE CAT: 誰立的牌子？
```

---

## 03 紅眼睛降臨

參考圖：`images/ep1/07.webp`（畫風）＋ `story/refs/` 的荒坂小次郎與四位主角

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| 上 | 天空裂開，巨大紅色魔法陣展開，中心是紅色三球紋章（直莖頂一球、左右短枝各一球），四貓仰頭顯得很小 | 小鳥不啾「天空……裂開了。」 | 抖框 |
| 中 | 魔王從魔法陣降下：暗棕長毛、紅眼、黑紅披風、金鎖鍊、紅色紋章 | 魔王「這個世界的魔力，是我在配的。」 | 魔王框 |
| 下 | 四貓炸毛後退，魔王俯視，露齒慢笑 | 魔王「四隻空瓶子，還敢慶祝。」 | 魔王框 |

用意：對比要拉大，四貓要小。**框型在這一頁換手**——四貓的抖框被黑底尖刺框壓過去，畫面的主導權轉給魔王。他的笑是「有意思」不是「要吃你」，這裡就要鋪。

```
PANEL 1 (top): the sky splits open and an enormous crimson magic circle unfurls overhead, its
runes glowing red, a flat red three-balled crest at its centre - one straight stem with a ball on
top plus one short branch to each side, each ending in a ball. The four small cats look up from below,
tiny against it.
  TREMBLE BALLOON from the MAGE CAT: 天空……裂開了。
PANEL 2 (middle): the DEMON KING CAT descends out of the crimson magic circle - colossal, dark
chocolate-brown long fur, glowing red eyes, black-and-crimson cape billowing, heavy gold chain,
red crest emblem. Majestic and terrifying.
  DEMON BALLOON from the DEMON KING CAT: 這個世界的魔力，是我在配的。
PANEL 3 (bottom): the four cats' fur puffs up in fright as they stagger backwards; the Demon King
looms above them looking down, fangs showing in a slow amused grin.
  DEMON BALLOON from the DEMON KING CAT: 四隻空瓶子，還敢慶祝。
```

---

## 04 這不就是 code review

參考圖：`images/ep1/07.webp`（畫風）＋ `story/refs/` 的荒坂小次郎與四位主角

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| 上 | 中年攻城屍雙爪舉木刀擋在三人前面，姿勢很帥，刀很木 | 中年攻城屍「都退後。老夫擋。」 | 爆炸框 |
| 上 | | 里歐「大叔，你那把是木頭。」 | 弱框 |
| 中 | 魔王抬起巨爪，爪尖攤開一張巨大半透明卷軸，表面是空的欄線 | 魔王「想要魔力？先過我的審核。」 | 魔王框 |
| 下 | 四貓同時面無表情；每隻貓頭上浮一顆發光小圓框，框裡是前世的人類身影 | 一個橫跨四貓的框「……這不就是 code review。」 | 雲朵思考框 |

用意：**內心 OS 的示範頁**。這一格定義了本作的語法：貓形＝現在，人臉＝內心。小圓框裡不要有字。上格「爆炸框配木刀」是刻意的反差笑點。

```
PANEL 1 (top): the SAMURAI CAT plants himself bravely in front of the other three with his wooden
practice sword raised in both paws - heroic pose, but the sword is obviously just wood.
  SHOUT BALLOON from the SAMURAI CAT: 都退後。老夫擋。
  WEAK BALLOON from the ROGUE CAT: 大叔，你那把是木頭。
PANEL 2 (middle): the DEMON KING CAT lifts one huge paw and a gigantic semi-transparent glowing
scroll unrolls from his claw tip, its surface ruled with empty rows.
  DEMON BALLOON from the DEMON KING CAT: 想要魔力？先過我的審核。
PANEL 3 (bottom): all four cats freeze with identical flat unimpressed expressions; above each
cat's head floats a small round glowing memory bubble showing their former human self - a woman
engineer with glasses, a young man with a headband, a heavyset middle-aged man with a gold chain,
and a cool young man holding a coffee cup. No text inside those memory bubbles.
  One wide THOUGHT BALLOON shared by all four cats: ……這不就是 code review。
```

---

## 05 規則是寫出來的

參考圖：`images/ep1/07.webp`（畫風）＋ `story/refs/` 的四位主角

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| 上 | 小鳥不啾臉部大特寫，兩片鏡片映滿紅色符文，瞳孔縮成針尖 | 小鳥不啾「等一下。這些符文我讀得懂。」 | 雲朵思考框 |
| 中 | 她用貓爪在空中畫出金色符文（抽象符號，不是字），杖上寶石重新亮起 | 小鳥不啾「規則是寫出來的——那就能改。」 | 橢圓框 |
| 下 | 魔法陣由紅轉金，四貓魔力回流全身發光：真刀、爪光、全隱形、火球 | 小白++「魔力回來了！」 | 爆炸框 |
| 下 | | 中年攻城屍「刀也回來了。」 | 橢圓框 |

用意：全話的轉折點，只用一張臉演。上格是思考框（她還沒說出口），中格說出口才變橢圓框——**框型變化本身就是「想到了→講出來」**。空中的符文不能是任何看得懂的文字。下格是降級三連發的回收，爆炸框回來了。

```
PANEL 1 (top): extreme close-up on the MAGE CAT's face; the crimson runes of the magic circle are
mirrored across both lenses of her round glasses, her pupils contract to pinpricks - the moment she
understands.
  THOUGHT BALLOON from the MAGE CAT: 等一下。這些符文我讀得懂。
PANEL 2 (middle): she draws a glowing golden sigil in mid-air with one cat paw - abstract magical
symbols only, never real letters; the blue orb on her staff blazes back to life.
  OVAL BALLOON from the MAGE CAT: 規則是寫出來的——那就能改。
PANEL 3 (bottom): the crimson magic circle turns brilliant gold; magic power floods back into all
four cats and they glow all over - real steel katana, blazing claws, full invisibility shimmer, a
roaring fireball. Triumphant heroic group shot.
  SHOUT BALLOON from the SWORDSMAN CAT: 魔力回來了！
  OVAL BALLOON from the SAMURAI CAT: 刀也回來了。
```

---

## 06 通行證，與那座黑塔

參考圖：`images/ep1/07.webp`（畫風）＋ `story/refs/` 的荒坂小次郎與四位主角

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| 上 | 魔王仰頭大笑，紅眼瞇起，是欣賞不是憤怒 | 魔王「有意思。」 | 魔王框 |
| 中 | 他扯下胸前紅色紋章拋下，小白++雙爪接住，愣愣看著 | 魔王「你們是第一組看懂規則的。這個拿去。」 | 魔王框 |
| 中 | | 小白++「這是……通行證？」 | 抖框 |
| 下 | 四貓回頭望向遠方，更高的黑塔頂端亮起另一個更大、冷藍白色的魔法陣 | 里歐「那座塔上的光……不是紅色的。」 | 抖框 |
| 下 | | 「第二話 完　未完待續……」 | 直角旁白框 |

用意：把魔王從反派翻成管理員。紋章＝通行證，是第三話的道具。結尾冷色對紅色，暗示那座塔不是小次郎點的。最後那個直角框是全頁唯一的直角，用來收尾。

```
PANEL 1 (top): the DEMON KING CAT throws his head back laughing - not angry, genuinely delighted,
red eyes narrowed with approval.
  DEMON BALLOON from the DEMON KING CAT: 有意思。
PANEL 2 (middle): he tears THE PASS off his chest and tosses it down - the round black
medallion with a thin red rim and a flat red three-balled emblem; the SWORDSMAN CAT catches it with both paws, staring at it in awe.
  DEMON BALLOON from the DEMON KING CAT: 你們是第一組看懂規則的。這個拿去。
  TREMBLE BALLOON from the SWORDSMAN CAT: 這是……通行證？
PANEL 3 (bottom): the four cats turn and look into the distance where, atop a far taller black
tower, a second much larger magic circle ignites in cold blue-white light. Ominous closing shot,
dramatic sky.
  TREMBLE BALLOON from the ROGUE CAT: 那座塔上的光……不是紅色的。
  CAPTION BOX in the bottom-right corner: 第二話 完　未完待續……
```

---

## 荒坂小次郎的角色卡

`images/char-kojiro.webp`。他沒有前世側——來歷留到後面再說，所以卡面只有貓世界那半邊，跟其他四位的左右對照不同。這是刻意的。卡面不放任何文字。

```
A single full-body character card portrait, NOT a multi-panel page, and with NO text of any kind
anywhere in the image. The DEMON KING CAT alone: enormous dark chocolate-brown long-haired cat
standing in three-quarter view, glowing red eyes, black-and-crimson cape, heavy gold chain across
the chest, and on it a round medallion crest with a gold rim, a black face and a flat red
three-balled emblem, claws out, a slow confident grin. Behind him a
swirling crimson magic circle and a dark castle among floating islands. Same painterly vibrant
anime fantasy style as the reference. Portrait aspect ratio 2:3.
```
