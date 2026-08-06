# 第六話：魔王的 PR 審查！

先讀 [`story/README.md`](README.md) 的鐵律與框型表再動手。這一話由 pipeline 產出,對白與框型跟生圖 prompt 是同一份。

## 這一話在講什麼

四貓興高采烈提交 Pull Request，沒想到直接觸發荒坂小次郎的 CI/CD 自動審查，陷入嚴苛的 CI pipeline 與魔王親自 Code Review 的烏龍危機。

三個轉折：

1. 四貓信心滿滿發起 Pull Request，結果被 CI pipeline 自動退件
2. 修正格式問題後，竟觸發荒坂小次郎的即時監控與魔王影像 Code Review
3. 魔王當面抓出一堆低級 Bug，四貓才發現是小白++輸入了錯字，最後慘遭 Merge Blocked


---

## 01

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | SWORDSMAN CAT proudly hits a huge floating glowing green 'Submit Pull Request' holographic button with his paw in front of the tower server core. | 小白++「按下 Submit！Pull Request 送出去啦！」 | SHOUT |
|  |  | 中年攻城屍「幹得好！這下 Core Bug 就修復完成了吧！」 | SHOUT |
| mid | MAGE CAT adjusts her gold-rimmed glasses while looking at the floating console screen, staff in hand, as small yellow warning text appears on screen. | 小鳥不啾「等一下，系統進入 CI/CD 自動測試流程了。」 | OVAL |
|  |  | 里歐「免驚啦，我們剛才寫得超完美的好嗎。」 | OVAL |
| bottom | The screen flashes bright red with huge warning text 'BUILD FAILED: IndentationError: unexpected indent'. All four cats freeze in shock. | 小白++「蛤？！Build 失敗？！」 | TREMBLE |
|  |  | 小鳥不啾「誰在 Python 程式碼裡面混用了 Tab 和空格……」 | WEAK |

參考圖：style、balloons、tower、xiaobai、xiaoniao、uncle、leo

```
PANEL 1 (top): SWORDSMAN CAT proudly hits a huge floating glowing green 'Submit Pull Request' holographic button with his paw in front of the tower server core.
  SHOUT BALLOON from xiaobai: 按下 Submit！Pull Request 送出去啦！
  SHOUT BALLOON from uncle: 幹得好！這下 Core Bug 就修復完成了吧！
PANEL 2 (middle): MAGE CAT adjusts her gold-rimmed glasses while looking at the floating console screen, staff in hand, as small yellow warning text appears on screen.
  OVAL BALLOON from xiaoniao: 等一下，系統進入 CI/CD 自動測試流程了。
  OVAL BALLOON from leo: 免驚啦，我們剛才寫得超完美的好嗎。
PANEL 3 (bottom): The screen flashes bright red with huge warning text 'BUILD FAILED: IndentationError: unexpected indent'. All four cats freeze in shock.
  TREMBLE BALLOON from xiaobai: 蛤？！Build 失敗？！
  WEAK BALLOON from xiaoniao: 誰在 Python 程式碼裡面混用了 Tab 和空格……
```

---

## 02

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | ROGUE CAT frantically uses both front paws to type on a holographic keyboard, sweating with a worried expression. | 里歐「快快快！自動排版套用 autopep8！重新排版！」 | SHOUT |
|  |  | 中年攻城屍「賢弟冷靜啊！千萬不要蓋到老夫的 commit！」 | TREMBLE |
| mid | SWORDSMAN CAT uses his paw to hit the force push button, grinning confidentially. | 小白++「不管了！看我直接 git push --force！」 | SHOUT |
|  |  | 小鳥不啾「小白住手！正式環境不能 Force Push——」 | SHOUT |
| bottom | A huge alarm chime sounds, and a loud siren banner flashes 'Reviewer Assigned: Arasaka Kojiro'. SAMURAI CAT holds his head in horror. | 中年攻城屍「完了……強制推送觸發魔王的即時通報了！」 | TREMBLE |
|  |  | 里歐「這下直接送到老闆的 Slack 通知了啦……」 | WEAK |

參考圖：style、balloons、tower、xiaobai、xiaoniao、uncle、leo

```
PANEL 1 (top): ROGUE CAT frantically uses both front paws to type on a holographic keyboard, sweating with a worried expression.
  SHOUT BALLOON from leo: 快快快！自動排版套用 autopep8！重新排版！
  TREMBLE BALLOON from uncle: 賢弟冷靜啊！千萬不要蓋到老夫的 commit！
PANEL 2 (middle): SWORDSMAN CAT uses his paw to hit the force push button, grinning confidentially.
  SHOUT BALLOON from xiaobai: 不管了！看我直接 git push --force！
  SHOUT BALLOON from xiaoniao: 小白住手！正式環境不能 Force Push——
PANEL 3 (bottom): A huge alarm chime sounds, and a loud siren banner flashes 'Reviewer Assigned: Arasaka Kojiro'. SAMURAI CAT holds his head in horror.
  TREMBLE BALLOON from uncle: 完了……強制推送觸發魔王的即時通報了！
  WEAK BALLOON from leo: 這下直接送到老闆的 Slack 通知了啦……
```

---

## 03

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | A dark holographic projection of DEMON CAT KOJIRO with glowing red eyes appears above the central column, looking down with extreme pressure. | 荒坂小次郎「是誰在半夜三點對主幹分支 Force Push？」 | DEMON |
|  |  | 小白++「對不起小次郎哥！我們是來幫你修 Bug 的！」 | TREMBLE |
| mid | Close-up of KOJIRO holographic face pointing his paw with sharp claws toward a specific line of floating red code. | 荒坂小次郎「修 Bug？你們看這行寫了什麼。」 | DEMON |
|  |  | 中年攻城屍「嗯？這不是老夫精心設計的演算法嗎？」 | OVAL |
| bottom | Close-up on the screen showing code 'while (true) { sleep(1); } // 暫時解決 CPU 過熱'. SAMURAI CAT drops his katana with a flat face. | 荒坂小次郎「無窮迴圈配 sleep？這叫修 Bug 還是寫 Bug？」 | DEMON |
|  |  | 中年攻城屍「老夫……老夫當時只是想讓系統喘一口氣……」 | WEAK |

參考圖：style、balloons、tower、kojiro、xiaobai、xiaoniao、uncle、leo

```
PANEL 1 (top): A dark holographic projection of DEMON CAT KOJIRO with glowing red eyes appears above the central column, looking down with extreme pressure.
  DEMON BALLOON from kojiro: 是誰在半夜三點對主幹分支 Force Push？
  TREMBLE BALLOON from xiaobai: 對不起小次郎哥！我們是來幫你修 Bug 的！
PANEL 2 (middle): Close-up of KOJIRO holographic face pointing his paw with sharp claws toward a specific line of floating red code.
  DEMON BALLOON from kojiro: 修 Bug？你們看這行寫了什麼。
  OVAL BALLOON from uncle: 嗯？這不是老夫精心設計的演算法嗎？
PANEL 3 (bottom): Close-up on the screen showing code 'while (true) { sleep(1); } // 暫時解決 CPU 過熱'. SAMURAI CAT drops his katana with a flat face.
  DEMON BALLOON from kojiro: 無窮迴圈配 sleep？這叫修 Bug 還是寫 Bug？
  WEAK BALLOON from uncle: 老夫……老夫當時只是想讓系統喘一口氣……
```

---

## 04

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | MAGE CAT adjusts her glasses and points her hand at another file on the floating terminal. | 小鳥不啾「報告老闆，至少我的記憶體優化 Module 是沒問題的。」 | OVAL |
|  |  | 荒坂小次郎「是嗎？那你看看小白幫你改的變數名稱。」 | DEMON |
| mid | The screen shows a variable named 'temp_final_v2_FINAL_real_last'. MAGE CAT facepalms with her paw. | 小白++「這樣寫比較好懂啊……比較有臨場感。」 | WEAK |
|  |  | 小鳥不啾「小白，回去重修命名規範手冊十遍。」 | WEAK |
| bottom | ROGUE CAT carefully sneaks behind the console trying to unplug the alarm cable with his paw, sweating nervously. | 里歐「（偷偷拔掉網路線應該就不會被檢討了吧……）」 | OVAL |
|  |  | 荒坂小次郎「里歐，你的手在摸哪裡？」 | DEMON |

參考圖：style、balloons、tower、kojiro、xiaobai、xiaoniao、uncle、leo

```
PANEL 1 (top): MAGE CAT adjusts her glasses and points her hand at another file on the floating terminal.
  OVAL BALLOON from xiaoniao: 報告老闆，至少我的記憶體優化 Module 是沒問題的。
  DEMON BALLOON from kojiro: 是嗎？那你看看小白幫你改的變數名稱。
PANEL 2 (middle): The screen shows a variable named 'temp_final_v2_FINAL_real_last'. MAGE CAT facepalms with her paw.
  WEAK BALLOON from xiaobai: 這樣寫比較好懂啊……比較有臨場感。
  WEAK BALLOON from xiaoniao: 小白，回去重修命名規範手冊十遍。
PANEL 3 (bottom): ROGUE CAT carefully sneaks behind the console trying to unplug the alarm cable with his paw, sweating nervously.
  OVAL BALLOON from leo: （偷偷拔掉網路線應該就不會被檢討了吧……）
  DEMON BALLOON from kojiro: 里歐，你的手在摸哪裡？
```

---

## 05

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | KOJIRO holographic projection crosses his arms, hovering high over the four depressed cats sitting on the floor. | 荒坂小次郎「12 個 Commit、0 個 Unit Test、硬編碼密碼還沒拔。」 | DEMON |
|  |  | 小白++「我們只是想趕快上線嘛……」 | WEAK |
| mid | MAGE CAT pushes her glasses thoughtfully; above her head floats a small round memory bubble of her former human self staring at a code review rejection email. | 小鳥不啾「這嚴苛的審查標準……跟前世的小次郎哥一模一樣。」 | THOUGHT |
|  |  | 中年攻城屍「不愧是魔王，連 Code Review 都帶有殺氣。」 | OVAL |
| bottom | Close-up of KOJIRO paw hitting a massive glowing red stamp onto the holographic PR page, text reading 'REQUEST CHANGES'. | 荒坂小次郎「PR 退回！把測試補齊、Lint 跑過再來！」 | DEMON |
|  |  | 小白++「被退件啦——！！」 | SHOUT |

參考圖：style、tower、kojiro、xiaobai、xiaoniao、uncle、leo、past

```
PANEL 1 (top): KOJIRO holographic projection crosses his arms, hovering high over the four depressed cats sitting on the floor.
  DEMON BALLOON from kojiro: 12 個 Commit、0 個 Unit Test、硬編碼密碼還沒拔。
  WEAK BALLOON from xiaobai: 我們只是想趕快上線嘛……
PANEL 2 (middle): MAGE CAT pushes her glasses thoughtfully; above her head floats a small round memory bubble of her former human self staring at a code review rejection email.
  THOUGHT BALLOON from xiaoniao: 這嚴苛的審查標準……跟前世的小次郎哥一模一樣。
  OVAL BALLOON from uncle: 不愧是魔王，連 Code Review 都帶有殺氣。
PANEL 3 (bottom): Close-up of KOJIRO paw hitting a massive glowing red stamp onto the holographic PR page, text reading 'REQUEST CHANGES'.
  DEMON BALLOON from kojiro: PR 退回！把測試補齊、Lint 跑過再來！
  SHOUT BALLOON from xiaobai: 被退件啦——！！
```

---

## 06

| 格 | 畫面 | 對白 | 框型 |
|---|---|---|---|
| top | The holographic projection disappears, leaving the four cats exhausted in the dimly lit server room with glowing blue consoles. | 里歐「結果修一個 Bug，被列出二十個 Request Changes……」 | WEAK |
|  |  | 中年攻城屍「老夫的自信心被打擊得體無完膚……」 | WEAK |
| mid | MAGE CAT uses her staff to point at a small green note at the bottom of the review comments, smiling slightly. | 小鳥不啾「等一下，魔王在評語最下面留了一行字。」 | OVAL |
|  |  | 小白++「『架構方向對了，辛苦了。修正完請我吃罐頭』？」 | OVAL |
| bottom | SWORDSMAN CAT raises his front paw enthusiastically while ROGUE CAT and SAMURAI CAT roll up their sleeves ready to type again. | 小白++「好！修重構啦！今晚加班把 PR 改到過！」 | SHOUT |
|  |  | 小白++「第六話 完 未完待續……」 | CAPTION |

參考圖：style、balloons、tower、xiaobai、xiaoniao、uncle、leo

```
PANEL 1 (top): The holographic projection disappears, leaving the four cats exhausted in the dimly lit server room with glowing blue consoles.
  WEAK BALLOON from leo: 結果修一個 Bug，被列出二十個 Request Changes……
  WEAK BALLOON from uncle: 老夫的自信心被打擊得體無完膚……
PANEL 2 (middle): MAGE CAT uses her staff to point at a small green note at the bottom of the review comments, smiling slightly.
  OVAL BALLOON from xiaoniao: 等一下，魔王在評語最下面留了一行字。
  OVAL BALLOON from xiaobai: 『架構方向對了，辛苦了。修正完請我吃罐頭』？
PANEL 3 (bottom): SWORDSMAN CAT raises his front paw enthusiastically while ROGUE CAT and SAMURAI CAT roll up their sleeves ready to type again.
  SHOUT BALLOON from xiaobai: 好！修重構啦！今晚加班把 PR 改到過！
  CAPTION BOX from xiaobai: 第六話 完 未完待續……
```
