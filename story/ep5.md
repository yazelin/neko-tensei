# 第五話：魔王的備份資料庫

先讀 [`story/README.md`](README.md) 的鐵律與框型表再動手。這一話由 pipeline 產出,對白與框型跟生圖 prompt 是同一份。

## 這一話在講什麼

四貓深入荒坂小次郎的私有機房，竟在備份硬碟中發現自己前世被留存的程式碼與黑歷史。

三個轉折：

1. 在私有機房發現儲存四人前世紀錄的古老硬碟陣列
2. 小白++誤觸過載復原機制，差點格式化備份區
3. 發現小次郎留下這座塔真正的目的與未完成的 Patch


---

## 01

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | The four cats stand inside the massive server vault facing a giant shining blue storage array rack filled with thousands of glowing crystal drive bays. | 小白++「哇！這整面牆都是硬碟陣列！」 | SHOUT |
|  |  | 中年攻城屍「小心點，這裡每一顆感覺都有幾 TB。」 | OVAL |
| mid | Close-up of MAGE CAT inspecting the glowing label on one crystal drive bay; text reads 'Project: Earth Engineers Backup'. | 小鳥不啾「標籤上寫著……『轉生工程師專案備份』。」 | OVAL |
|  |  | 里歐「等等，該不會我們的前世資料都在裡面？！」 | TREMBLE |
| bottom | SAMURAI CAT crosses his arms with a stern proud face while ROGUE CAT sweatdrops beside him. | 中年攻城屍「哼，老夫當年寫的完美 Architecture 也在裡面吧。」 | OVAL |
|  |  | 里歐「大叔你上個星期才把正式環境的資料庫炸掉掉吧……」 | WEAK |

參考圖：style、balloons、tower、xiaobai、uncle、xiaoniao、leo

```
PANEL 1 (top): The four cats stand inside the massive server vault facing a giant shining blue storage array rack filled with thousands of glowing crystal drive bays.
  SHOUT BALLOON from xiaobai: 哇！這整面牆都是硬碟陣列！
  OVAL BALLOON from uncle: 小心點，這裡每一顆感覺都有幾 TB。
PANEL 2 (middle): Close-up of MAGE CAT inspecting the glowing label on one crystal drive bay; text reads 'Project: Earth Engineers Backup'.
  OVAL BALLOON from xiaoniao: 標籤上寫著……『轉生工程師專案備份』。
  TREMBLE BALLOON from leo: 等等，該不會我們的前世資料都在裡面？！
PANEL 3 (bottom): SAMURAI CAT crosses his arms with a stern proud face while ROGUE CAT sweatdrops beside him.
  OVAL BALLOON from uncle: 哼，老夫當年寫的完美 Architecture 也在裡面吧。
  WEAK BALLOON from leo: 大叔你上個星期才把正式環境的資料庫炸掉掉吧……
```

---

## 02

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | SWORDSMAN CAT reaches his paw out curiosity and pulls out a glowing blue crystal drive from the rack. | 小白++「不管了！抽一顆出來看看裡面寫啥！」 | SHOUT |
|  |  | 小鳥不啾「小白！不要在運行中熱插拔——」 | TREMBLE |
| mid | A large red holographic warning light flashes above the drive bay with error message 'RAID Array Degraded! Emergency Restore Triggered!'. | 里歐「警報響了！RAID 陣列崩潰啦！」 | TREMBLE |
|  |  | 中年攻城屍「蠢材！就叫你不要亂抽！」 | SHOUT |
| bottom | SWORDSMAN CAT desperately tries to push the crystal drive back into the socket with both paws, sweating profusely. | 小白++「對不起！我現在插回去！給個機會！」 | WEAK |
|  |  | 小鳥不啾「進度條開始倒數了，十秒後強制清空……」 | WEAK |

參考圖：style、balloons、tower、xiaobai、uncle、xiaoniao、leo

```
PANEL 1 (top): SWORDSMAN CAT reaches his paw out curiosity and pulls out a glowing blue crystal drive from the rack.
  SHOUT BALLOON from xiaobai: 不管了！抽一顆出來看看裡面寫啥！
  TREMBLE BALLOON from xiaoniao: 小白！不要在運行中熱插拔——
PANEL 2 (middle): A large red holographic warning light flashes above the drive bay with error message 'RAID Array Degraded! Emergency Restore Triggered!'.
  TREMBLE BALLOON from leo: 警報響了！RAID 陣列崩潰啦！
  SHOUT BALLOON from uncle: 蠢材！就叫你不要亂抽！
PANEL 3 (bottom): SWORDSMAN CAT desperately tries to push the crystal drive back into the socket with both paws, sweating profusely.
  WEAK BALLOON from xiaobai: 對不起！我現在插回去！給個機會！
  WEAK BALLOON from xiaoniao: 進度條開始倒數了，十秒後強制清空……
```

---

## 03

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | ROGUE CAT quickly pulls out a glowing silver bypass key with his hand and inserts it into a slot under the rack terminal. | 里歐「讓開！插入備份強制卡鎖！」 | SHOUT |
|  |  | 中年攻城屍「來得及嗎？！」 | TREMBLE |
| mid | The red alarm lights instantly turn into mild yellow; a green message bar shows 'Rebuilding RAID... 0.1%'. | 里歐「呼……還好有留硬體寫保護開關。」 | OVAL |
|  |  | 小白++「差點把我們自己的備份檔給格式化了……」 | WEAK |
| bottom | SAMURAI CAT wipes sweat from his forehead with his paw, taking a deep breath. | 中年攻城屍「老夫剛才心臟差點停止跳動……」 | OVAL |
|  |  | 小鳥不啾「大家看螢幕，陣列修復時彈出了舊檔歷史紀錄。」 | OVAL |

參考圖：style、balloons、tower、xiaobai、uncle、xiaoniao、leo

```
PANEL 1 (top): ROGUE CAT quickly pulls out a glowing silver bypass key with his hand and inserts it into a slot under the rack terminal.
  SHOUT BALLOON from leo: 讓開！插入備份強制卡鎖！
  TREMBLE BALLOON from uncle: 來得及嗎？！
PANEL 2 (middle): The red alarm lights instantly turn into mild yellow; a green message bar shows 'Rebuilding RAID... 0.1%'.
  OVAL BALLOON from leo: 呼……還好有留硬體寫保護開關。
  WEAK BALLOON from xiaobai: 差點把我們自己的備份檔給格式化了……
PANEL 3 (bottom): SAMURAI CAT wipes sweat from his forehead with his paw, taking a deep breath.
  OVAL BALLOON from uncle: 老夫剛才心臟差點停止跳動……
  OVAL BALLOON from xiaoniao: 大家看螢幕，陣列修復時彈出了舊檔歷史紀錄。
```

---

## 04

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | The floating cyan screen displays a video log of former human male engineer Kojiro typing tiredly at night in an office. | 小白++「這是……小次郎前世的影像紀錄？」 | OVAL |
|  |  | 里歐「看起來也是個每天加班到深夜的苦命工程師。」 | OVAL |
| mid | Close-up on the video terminal log displaying text code comments 'TODO: Build a cat world for my burnt-out teammates.' | 小鳥不啾「註解寫著……『為過勞的夥伴們建立一個貓貓世界』。」 | WEAK |
|  |  | 中年攻城屍「什麼？！這座塔跟這個世界……是他特地建的？！」 | TREMBLE |
| bottom | MAGE CAT pushes her glasses with a solemn expression; above her head floats a small round memory bubble of her former human female engineer self looking touched. | 小鳥不啾「原本以為他只是嚴厲的老闆，沒想到他暗中留了退路給我們。」 | THOUGHT |
|  |  | 小白++「小次郎哥……原來一直把我們當兄弟……」 | WEAK |

參考圖：style、balloons、tower、xiaobai、uncle、xiaoniao、leo、past

```
PANEL 1 (top): The floating cyan screen displays a video log of former human male engineer Kojiro typing tiredly at night in an office.
  OVAL BALLOON from xiaobai: 這是……小次郎前世的影像紀錄？
  OVAL BALLOON from leo: 看起來也是個每天加班到深夜的苦命工程師。
PANEL 2 (middle): Close-up on the video terminal log displaying text code comments 'TODO: Build a cat world for my burnt-out teammates.'
  WEAK BALLOON from xiaoniao: 註解寫著……『為過勞的夥伴們建立一個貓貓世界』。
  TREMBLE BALLOON from uncle: 什麼？！這座塔跟這個世界……是他特地建的？！
PANEL 3 (bottom): MAGE CAT pushes her glasses with a solemn expression; above her head floats a small round memory bubble of her former human female engineer self looking touched.
  THOUGHT BALLOON from xiaoniao: 原本以為他只是嚴厲的老闆，沒想到他暗中留了退路給我們。
  WEAK BALLOON from xiaobai: 小次郎哥……原來一直把我們當兄弟……
```

---

## 05

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | ROGUE CAT points his cat paw at a flashing red line of code at the bottom of the video log. | 里歐「但是等一下！最後一行寫著『Unresolved Critical Bug』！」 | SHOUT |
|  |  | 中年攻城屍「什麼？！連魔王都解不掉的致命 Bug？！」 | SHOUT |
| mid | Close-up of the screen displaying red glowing warning text 'Error: Memory Overflow in Cat Transformation Protocol'. | 小鳥不啾「這是『貓化協定記憶體溢位』……難怪我們有時候會忘記前世的事情。」 | OVAL |
|  |  | 小白++「如果 Bug 沒修好會怎樣？」 | TREMBLE |
| bottom | The whole server room lightly vibrates as a hollow mechanical voice echoes through ambient speakers. | 小鳥不啾「會被系統當成垃圾回收，徹底變回普通的貓……」 | WEAK |
|  |  | 中年攻城屍「絕不能讓這種事發生！」 | SHOUT |

參考圖：style、balloons、tower、xiaobai、uncle、xiaoniao、leo

```
PANEL 1 (top): ROGUE CAT points his cat paw at a flashing red line of code at the bottom of the video log.
  SHOUT BALLOON from leo: 但是等一下！最後一行寫著『Unresolved Critical Bug』！
  SHOUT BALLOON from uncle: 什麼？！連魔王都解不掉的致命 Bug？！
PANEL 2 (middle): Close-up of the screen displaying red glowing warning text 'Error: Memory Overflow in Cat Transformation Protocol'.
  OVAL BALLOON from xiaoniao: 這是『貓化協定記憶體溢位』……難怪我們有時候會忘記前世的事情。
  TREMBLE BALLOON from xiaobai: 如果 Bug 沒修好會怎樣？
PANEL 3 (bottom): The whole server room lightly vibrates as a hollow mechanical voice echoes through ambient speakers.
  WEAK BALLOON from xiaoniao: 會被系統當成垃圾回收，徹底變回普通的貓……
  SHOUT BALLOON from uncle: 絕不能讓這種事發生！
```

---

## 06

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | SWORDSMAN CAT raises his front paw high with determined eyes, tiger fang gleaming. | 小白++「這次換我們來幫小次郎哥完成這個 Patch！」 | SHOUT |
|  |  | 里歐「沒錯！我們可是專業的 Debug 團隊！」 | SHOUT |
| mid | SAMURAI CAT holds his katana high while MAGE CAT readies her blue gem staff beside him. | 中年攻城屍「老夫的鋼刀，這次要砍向系統的 Core Bug！」 | SHOUT |
|  |  | 小鳥不啾「準備開始對主伺服器發起 Pull Request。」 | OVAL |
| bottom | Wide hero shot of the four cats standing firmly side by side before the giant glowing blue core tower pedestal, four determined cat shadows cast long. | 小白++「修 Bug 小隊，正式出擊！」 | SHOUT |
|  |  | 小白++「第五話 完 未完待續……」 | CAPTION |

參考圖：style、balloons、tower、xiaobai、uncle、xiaoniao、leo

```
PANEL 1 (top): SWORDSMAN CAT raises his front paw high with determined eyes, tiger fang gleaming.
  SHOUT BALLOON from xiaobai: 這次換我們來幫小次郎哥完成這個 Patch！
  SHOUT BALLOON from leo: 沒錯！我們可是專業的 Debug 團隊！
PANEL 2 (middle): SAMURAI CAT holds his katana high while MAGE CAT readies her blue gem staff beside him.
  SHOUT BALLOON from uncle: 老夫的鋼刀，這次要砍向系統的 Core Bug！
  OVAL BALLOON from xiaoniao: 準備開始對主伺服器發起 Pull Request。
PANEL 3 (bottom): Wide hero shot of the four cats standing firmly side by side before the giant glowing blue core tower pedestal, four determined cat shadows cast long.
  SHOUT BALLOON from xiaobai: 修 Bug 小隊，正式出擊！
  CAPTION BOX from xiaobai: 第五話 完 未完待續……
```
