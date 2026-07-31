#!/usr/bin/env python3
"""pipeline 的單元測試。只驗純邏輯,不打任何外部服務。

跑法: python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""
import io
import json
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import prompt
import next_episode as ne


class TestCanon(unittest.TestCase):
    def test_下一話話數接在最後一話之後(self):
        c = ne.load_canon()
        self.assertEqual(c['next_n'], c['episodes'][-1]['n'] + 1)

    def test_帶進創作規範全文(self):
        c = ne.load_canon()
        self.assertIn('對話框的形狀跟著劇情走', c['rules'])
        self.assertIn('必勝', c['rules'])

    def test_帶進最近兩話的分鏡(self):
        c = ne.load_canon()
        # 兩話各斷言一個只出現在自己檔案裡的字串。不要兩個都選 ep2 的——
        # 那樣把 eps[-2:] 改成 eps[-1:] 測試照樣會過,測不到「兩話」。
        self.assertIn('史萊姆登場過場頁', c['recent'])   # 只在 ep1.md
        self.assertIn('魔力不足', c['recent'])           # 只在 ep2.md

    def test_話數不重複(self):
        c = ne.load_canon()
        ns = [e['n'] for e in c['episodes']]
        self.assertEqual(len(ns), len(set(ns)))


class TestPrompt(unittest.TestCase):
    def test_參考圖鍵值齊全(self):
        for k in ['style', 'xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro', 'past']:
            self.assertIn(k, prompt.REF, k)

    def test_參考圖檔案真的存在(self):
        root = pathlib.Path(__file__).parent.parent
        for k, (rel, _desc) in prompt.REF.items():
            self.assertTrue((root / rel).is_file(), f'{k} 指到不存在的檔案: {rel}')

    def test_內頁帶框型與對白規則(self):
        p = prompt.build_prompt('01', ['style', 'xiaobai'], 'PANEL 1: ...')
        self.assertIn('BALLOON SHAPES', p)
        self.assertIn('TRADITIONAL CHINESE', p)
        self.assertIn('FINAL CHECK', p)

    def test_角色卡不帶框型與對白規則(self):
        p = prompt.build_prompt('kojiro', ['kojiro'], 'A single portrait')
        self.assertNotIn('BALLOON SHAPES', p)
        self.assertNotIn('FINAL CHECK', p)

    def test_封面也不帶框型與對白規則(self):
        p = prompt.build_prompt('cover', ['style', 'xiaoniao'], 'A cover')
        self.assertNotIn('BALLOON SHAPES', p)
        self.assertNotIn('FINAL CHECK', p)

    def test_參考圖清單會逐張標明是誰(self):
        p = prompt.build_prompt('03', ['style', 'kojiro'], 'x')
        self.assertIn('- image 1: ', p)
        self.assertIn('- image 2: ', p)

    def test_出場前世時才帶前世設定(self):
        with_past = prompt.build_prompt('04', ['style', 'past'], 'x')
        without = prompt.build_prompt('04', ['style', 'uncle'], 'x')
        # 斷言用只出現在 PAST 常數裡的句子。不要用 'FORMER HUMAN SELVES'——
        # REF['past'] 的說明文字本身就含那個字串,會讓這條測試變成假陽性。
        self.assertIn('THE PAST IS ALWAYS BLACK AND WHITE', with_past)
        self.assertNotIn('THE PAST IS ALWAYS BLACK AND WHITE', without)

    def test_七種框型都在(self):
        self.assertEqual(prompt.SHAPES, {
            'SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON', 'CAPTION'})


class TestWishes(unittest.TestCase):
    def test_挑出留言文字(self):
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [
                 {'body': '想看小白++單挑魔王'},
                 {'body': '希望里歐的隱形術再出包一次'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload),
                         ['想看小白++單挑魔王', '希望里歐的隱形術再出包一次'])

    def test_只收許願那一串不收每話討論(self):
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '/neko-tensei/ep2.html', 'category': {'name': 'General'},
             'comments': {'nodes': [{'body': '這話好笑'}]}},
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [{'body': '想看貓咪泡溫泉'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload), ['想看貓咪泡溫泉'])

    def test_分類與標題兩個條件都要符合(self):
        # brief 給的「只收許願那一串不收每話討論」測試裡,不合格的那個節點
        # 標題跟分類同時錯,拿掉其中任一過濾條件測試照樣會過。這裡把兩個
        # 條件拆開各錯一個,才能各自驗到。
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '劇情許願', 'category': {'name': 'General'},
             'comments': {'nodes': [{'body': '分類錯不該出現'}]}},
            {'title': '其他討論串', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [{'body': '標題錯不該出現'}]}},
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [{'body': '兩個都對才該出現'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload), ['兩個都對才該出現'])

    def test_還沒有人許願時回空清單(self):
        self.assertEqual(
            ne.parse_wishes({'data': {'repository': {'discussions': {'nodes': []}}}}), [])

    def test_回應格式不對也不炸(self):
        self.assertEqual(ne.parse_wishes({}), [])
        self.assertEqual(ne.parse_wishes({'data': None}), [])

    def test_空白留言被濾掉(self):
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [{'body': '  '}, {'body': '有效的許願'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload), ['有效的許願'])

    @patch('next_episode.subprocess.run')
    def test_gh失敗時回傳失敗原因不是None(self, mock_run):
        # gh 沒認證 / API 壞了,是真的該讓人知道的失敗,不能跟「沒人許願」
        # 混在一起變成同一種「回空清單」。
        mock_run.return_value = subprocess.CompletedProcess(
            args=['gh'], returncode=1, stdout='', stderr='gh: authentication required')
        wishes, err = ne.fetch_wishes()
        self.assertEqual(wishes, [])
        self.assertIsNotNone(err)
        self.assertIn('authentication required', err)

    @patch('next_episode.subprocess.run')
    def test_gh成功但沒人許願時第二個值是None(self, mock_run):
        # 「正常空」跟「失敗」的分界:成功打到 API、只是還沒人留言,
        # 第二個值一定要是 None,呼叫端才不會誤判成錯誤。
        payload = json.dumps({'data': {'repository': {'discussions': {'nodes': []}}}})
        mock_run.return_value = subprocess.CompletedProcess(
            args=['gh'], returncode=0, stdout=payload, stderr='')
        wishes, err = ne.fetch_wishes()
        self.assertEqual(wishes, [])
        self.assertIsNone(err)

    @patch('next_episode.subprocess.run')
    def test_subprocess丟例外時回傳失敗原因不是None(self, mock_run):
        mock_run.side_effect = FileNotFoundError('gh: command not found')
        wishes, err = ne.fetch_wishes()
        self.assertEqual(wishes, [])
        self.assertIsNotNone(err)


def _good_plan(n=3):
    """一份會通過驗證的最小企劃,測試用它當基準再逐項弄壞。"""
    shapes = ['SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON']
    return {
        'title': '黑塔上的另一個人',
        'desc': '四貓帶著通行證走向黑塔,塔上的魔法陣不是小次郎點的。',
        'beats': ['出發', '塔前受阻', '看見塔頂的人影'],
        'pages': [
            {'n': f'{i:02d}',
             'chars': ['xiaoniao', 'xiaobai'],
             'panels': [
                 {'pos': 'top', 'scene': '四貓走在荒原上',
                  'lines': [{'speaker': 'xiaobai', 'shape': shapes[i - 1],
                             'text': '那座塔越來越近了。'}]},
                 {'pos': 'mid', 'scene': '塔門緊閉',
                  # 用 shapes[i % 6] 而非固定 'OVAL':固定值在 i=2 時會撞上
                  # shapes[i - 1](= shapes[1] = 'OVAL'),讓「好的企劃」在
                  # 第 02 頁自己觸發「框型全部一樣」——基準本身就該是乾淨的。
                  'lines': [{'speaker': 'xiaoniao', 'shape': shapes[i % 6],
                             'text': '門上有符文。'}]},
             ]}
            for i in range(1, 7)
        ],
    }


class TestSimplified(unittest.TestCase):
    def test_抓到簡體字(self):
        self.assertEqual(ne.has_simplified('这个世界的魔力'), '这')
        self.assertEqual(ne.has_simplified('魔力回来了'), '来')

    def test_正體中文放行(self):
        self.assertIsNone(ne.has_simplified('這個世界的魔力，是我在配的。'))
        self.assertIsNone(ne.has_simplified('得加 Token！'))

    def test_容易被誤判的正體字要放行(self):
        # 這幾個字在手打字表的版本裡被誤收成簡體,「那」幾乎每句話都有,
        # 誤判會讓驗證器擋掉絕大多數合法企劃。
        for s in ['那座塔上的光……不是紅色的。', '隱形只隱一半。這比沒隱還慘。',
                  '四隻空瓶子，還敢慶祝。', '巨大的暗棕色長毛貓',
                  '唯一的線索', '反而露出笑', '埋下伏筆', '準備好了']:
            self.assertIsNone(ne.has_simplified(s), s)

    def test_台灣標準異體字要放行(self):
        # code review 抓到的 Critical:STCharacters.txt 收了一批「異體字
        # 正規化」,不是真的簡繁對立——「峰」的候選只有「峯」,照字元候選清單
        # 的規則會誤判成簡體,但「峰」才是台灣教育部標準寫法。全表掃描確認
        # 只有這 7 個字受影響:秘/祕、群/羣、床/牀、峰/峯、痴/癡、灶/竈、
        # 粽/糉。最後一句是這個 repo 自己 index.html/README.md 的既有文案,
        # 「一群貓」對貓漫畫是高機率用詞,這條錯了會擋掉大多數合法企劃。
        for s in ['秘密', '一群貓', '起床', '山峰', '痴心', '灶臺', '粽子',
                  '誕生於 LINE C# 社群閒聊的連載漫畫']:
            self.assertIsNone(ne.has_simplified(s), s)

    def test_TW_EXTRA表裡的字全部放行(self):
        # 逐字鎖住 TW_EXTRA 放行表——目前只有「霉」,查證來源是教育部
        # 《重編國語辭典修訂本》(見 TW_EXTRA 的註解)。連常見詞一起測,不是
        # 只測單字,因為驗證器實際收到的是整句對白。
        for ch in ne.TW_EXTRA:
            self.assertIsNone(ne.has_simplified(ch), ch)
        for s in ['發霉', '倒霉', '霉味', '地下室有一股霉味,誰都不敢進去。']:
            self.assertIsNone(ne.has_simplified(s), s)

    def test_TW_EXTRA不能收真正的簡體字(self):
        # 反向測試:防止 TW_EXTRA 被濫用成第二份手打字表。
        #
        # coordinator 原本要求的做法是「斷言表裡的字不在 STCharacters.txt
        # 的簡體來源欄位裡」——實測發現這條做不到:STCharacters.txt 的簡體
        # 來源欄位(左欄)就是 _simplified_map() 的 key,而 TW_EXTRA 裡的字
        # 「之所以」需要被收進放行表,正是因為它們本來就在那個左欄(例如
        # 「霉」對應到候選「黴」)。這條檢查對任何一個真的需要放進 TW_EXTRA
        # 的字,結構上必定失敗,不是我漏做,是這個檢查跟「為什麼需要
        # TW_EXTRA」互相矛盾——細節與 mutation 證據見 task-4-report.md。
        #
        # 改成兩個真的可以自動驗證、對防濫用有意義的檢查:
        # 1. 候選數必須剛好 1 個。像「发」的候選是【發、髮】兩個完全不同的
        #    繁體字,是「多個繁體字被簡化合併成一個字」的真簡化特徵,結構上
        #    不可能是單純的異體字分工(異體字分工是一對一,如「峰/峯」)。
        #    候選數 >= 2 的字直接排除,防止之後有人手滑把這種字塞進來。
        for ch in ne.TW_EXTRA:
            cands = ne._simplified_map().get(ch, [])
            self.assertEqual(len(cands), 1,
                              f'{ch} 候選數不是 1,像多對一合併的真簡化字,不該進 TW_EXTRA:{cands}')
        # 2. 跟既有回歸測試裡「確定必須繼續被擋」的核心簡體字互斥——這些字
        #    沒有任何 TW/異體字佐證,是 test_抓到簡體字 鎖住的基準。
        core_simplified = {'这', '来', '发', '头', '爱', '门', '为'}
        self.assertEqual(ne.TW_EXTRA.keys() & core_simplified, set(),
                          'TW_EXTRA 收到了確定是簡體字的字')

    def test_既有正體中文資產全部放行(self):
        # 最有價值的一條:拿真實內容當回歸測試,範圍涵蓋整個 repo 的正體
        # 中文資產,不是只掃兩話分鏡——上一輪只掃 story/ep*.md,漏掉了
        # 「一群貓」這種只出現在 index.html/README.md 的假陽性,這條就是
        # 補那個洞。手打字表就是敗在同一個地方:誤收正體字之後,連自己
        # 已經上線的文案都會被判成簡體。
        import pathlib as _p
        root = _p.Path(__file__).parent.parent
        targets = (list(root.glob('story/*.md')) +
                   [root / 'index.html', root / 'README.md',
                    root / 'partials' / 'footer.html'] +
                   list(root.glob('char/*.html')))
        self.assertGreaterEqual(len(targets), 8, f'掃描目標太少,glob 可能沒對到檔案:{targets}')
        for f in sorted(targets):
            bad = ne.has_simplified(f.read_text('utf-8'))
            self.assertIsNone(bad, f'{f.relative_to(root)} 出現「{bad}」')

    def test_空字串與None不炸(self):
        self.assertIsNone(ne.has_simplified(''))
        self.assertIsNone(ne.has_simplified(None))


class TestValidate(unittest.TestCase):
    def test_好的企劃通過(self):
        self.assertEqual(ne.validate_plan(_good_plan(), 3, ['我們怎麼變成貓了？！']), [])

    def test_內頁必須六頁(self):
        p = _good_plan(); p['pages'] = p['pages'][:5]
        errs = ne.validate_plan(p, 3, [])
        # 直接斷言帶頁數的完整訊息,不接受「隨便哪個錯誤裡出現 6」就算過——
        # 拿掉頁數檢查那行邏輯,這條斷言必須跟著失敗才算數。
        self.assertIn('內頁必須六頁,拿到 5 頁', errs)

    def test_缺欄位會被擋(self):
        for field in ['title', 'desc', 'beats', 'pages']:
            p = _good_plan(); del p[field]
            errs = ne.validate_plan(p, 3, [])
            # 驗的是「缺哪個欄位就報哪個欄位」,不是「回傳非空」——
            # 後者就算欄位檢查認錯欄位,測試照樣會過。
            self.assertTrue(any(f'缺欄位:{field}' in e for e in errs),
                             f'缺 {field} 沒有對應的錯誤訊息:{errs}')

    def test_對白含簡體字會被擋(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['text'] = '这个世界的魔力'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('簡體' in e for e in errs), errs)

    def test_框型全部相同會被擋(self):
        p = _good_plan()
        for pg in p['pages']:
            for pn in pg['panels']:
                for ln in pn['lines']:
                    ln['shape'] = 'OVAL'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('框型' in e for e in errs), errs)

    def test_不存在的框型會被擋(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['shape'] = 'ROUNDED'
        self.assertTrue(any('ROUNDED' in e for e in ne.validate_plan(p, 3, [])))

    def test_小次郎不能用內心OS框(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['speaker'] = 'kojiro'
        p['pages'][0]['panels'][0]['lines'][0]['shape'] = 'THOUGHT'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('kojiro' in e and 'THOUGHT' in e for e in errs), errs)

    def test_小次郎用別的框型可以(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['speaker'] = 'kojiro'
        p['pages'][0]['panels'][0]['lines'][0]['shape'] = 'DEMON'
        self.assertEqual(ne.validate_plan(p, 3, []), [])

    def test_標題與既有話數重複會被擋(self):
        p = _good_plan()
        p['title'] = '我們怎麼變成貓了？！'
        errs = ne.validate_plan(p, 3, ['我們怎麼變成貓了？！'])
        self.assertTrue(any('標題' in e for e in errs), errs)

    def test_不認識的角色會被擋(self):
        p = _good_plan()
        p['pages'][0]['chars'] = ['xiaoniao', '路人甲']
        self.assertTrue(any('路人甲' in e for e in ne.validate_plan(p, 3, [])))

    def test_沒有對白的頁面會被擋(self):
        p = _good_plan()
        p['pages'][2]['panels'] = [{'pos': 'top', 'scene': '空景', 'lines': []}]
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('對白' in e for e in errs), errs)

    def test_整頁框型都不合法不會crash(self):
        # code review 抓到的 Important:page_shapes 只收合法框型,整頁都是
        # 不存在的框型時 page_shapes 是空 list,原本的「框型全部一樣」檢查
        # 會拿 page_shapes[0] 去比,直接 IndexError——守門員在最該擋的時候
        # 自己先死掉,而不是回一份錯誤清單。這裡驗證不會丟例外,而是正常
        # 回報「不存在的框型」。
        p = _good_plan()
        for ln in p['pages'][0]['panels'][0]['lines'] + p['pages'][0]['panels'][1]['lines']:
            ln['shape'] = 'ROUND'
        errs = ne.validate_plan(p, 3, [])  # 不該丟例外
        self.assertTrue(any('不存在的框型' in e for e in errs), errs)

    def test_不認得的說話者會被擋(self):
        # 跟 test_不認識的角色會被擋 測的是不同欄位:那條測的是 pg['chars']
        # 名單,這條測的是對白本身的 speaker 沒人認得(chars 名單是對的,
        # 只是某一句對白的 speaker 打錯或幻覺出一個不存在的角色)。
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['speaker'] = '路人乙'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('路人乙' in e for e in errs), errs)

    def test_頁面沒有分格會被擋(self):
        # 跟 test_沒有對白的頁面會被擋 測的是不同情況:那條的 panels 是
        # 非空清單、裡面的 lines 是空的;這條是 panels 本身就是空清單,
        # 要走「沒有分格」那個 continue 分支,不是「一句對白都沒有」那條。
        p = _good_plan()
        p['pages'][2]['panels'] = []
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('沒有分格' in e for e in errs), errs)

    def test_企劃不是物件會被擋(self):
        for bad_plan in [['not', 'a', 'dict'], 'a string', None, 42]:
            self.assertEqual(ne.validate_plan(bad_plan, 3, []), ['企劃不是一個物件'])

    def test_空白對白會被擋(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['text'] = '   '
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('空白對白' in e for e in errs), errs)

    def test_頁碼重複會被擋(self):
        p = _good_plan()
        p['pages'][1]['n'] = p['pages'][0]['n']  # 兩頁都是 01,06 就沒人補
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('頁碼' in e for e in errs), errs)

    def test_標題空白會被擋(self):
        p = _good_plan()
        p['title'] = '   '
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('缺欄位:title' in e for e in errs), errs)


class TestPlannerPrompt(unittest.TestCase):
    def test_prompt_帶進規範與最近分鏡(self):
        canon = ne.load_canon()
        p = ne.build_planner_prompt(canon, [])
        self.assertIn('對話框的形狀跟著劇情走', p)
        self.assertIn('得加 Token', p)

    def test_prompt_要求純JSON(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('JSON', p)

    def test_有許願時會寫進去(self):
        p = ne.build_planner_prompt(ne.load_canon(), ['想看貓咪泡溫泉'])
        self.assertIn('想看貓咪泡溫泉', p)

    def test_沒有許願時明講由AI自己決定(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('由你自己決定要畫什麼', p)

    def test_prompt_列出四種話型(self):
        # 斷言常數本身。不要斷言整份 prompt——_PLAN_SHAPE 的 JSON 範例裡
        # 本來就有 "kind": "推進主線 | 日常番 | 烏龍 | 角色刻畫",
        # 那會讓這條測試在 EPISODE_KINDS 整段被掏空時照樣通過。
        for k in ['推進主線', '日常番', '烏龍', '角色刻畫']:
            self.assertIn(k, ne.EPISODE_KINDS)
        # 也要確認它真的被組進 prompt
        self.assertIn(ne.EPISODE_KINDS, ne.build_planner_prompt(ne.load_canon(), []))

    def test_prompt_明講不必每話推進主線(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('不必每一話都推進主線', p)

    def test_prompt_帶進七種框型(self):
        # 斷言串接後的整串。單獨的 SHOUT/DEMON/CAPTION 在 story/README.md
        # 的框型對照表裡就有,而 rules 一定會被塞進 prompt,那樣測不到東西。
        joined = ' / '.join(sorted(prompt.SHAPES))
        self.assertIn(joined, ne.build_planner_prompt(ne.load_canon(), []))


class TestCallLLMErrors(unittest.TestCase):
    """畸形回應要丟帶診斷資訊的 RuntimeError,不是裸的 KeyError/IndexError。

    不打任何網路——urllib.request.urlopen 整個被 mock 掉,回傳一個假的
    context manager,__enter__ 給一段 BytesIO 讓 json.load 讀。
    """

    def _urlopen_returning(self, payload):
        cm = unittest.mock.MagicMock()
        cm.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        return cm

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key-for-test'})
    @patch('next_episode.urllib.request.urlopen')
    def test_candidates是空list時丟RuntimeError帶promptFeedback(self, mock_urlopen):
        mock_urlopen.return_value = self._urlopen_returning(
            {'candidates': [], 'promptFeedback': {'blockReason': 'SAFETY'}})
        with self.assertRaises(RuntimeError) as cm:
            ne.call_llm('prompt')
        self.assertIn('SAFETY', str(cm.exception))

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key-for-test'})
    @patch('next_episode.urllib.request.urlopen')
    def test_沒有candidates鍵時丟RuntimeError(self, mock_urlopen):
        mock_urlopen.return_value = self._urlopen_returning({'error': {'message': 'boom'}})
        with self.assertRaises(RuntimeError) as cm:
            ne.call_llm('prompt')
        # 訊息要指出問題出在 candidates,不能只是隨便一句 RuntimeError。
        self.assertIn('candidates', str(cm.exception))

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key-for-test'})
    @patch('next_episode.urllib.request.urlopen')
    def test_被安全機制擋掉沒有parts時丟RuntimeError帶finishReason(self, mock_urlopen):
        mock_urlopen.return_value = self._urlopen_returning(
            {'candidates': [{'finishReason': 'SAFETY', 'content': {}}]})
        with self.assertRaises(RuntimeError) as cm:
            ne.call_llm('prompt')
        self.assertIn('SAFETY', str(cm.exception))

    @patch('next_episode.call_llm')
    def test_LLM回非JSON時make_plan丟RuntimeError帶原文前300字(self, mock_call_llm):
        mock_call_llm.return_value = '這不是 JSON,是 LLM 亂回的一段文字說明。'
        canon = {'next_n': 3, 'rules': '', 'recent': ''}
        with self.assertRaises(RuntimeError) as cm:
            ne.make_plan(canon, [])
        self.assertIn('這不是 JSON', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
