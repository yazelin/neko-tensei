#!/usr/bin/env python3
"""pipeline 的單元測試。只驗純邏輯,不打任何外部服務。

跑法: python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""
import base64
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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
        """最後兩話都要在,再往前一話不可以在。

        原本這裡寫死「ep1 的字串 + ep2 的字串」,第三話一落地就紅了——它驗的
        其實是「現在剛好只有兩話」,不是「取最後兩話」。改成從 episodes.json
        推導:兩話各斷言一次(只斷言最後一話的話,把 [-2:] 改成 [-1:] 照樣會過,
        就測不到「兩話」),再斷言更早那話不在,才鎖得住上界。

        指標用各話分鏡檔自己的 H1 整行(含開頭的 `# `),不是標題字串——標題會被
        別話引用(ep2.md 講字幕替換時就整句引了第一話的標題),拿標題當指標會讓
        「不在」那條斷言假失敗。H1 只會出現在自己的檔案裡。
        """
        c = ne.load_canon()
        ns = sorted(e['n'] for e in c['episodes'])
        story = pathlib.Path(__file__).parent.parent / 'story'

        def h1(n):
            return (story / f'ep{n}.md').read_text('utf-8').splitlines()[0]

        for n in ns[-2:]:
            self.assertIn(h1(n), c['recent'], f'最後兩話之一沒帶進來:第 {n} 話')
        if len(ns) > 2:
            self.assertNotIn(h1(ns[-3]), c['recent'],
                             f'帶進了第三舊的一話,取的不是「最近兩話」:第 {ns[-3]} 話')

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


class TestDate(unittest.TestCase):
    """話數日期要用台灣時間。

    第四話的落檔跑在 2026-07-31T17:12Z,台灣已經是 8/1 凌晨,但
    datetime.date.today() 在 runner 上(系統時區 UTC)給的是 7/31。那個日期
    會印在首頁的話數列表,也會進 sitemap 的 lastmod——讀者在台灣。
    """

    def test_跨日那幾個小時要給台灣的日期(self):
        # UTC 的 7/31 16:00 = 台北 8/1 00:00,是最容易出錯的那一刻
        import datetime as dt
        fake_utc = dt.datetime(2026, 7, 31, 16, 30, tzinfo=dt.timezone.utc)

        class _FixedDatetime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_utc.astimezone(tz) if tz else fake_utc

        with patch.object(ne.datetime, 'datetime', _FixedDatetime):
            self.assertEqual(ne.today_tw(), '2026-08-01')

    def test_一般時段兩邊同一天(self):
        import datetime as dt
        fake_utc = dt.datetime(2026, 7, 31, 3, 0, tzinfo=dt.timezone.utc)

        class _FixedDatetime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_utc.astimezone(tz) if tz else fake_utc

        with patch.object(ne.datetime, 'datetime', _FixedDatetime):
            self.assertEqual(ne.today_tw(), '2026-07-31')


class TestSaveImage(unittest.TestCase):
    """落檔要重新壓縮。

    第一次真跑的第三話是 23 MB,手工做的第一話 3.5 MB、第二話 4.7 MB——
    因為 generate_image 把服務端回來的近無損 webp 直接寫檔。這個站是 PWA,
    圖檔全部會被 precache,一話 23 MB 每加一話就疊一次。
    """

    SIZE = (200, 200)
    _RAW = None

    @classmethod
    def _big_webp(cls):
        """一張壓不太動的圖,確認重壓真的有發生。整個類別只做一次。

        第一版用 (i*37 + j*91) % 256 當「噪點」,其實是平滑漸層,無損壓完
        只有 114 bytes,測試因此紅得莫名其妙。改用固定種子的亂數——固定
        種子是為了每次跑都一樣,不要讓測試的成敗看運氣。

        無損編碼噪點很慢,所以圖只開 200x200,而且結果快取起來重複用:
        每個 test 各編一次 400x400 會讓整套測試從 0.03 秒變成 5 秒。
        """
        if cls._RAW is None:
            import io
            import random
            from PIL import Image
            px = random.Random(0).randbytes(cls.SIZE[0] * cls.SIZE[1] * 3)
            buf = io.BytesIO()
            Image.frombytes('RGB', cls.SIZE, px).save(buf, 'WEBP', quality=100, lossless=True)
            cls._RAW = buf.getvalue()
        return cls._RAW

    def test_webp_會被重新壓縮而不是原樣寫入(self):
        raw = self._big_webp()
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / 'x.webp'
            ne.save_image(raw, out)
            self.assertLess(out.stat().st_size, len(raw),
                            '落檔的檔案沒有比服務端回來的小,重壓沒生效')

    def test_非_webp_原樣寫入(self):
        # 一次性腳本會存 .png 來目視,那條路徑不該被改寫
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / 'x.png'
            ne.save_image(b'not-an-image', out)
            self.assertEqual(out.read_bytes(), b'not-an-image')

    def test_重壓後尺寸不變(self):
        from PIL import Image
        raw = self._big_webp()
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / 'x.webp'
            ne.save_image(raw, out)
            self.assertEqual(Image.open(out).size, self.SIZE)


class TestResume(unittest.TestCase):
    """整話七張約 36 分鐘,中途掛掉不該從第一張重來。

    但光跳過已存在的圖是錯的:企劃每次重跑都會叫 LLM 產一份新故事,沿用
    舊圖等於把新劇本配舊圖。所以企劃本身也要一起快取,兩者是同一份狀態。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(ne, 'CACHE', pathlib.Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_沒有快取時回_None(self):
        self.assertIsNone(ne.load_cached_plan(3))

    def test_存下去再讀回來是同一份(self):
        p = _good_plan()
        ne.save_cached_plan(3, p)
        self.assertEqual(ne.load_cached_plan(3), p)

    def test_不同話數的快取不互相污染(self):
        ne.save_cached_plan(3, _good_plan())
        self.assertIsNone(ne.load_cached_plan(4))

    def test_壞掉的快取當作沒有而不是炸掉(self):
        # 上一次跑到一半被砍,檔案寫了一半——這時候該重出企劃,不是整條線倒
        (pathlib.Path(self.tmp.name) / 'ep3-plan.json').write_text('{"title": ', 'utf-8')
        self.assertIsNone(ne.load_cached_plan(3))

    def test_落檔成功後快取要清掉(self):
        ne.save_cached_plan(3, _good_plan())
        ne.clear_cached_plan(3)
        self.assertIsNone(ne.load_cached_plan(3))

    def test_清一個不存在的快取不會炸(self):
        ne.clear_cached_plan(99)      # 沒跑到出圖就失敗時會走到這裡


class TestInWorldUIText(unittest.TestCase):
    """世界內的英文 UI 文字是刻意開的例外,不是漏洞。

    第一次真跑產出的第三話,企劃在畫面描述裡寫了 'Patch 1.0.3 Downloading...'
    與 'Welcome Admin',模型照畫了——那跟舊版 RULES 的「圖上唯一允許的文字
    是對白加一個貓字」直接牴觸,同一份 prompt 裡兩段指令打架。這部作品的角色
    是工程師,那種 UI 文字是梗的一部分,所以規則改成放行,並明確界定範圍。
    """

    def test_RULES_放行畫面描述指定的英文_UI_文字(self):
        self.assertIn('in-world English UI text', prompt.RULES)

    def test_RULES_仍然禁止把對白翻成英文貼上去(self):
        self.assertIn('never an English translation or transcription',
                      prompt.RULES)

    def test_RULES_仍然禁止狀聲字與浮水印(self):
        for banned in ('no sound effects', 'no watermark', 'no page numbers'):
            self.assertIn(banned, prompt.RULES, banned)

    def test_貓字例外還在(self):
        # 放行英文 UI 的時候很容易順手把這條寫掉,它是另一件事
        self.assertIn('貓', prompt.RULES)


class TestCastJsonIsTheSource(unittest.TestCase):
    """設定資料的單一事實來源是 story/cast.json,prompt.py 只負責組裝。

    分成兩份手寫的下場已經發生過:cast.json 寫「樹在爪上」,prompt.py 的
    SHEET 跟著寫 tree above a paw,而正典上那個紋章既不是樹也沒有肉球,
    模型很聽話地照錯的描述畫,通行證就漂了。
    """

    def setUp(self):
        self.cast = json.loads(
            (pathlib.Path(__file__).parent.parent / 'story' / 'cast.json').read_text('utf-8'))

    def test_每個角色與道具的參考圖都在_REF_裡(self):
        for k in list(self.cast['cast']) + list(self.cast['world']):
            self.assertIn(k, prompt.REF, k)

    def test_角色設定表逐句來自_cast_json(self):
        for k, v in self.cast['cast'].items():
            if v.get('sheet'):
                self.assertIn(v['sheet'], prompt.SHEET, f'{k} 的 sheet 沒進 SHEET')

    def test_紋章描述已修正(self):
        # 錯的舊描述不能再出現在任何地方
        self.assertNotIn('tree above a paw', prompt.SHEET)
        # 正典是三顆圓球的紅色剪影,不是樹也沒有肉球
        self.assertIn('three round balls', prompt.SHEET)
        self.assertIn('NO paw print', prompt.SHEET)

    def test_兩隻褐虎斑的分界有寫到字面(self):
        """小鳥不啾與小白++ 都是褐虎斑,毛長是唯一分得開的地方。

        第三話第 02 頁小白++ 被畫上了小鳥不啾的眼鏡。當時設定裡「長毛」只寫在
        小鳥不啾那邊,小白++ 完全沒提毛長;眼鏡那句寫成「臉上一定看得到」卻沒說
        只屬於她——一份 prompt 裡同時有強指令和兩隻長得像的貓,眼鏡就跑掉了。
        """
        self.assertIn('SHORT-HAIRED', prompt.SHEET, '小白++ 的短毛沒寫進設定表')
        self.assertIn('NO glasses', prompt.SHEET, '沒寫死小白++ 不戴眼鏡')
        self.assertIn('NEVER on any other cat', prompt.SHEET, '沒寫死眼鏡只屬於小鳥不啾')

    def test_金牌在胸前_背影看不到(self):
        """第三話第 06 頁畫背影時,「貓」字金牌浮在武士貓的背上。

        原本的設定只寫「hanging on his chest」——那是「有什麼」,沒寫「什麼
        時候看不到」。跟眼鏡、通行證同一類:模型不會自己推論遮擋關係。
        """
        self.assertIn('NOT visible', prompt.SHEET)
        self.assertIn('Never draw the medallion on his back', prompt.SHEET)

    def test_動作要用手做的規則有進_planner(self):
        # 第 04 頁的「用貓牙咬電纜」「用後腿踢插座」就是這樣來的
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('動作要用手做', p)

    def test_道具設定圖是乾淨的單一物件(self):
        rel = self.cast['world']['pass']['ref']
        p = pathlib.Path(__file__).parent.parent / rel
        self.assertTrue(p.is_file(), rel)


class TestWorldRefs(unittest.TestCase):
    """道具與場景鎖。搬自 comic-studio 的 world 庫:分鏡指名 → prompt 帶設定
    → 參考圖優先於角色附上去。沒有這一層,同一個道具每頁都會重抽一個樣子。
    """

    def test_帶道具時_prompt_有道具段(self):
        p = prompt.build_prompt('01', ['style', 'pass', 'xiaobai'], 'x')
        self.assertIn('PROPS AND PLACES', p)
        self.assertIn('THE PASS', p)

    def test_不帶道具時就沒有道具段(self):
        p = prompt.build_prompt('01', ['style', 'xiaobai'], 'x')
        self.assertNotIn('PROPS AND PLACES', p)

    def test_道具段排在角色設定表之前(self):
        # comic-studio 的順序:場景/道具決定這一格長什麼樣,角色是放進去的東西
        p = prompt.build_prompt('01', ['style', 'pass', 'xiaobai'], 'x')
        self.assertLess(p.index('PROPS AND PLACES'), p.index('CHARACTER SHEET'))

    def test_page_refs_把道具排在角色前面(self):
        page = {'n': '01', 'chars': ['xiaobai', 'uncle'], 'world': ['pass'], 'panels': []}
        keys = ne.page_refs(page)
        # 順序:畫風錨 → 框型錨(兩個都是「怎麼畫」)→ 道具鎖 → 角色(「畫什麼」)
        self.assertEqual(keys[:3], ['style', 'balloons', 'pass'])
        self.assertLess(keys.index('pass'), keys.index('xiaobai'))

    def test_page_refs_不認得的道具_id_直接忽略(self):
        page = {'n': '01', 'chars': ['xiaobai'], 'world': ['不存在的東西'], 'panels': []}
        self.assertNotIn('不存在的東西', ne.page_refs(page))

    def test_page_refs_不超過上限(self):
        page = {'n': '01',
                'chars': ['xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro'],
                'world': ['pass'],
                'panels': [{'pos': 'top', 'scene': 's',
                            'lines': [{'speaker': 'xiaobai', 'shape': 'THOUGHT', 'text': 't'}]}]}
        keys = ne.page_refs(page)
        self.assertLessEqual(len(keys), ne.MAX_REFS)
        # 被截掉的時候,畫風錨與道具鎖必須留著
        self.assertIn('style', keys)
        self.assertIn('pass', keys)

    def test_框型對照圖會被帶上(self):
        """框型只有文字規則、沒有視覺錨,就是通行證漂掉的同一個病。

        兩次真跑的第三話都一樣:SHOUT 畫得出來,OVAL 與 TREMBLE 全退化成
        圓角矩形——而 prompt 的 REMINDER 早就明文警告過這個失敗模式。
        """
        page = {'n': '01', 'chars': ['xiaobai'], 'panels': []}
        self.assertIn('balloons', ne.page_refs(page))

    def test_框型圖排在畫風錨後面(self):
        keys = ne.page_refs({'n': '01', 'chars': ['xiaobai'], 'panels': []})
        self.assertEqual(keys[:2], ['style', 'balloons'])

    def test_額度不夠時先犧牲框型圖而不是角色(self):
        # 五位角色 + 前世 + 道具 + 畫風錨已經吃滿 8 張,框型圖是手法的錨,
        # 角色設定圖是內容正確性——擠不下時該掉的是前者
        page = {'n': '01',
                'chars': ['xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro'],
                'world': ['pass'],
                'panels': [{'pos': 'top', 'scene': 's',
                            'lines': [{'speaker': 'xiaobai', 'shape': 'THOUGHT', 'text': 't'}]}]}
        keys = ne.page_refs(page)
        self.assertNotIn('balloons', keys)
        for must in ('style', 'pass', 'past', 'xiaoniao', 'kojiro'):
            self.assertIn(must, keys, must)

    def test_封面不帶框型圖(self):
        # 封面沒有對話框
        self.assertNotIn('balloons', ne.cover_refs(_good_plan()))

    def test_prompt_要明講不要把對照圖畫進頁面(self):
        p = prompt.build_prompt('01', ['style', 'balloons', 'xiaobai'], 'x')
        self.assertIn('Do NOT draw the chart itself into the page', p)

    def test_企劃寫了不存在的道具_id_驗證器要擋(self):
        p = _good_plan()
        p['pages'][0]['world'] = ['不存在的東西']
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('道具' in e or 'world' in e for e in errs), errs)

    def test_封面也要帶道具鎖(self):
        # 第三話第一次真跑,封面沒帶任何道具鎖,通行證被畫成紅色長方形門禁卡
        # (內頁那張則畫成金懷錶)。封面是最多人看到的一張,不能是唯一沒上鎖的。
        p = _good_plan()
        p['pages'][2]['world'] = ['pass']
        keys = ne.cover_refs(p)
        self.assertEqual(keys[0], 'style')
        self.assertIn('pass', keys)
        self.assertLess(keys.index('pass'), keys.index('xiaobai'))

    def test_封面沒道具時就只有兩個錨與五位角色(self):
        keys = ne.cover_refs(_good_plan())
        self.assertEqual(keys, ['style', 'cover_style',
                                'xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro'])

    def test_封面參考圖不超過上限(self):
        p = _good_plan()
        for pg in p['pages']:
            pg['world'] = ['pass']
        self.assertLessEqual(len(ne.cover_refs(p)), ne.MAX_REFS)

    def test_企劃沒寫_world_欄位也算合法(self):
        # world 是選配,舊企劃不該因為少這個欄位就被擋下來
        self.assertEqual(ne.validate_plan(_good_plan(), 3, ['我們怎麼變成貓了？！']), [])


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
        """規範全文與最近兩話的分鏡都要進 planner。

        原本這裡寫死第二話標題裡的「得加 Token」,第四話一落地就紅了——它驗的
        是「現在最近兩話剛好是 ep1、ep2」。跟 test_帶進最近兩話的分鏡 同一種
        脆弱,同樣改成從 episodes.json 推導,用各話分鏡檔的 H1 整行當指標。
        """
        canon = ne.load_canon()
        p = ne.build_planner_prompt(canon, [])
        self.assertIn('對話框的形狀跟著劇情走', p)     # 規範全文

        story = pathlib.Path(__file__).parent.parent / 'story'
        for n in sorted(e['n'] for e in canon['episodes'])[-2:]:
            h1 = (story / f'ep{n}.md').read_text('utf-8').splitlines()[0]
            self.assertIn(h1, p, f'最近兩話之一沒進 planner:第 {n} 話')

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


class TestPageBody(unittest.TestCase):
    def test_翻成PANEL段落並帶上框型(self):
        page = {'n': '01', 'chars': ['xiaobai'], 'panels': [
            {'pos': 'top', 'scene': 'four cats on a hill',
             'lines': [{'speaker': 'xiaobai', 'shape': 'SHOUT', 'text': '出發！'}]}]}
        b = ne.page_body(page)
        self.assertIn('PANEL 1 (top): four cats on a hill', b)
        self.assertIn('SHOUT BALLOON', b)
        self.assertIn('出發！', b)

    def test_參考圖第一張永遠是畫風(self):
        page = {'n': '01', 'chars': ['leo', 'uncle'], 'panels': []}
        self.assertEqual(ne.page_refs(page)[0], 'style')

    def test_出場角色都被帶進參考圖(self):
        page = {'n': '01', 'chars': ['leo', 'uncle'], 'panels': []}
        keys = ne.page_refs(page)
        self.assertIn('leo', keys)
        self.assertIn('uncle', keys)

    def test_參考圖不重複(self):
        page = {'n': '01', 'chars': ['leo', 'leo', 'style'], 'panels': []}
        keys = ne.page_refs(page)
        self.assertEqual(len(keys), len(set(keys)))

    def test_有記憶泡才帶前世設定圖(self):
        with_os = {'n': '04', 'chars': ['uncle'], 'panels': [
            {'pos': 'bottom', 'scene': 'x',
             'lines': [{'speaker': 'uncle', 'shape': 'THOUGHT', 'text': '這不就是 code review。'}]}]}
        without = {'n': '01', 'chars': ['uncle'], 'panels': [
            {'pos': 'top', 'scene': 'x',
             'lines': [{'speaker': 'uncle', 'shape': 'OVAL', 'text': '哼。'}]}]}
        self.assertIn('past', ne.page_refs(with_os))
        self.assertNotIn('past', ne.page_refs(without))

    def test_組出來的prompt包含這一頁的對白(self):
        import prompt as pr
        page = {'n': '01', 'chars': ['xiaobai'], 'panels': [
            {'pos': 'top', 'scene': 'x',
             'lines': [{'speaker': 'xiaobai', 'shape': 'SHOUT', 'text': '出發！'}]}]}
        p = pr.build_prompt('01', ne.page_refs(page), ne.page_body(page))
        self.assertIn('出發！', p)
        self.assertIn('FINAL CHECK', p)


class TestPageBodyMissingFields(unittest.TestCase):
    """review 抓到的三種缺欄位:原本 scene 缺欄位是靜默印出空場景,
    shape/text 缺欄位是裸 KeyError,三種都要改成能指出第幾頁第幾格的
    ValueError,GitHub Actions 無人值守跑的時候 log 才看得出是哪裡壞的。
    """

    def test_缺scene會丟ValueError帶頁碼與格號(self):
        page = {'n': '03', 'panels': [
            {'pos': 'top', 'scene': 'ok', 'lines': []},
            {'pos': 'mid', 'lines': [{'speaker': 'uncle', 'shape': 'OVAL', 'text': 'x'}]}]}
        with self.assertRaises(ValueError) as cm:
            ne.page_body(page)
        self.assertIn('第 03 頁第 2 格缺 scene', str(cm.exception))

    def test_缺shape會丟ValueError帶頁碼與格號(self):
        page = {'n': '01', 'panels': [
            {'pos': 'top', 'scene': 'x',
             'lines': [{'speaker': 'uncle', 'text': '哼'}]}]}
        with self.assertRaises(ValueError) as cm:
            ne.page_body(page)
        self.assertIn('第 01 頁第 1 格缺 shape', str(cm.exception))

    def test_缺text會丟ValueError帶頁碼與格號(self):
        page = {'n': '01', 'panels': [
            {'pos': 'top', 'scene': 'x',
             'lines': [{'speaker': 'uncle', 'shape': 'OVAL'}]}]}
        with self.assertRaises(ValueError) as cm:
            ne.page_body(page)
        self.assertIn('第 01 頁第 1 格缺 text', str(cm.exception))


class TestGenerateImageMalformedResponse(unittest.TestCase):
    """generate_image 對畸形回應要丟帶診斷資訊的 RuntimeError,不是裸
    KeyError。不打網路,不真的睡 15 秒——urllib.request.urlopen 與
    time.sleep 都 mock 掉,跟 TestCallLLMErrors 用同一套手法。
    """

    def _urlopen_returning(self, payload):
        cm = unittest.mock.MagicMock()
        cm.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        return cm

    @patch.dict('os.environ', {'CODEX_IMAGE_KEY': 'fake-key-for-test'})
    @patch('next_episode.urllib.request.urlopen')
    def test_job建立回應缺id時丟RuntimeError(self, mock_urlopen):
        mock_urlopen.return_value = self._urlopen_returning({'status': 'queued'})
        with self.assertRaises(RuntimeError) as cm:
            ne.generate_image('01', ['style'], 'body', pathlib.Path('/tmp/unused.png'))
        self.assertIn('id', str(cm.exception))

    @patch.dict('os.environ', {'CODEX_IMAGE_KEY': 'fake-key-for-test'})
    @patch('next_episode.time.sleep')
    @patch('next_episode.urllib.request.urlopen')
    def test_succeeded但沒有images時丟RuntimeError(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            self._urlopen_returning({'id': 'job-1'}),
            self._urlopen_returning({'status': 'succeeded'}),
        ]
        # generate_image 拿到 job id 就會印一行進度,這裡吞掉它,不然測試
        # 輸出裡會冒出一行沒頭沒尾的「job 01 job-1」。
        with self.assertRaises(RuntimeError) as cm, redirect_stdout(io.StringIO()):
            ne.generate_image('01', ['style'], 'body', pathlib.Path('/tmp/unused.png'))
        self.assertIn('images', str(cm.exception))


class TestRender(unittest.TestCase):
    def test_分鏡檔含標題轉折與每頁對白(self):
        md = ne.render_storyboard(_good_plan(), 3)
        self.assertIn('第三話：黑塔上的另一個人', md)
        self.assertIn('塔前受阻', md)
        self.assertIn('那座塔越來越近了。', md)

    def test_分鏡檔含該頁的生圖prompt(self):
        md = ne.render_storyboard(_good_plan(), 3)
        self.assertIn('PANEL 1 (top):', md)

    def test_episodes條目頁數正確(self):
        e = ne.episode_entry(_good_plan(), 3, '2026-08-07', has_cover=True)
        self.assertEqual(e['n'], 3)
        self.assertEqual(len(e['pages']), 7)
        self.assertEqual(e['pages'][0]['f'], '00-cover.webp')
        self.assertEqual(e['pages'][-1]['f'], '06.webp')

    def test_沒有封面時只有六頁(self):
        e = ne.episode_entry(_good_plan(), 3, '2026-08-07', has_cover=False)
        self.assertEqual(len(e['pages']), 6)
        self.assertEqual(e['pages'][0]['f'], '01.webp')

    def test_每頁都有alt文字(self):
        e = ne.episode_entry(_good_plan(), 3, '2026-08-07', has_cover=True)
        for p in e['pages']:
            self.assertTrue(p['alt'].strip(), p)

    def test_PR內文每頁都附劇本說的(self):
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('劇本說的', b)
        self.assertIn('那座塔越來越近了。', b)

    def test_PR內文列出許願並說明有沒有收進去(self):
        b = ne.pr_body(_good_plan(), 3, ['想看貓咪泡溫泉'])
        self.assertIn('想看貓咪泡溫泉', b)
        self.assertIn('讀了 1 則社群許願', b)

    def test_PR內文標出話型(self):
        p = _good_plan(); p['kind'] = '日常番'
        self.assertIn('話型：日常番', ne.pr_body(p, 3, []))

    def test_沒有許願時PR內文要講明(self):
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('由 AI 自己決定', b)

    def test_PR內文提醒要看的是圖有沒有照劇本畫(self):
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('圖有沒有照劇本畫', b)

    def test_讀許願失敗時PR內文要講明不能誤判成沒有許願(self):
        # wish_err 非 None 是「讀取本身出錯」,不是「這次沒有人許願」——
        # 兩者混在一起顯示,社群寫了許願卻全被當成沒發生過,而且沒人會
        # 發現。這裡同時鎖住「有講失敗原因」與「不能出現沒有許願那句話」,
        # 只斷言前者會漏掉「函式其實還是走了沒有許願那個分支、只是額外
        # 多印一行失敗訊息」這種半吊子修法。
        err = 'gh api graphql 失敗: authentication required'
        b = ne.pr_body(_good_plan(), 3, [], wish_err=err)
        self.assertIn('讀許願失敗', b)
        self.assertIn(err, b)
        self.assertNotIn('這次沒有許願，由 AI 自己決定要畫什麼', b)

    def test_讀許願失敗時就算有許願清單也要以失敗為準(self):
        # 理論上 wish_err 非 None 時 wishes 應該永遠是空清單(fetch_wishes
        # 的介面保證),但呼叫端萬一傳錯也不該讓「有許願」的分支蓋掉失敗
        # 訊息——失敗優先顯示,不然還是會出現「看起來收到許願了」的假象。
        err = 'gh api graphql 失敗: rate limited'
        b = ne.pr_body(_good_plan(), 3, ['想看貓咪泡溫泉'], wish_err=err)
        self.assertIn('讀許願失敗', b)
        self.assertNotIn('讀了 1 則社群許願', b)

    def test_PR內文圖片連結指向草稿分支不是main(self):
        # code review 抓到的 Critical:pr_body 原本用 blob/HEAD,在 GitHub
        # 上會解析成預設分支(main)——但這一話的新圖只在尚未合併的分支上,
        # main 沒有,附出來的圖全是壞連結,「人看圖再按 merge」的閘門形同
        # 虛設。改用 raw.githubusercontent.com 指到實際的草稿分支。
        b = ne.pr_body(_good_plan(), 3, [], branch='auto/ep3')
        self.assertIn(
            'https://raw.githubusercontent.com/yazelin/neko-tensei/'
            'auto/ep3/images/ep3/01.webp', b)
        self.assertNotIn('blob/HEAD', b)

    def test_PR內文沒給branch時預設用auto_epN(self):
        # branch 沒傳的話要有一個合理預設,不能整個炸掉或退回壞連結。
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('auto/ep3', b)
        self.assertNotIn('blob/HEAD', b)

    def test_分鏡表格對白含管線符號不會切壞表格(self):
        # code review 抓到的 Important:表格欄位值裡的 | 沒跳脫,對白裡的
        # | 會被 markdown 當成分欄符號,把一列切成錯的欄數——這部漫畫角色
        # 是工程師,對白出現 | 不是罕見情況。這裡直接數那一列「沒有被跳脫
        # 的 |」數量,好的表格列(4 欄)固定是 5 個:首尾各一,欄與欄之間 3
        # 個。如果 | 沒跳脫,對白裡多的那個 | 會讓這個數字變成 6。
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['text'] = '訊息 | 收到了嗎'
        md = ne.render_storyboard(p, 3)
        line = next(l for l in md.splitlines() if '收到了嗎' in l)
        unescaped = re.findall(r'(?<!\\)\|', line)
        self.assertEqual(len(unescaped), 5,
                         f'對白裡的 | 沒被跳脫,表格列被切成了 {len(unescaped) - 1} 欄:{line}')
        # 跳脫後的內容還是要看得到原本的對白,不能整段被吃掉。
        self.assertIn('訊息 \\| 收到了嗎', md)


class TestBaseUrlFallback(unittest.TestCase):
    """base url 的環境變數是空字串時要退回內建預設。

    workflow 把 ${{ secrets.X }} 塞進 env,secret 沒設時給的是空字串而不是
    「沒這個變數」,os.environ.get 的第二參數救不到——URL 會組成
    /v1beta/models/... 直接炸在 CI 上,而本機因為根本沒設那個變數,永遠
    重現不出來。這個測試靠重新 import 模組來看模組層級的求值結果。
    """

    def _reimport_with(self, env):
        import importlib
        with patch.dict(os.environ, env):
            return importlib.reload(ne)

    def tearDown(self):
        import importlib
        importlib.reload(ne)          # 還原成乾淨環境下的模組狀態

    def test_空字串要退回內建預設(self):
        m = self._reimport_with({'GEMINI_WEB_BASE_URL': '', 'CODEX_IMAGE_BASE_URL': ''})
        self.assertTrue(m.GEMINI_BASE.startswith('https://'), m.GEMINI_BASE)
        self.assertTrue(m.IMG_BASE.startswith('https://'), m.IMG_BASE)

    def test_有值時照用(self):
        m = self._reimport_with({'GEMINI_WEB_BASE_URL': 'https://example.test/g',
                                 'CODEX_IMAGE_BASE_URL': 'https://example.test/c'})
        self.assertEqual(m.GEMINI_BASE, 'https://example.test/g')
        self.assertEqual(m.IMG_BASE, 'https://example.test/c')


class TestCover(unittest.TestCase):
    """封面要跟第一、二話同一個系列:大標題、角色名牌、底部話數帶。

    pipeline 一開始刻意讓封面完全無字(理由是「文字烤進圖裡,改一個字就是
    整張重生」),結果第三話封面跟前兩話不是同一個系列——前兩話的標題就是
    AI 畫進去的(story/README.md 有一整段在講外稿封面的錯字怎麼修,會有錯字
    正代表那些字是模型畫的)。所以改回烤字,並把前兩話的封面當參考圖鎖版面。
    """

    def test_封面描述帶進三個轉折(self):
        b = ne.cover_body(_good_plan(), 3)
        for beat in _good_plan()['beats']:
            self.assertIn(beat, b)

    def test_封面要求全員入鏡(self):
        self.assertIn('all five', ne.cover_body(_good_plan(), 3).lower())

    def test_封面帶作品大標題(self):
        self.assertIn('轉生成貓貓的我們', ne.cover_body(_good_plan(), 3))

    def test_封面底部帶話數與這一話標題(self):
        b = ne.cover_body(_good_plan(), 3)
        self.assertIn('第三話：黑塔上的另一個人', b)

    def test_話數用中文數字(self):
        self.assertIn('第十話：', ne.cover_body(_good_plan(), 10))

    def test_封面帶五位角色的名牌(self):
        b = ne.cover_body(_good_plan(), 3)
        for name in ne.NAME.values():
            self.assertIn(name, b, name)

    def test_封面不含對話框規則(self):
        # 封面沒有對白,不該帶 BALLOON SHAPES——但它現在有字,所以要帶逐字
        # 照抄的規則,這兩件事不是同一件
        p = prompt.build_prompt('cover', ['style'], ne.cover_body(_good_plan(), 3))
        self.assertNotIn('BALLOON SHAPES', p)

    def test_封面要帶逐字照抄的中文規則(self):
        p = prompt.build_prompt('cover', ['style'], ne.cover_body(_good_plan(), 3))
        self.assertIn('CHARACTER BY CHARACTER', p)

    def test_角色卡仍然完全無字(self):
        p = prompt.build_prompt('kojiro', ['kojiro'], 'A single portrait')
        self.assertNotIn('CHARACTER BY CHARACTER', p)
        self.assertNotIn('BALLOON SHAPES', p)

    def test_封面要壓掉BASE的三格分鏡指令(self):
        # BASE 寫死「THREE horizontal panels」,封面是單張圖。body 排在
        # prompt 最後面,這句反指令必須在,不然模型會照 BASE 畫成三格。
        p = prompt.build_prompt('cover', ['style'], ne.cover_body(_good_plan(), 3))
        self.assertIn('THREE horizontal panels', p)          # BASE 還在
        self.assertIn('NOT a multi-panel page', p)           # 反指令也在
        self.assertGreater(p.index('NOT a multi-panel page'),
                           p.index('THREE horizontal panels'),
                           '反指令必須排在 BASE 之後才蓋得掉')

    def test_封面參考圖含既有封面當版面錨(self):
        keys = ne.cover_refs(_good_plan())
        self.assertIn('cover_style', keys)
        self.assertLess(keys.index('cover_style'), keys.index('xiaoniao'),
                        '版面錨要排在角色前面')


class TestRetry(unittest.TestCase):
    def _with_fake_plan(self, fake):
        orig = ne.make_plan
        ne.make_plan = fake
        self.addCleanup(setattr, ne, 'make_plan', orig)

    def test_第一次就過就不重試(self):
        calls = []
        self._with_fake_plan(lambda canon, wishes: (calls.append(1), _good_plan())[1])
        ne.plan_with_retry(ne.load_canon(), [], [], 3)
        self.assertEqual(len(calls), 1)

    def test_第一次不過會重試第二次(self):
        calls = []

        def fake(canon, wishes):
            calls.append(1)
            if len(calls) == 1:
                bad = _good_plan()
                bad['pages'] = bad['pages'][:3]
                return bad
            return _good_plan()

        self._with_fake_plan(fake)
        with redirect_stdout(io.StringIO()):
            plan = ne.plan_with_retry(ne.load_canon(), [], [], 3)
        self.assertEqual(len(calls), 2)
        self.assertEqual(plan['title'], _good_plan()['title'])

    def test_連兩次都不過就丟例外並帶上原因(self):
        def fake(canon, wishes):
            bad = _good_plan()
            bad['pages'] = bad['pages'][:2]
            return bad

        self._with_fake_plan(fake)
        with self.assertRaises(RuntimeError) as cm, redirect_stdout(io.StringIO()):
            ne.plan_with_retry(ne.load_canon(), [], [], 3)
        self.assertIn('六頁', str(cm.exception))

    def test_出圖重試上限是三次(self):
        self.assertEqual(ne.IMG_RETRIES, 3)

    def test_出圖前兩次失敗第三次成功就算過(self):
        calls = []

        def fake(name, keys, body, out):
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError('502 內容重複偵測')

        with patch.object(ne, 'generate_image', fake), \
                patch.object(ne.time, 'sleep'), redirect_stdout(io.StringIO()):
            ne.generate_with_retry('01', ['style'], 'body', pathlib.Path('/tmp/unused.webp'))
        self.assertEqual(len(calls), 3)

    def test_出圖三次都失敗就丟例外並帶上最後一次原因(self):
        def fake(name, keys, body, out):
            raise RuntimeError('502 內容重複偵測')

        with patch.object(ne, 'generate_image', fake), \
                patch.object(ne.time, 'sleep'), redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as cm:
                ne.generate_with_retry('01', ['style'], 'body',
                                       pathlib.Path('/tmp/unused.webp'))
        self.assertIn('502', str(cm.exception))


class TestMain(unittest.TestCase):
    """驅動腳本的旗標。

    fetch_wishes 一律 patch 掉:那支會叫 `gh` 打 GitHub,單元測試不該
    需要網路、也不該因為許願串的內容變了就紅。這裡要驗的是旗標的
    分流,不是讀許願——那個 TestWishes 已經驗過了。
    """

    def _run(self, argv, plan):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as f:
            json.dump(plan, f)
            path = f.name
        self.addCleanup(os.unlink, path)
        buf = io.StringIO()
        with patch.object(ne, 'fetch_wishes', return_value=([], None)), \
                redirect_stdout(buf):
            rc = ne.main(argv + ['--plan-from', path])
        return rc, buf.getvalue()

    def test_plan_from_搭配_dry_run_不碰任何檔案(self):
        before = _tree_snapshot()
        rc, out = self._run(['--dry-run'], _good_plan())
        self.assertEqual(rc, 0, out)
        self.assertIn('企劃通過驗證', out)
        self.assertEqual(_tree_snapshot(), before, '--dry-run 動到了 repo 裡的檔案')

    def test_壞企劃會讓程式回非零並印出原因(self):
        bad = _good_plan()
        bad['pages'][0]['panels'][0]['lines'][0]['text'] = '这个世界'
        rc, out = self._run(['--dry-run'], bad)
        self.assertEqual(rc, 1)
        self.assertIn('簡體', out)


def _tree_snapshot():
    """repo 裡「pipeline 會寫到」的那些檔案的 (路徑, mtime, 大小)。

    整個 repo 走一遍太慢也太吵(__pycache__、.git 都會動),只盯落檔那一步
    真的會碰的目標。
    """
    root = pathlib.Path(ne.ROOT)
    targets = [root / 'episodes.json', root / 'sw.js', root / 'story', root / 'ep']
    snap = []
    for t in targets:
        paths = sorted(t.rglob('*')) if t.is_dir() else [t]
        for p in paths:
            if p.is_file():
                st = p.stat()
                snap.append((str(p), st.st_mtime_ns, st.st_size))
    return snap


class TestBackendDispatch(unittest.TestCase):
    """企劃與出圖各自可以換後端。fork 的人靠這兩個環境變數擺脫我的自架服務,
    所以「分流有沒有真的分到」要有測試盯著——設錯了會靜靜打回預設的後端,
    而預設那個別人根本沒有金鑰,錯誤訊息會指向完全無關的地方。
    """

    def _urlopen_returning(self, payload):
        cm = unittest.mock.MagicMock()
        cm.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        return cm

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'fake'})
    @patch('next_episode.PLANNER_PROVIDER', 'openai')
    @patch('next_episode.urllib.request.urlopen')
    def test_openai相容端點取得企劃文字(self, mock_urlopen):
        mock_urlopen.return_value = self._urlopen_returning(
            {'choices': [{'message': {'content': '{"title": "x"}'}}]})
        self.assertEqual(ne.call_llm('prompt'), '{"title": "x"}')
        req = mock_urlopen.call_args[0][0]
        self.assertTrue(req.full_url.endswith('/chat/completions'), req.full_url)
        self.assertEqual(req.get_header('Authorization'), 'Bearer fake')

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'fake'})
    @patch('next_episode.PLANNER_PROVIDER', 'openai')
    @patch('next_episode.urllib.request.urlopen')
    def test_openai回應沒有content時丟RuntimeError帶finish_reason(self, mock_urlopen):
        mock_urlopen.return_value = self._urlopen_returning(
            {'choices': [{'finish_reason': 'content_filter'}]})
        with self.assertRaises(RuntimeError) as cm:
            ne.call_llm('prompt')
        self.assertIn('content_filter', str(cm.exception))

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'fake'})
    @patch('next_episode.PLANNER_PROVIDER', 'openai')
    @patch('next_episode.urllib.request.urlopen')
    def test_請求要帶自訂UA與夠大的max_tokens(self, mock_urlopen):
        # UA:Groq 擋在 Cloudflare 後面,看到 Python-urllib 的預設 UA 直接回
        # 403 error code 1010,而回應裡沒有一個字提到 UA。實測換 UA 就通。
        # max_tokens:沒設時 gpt-oss-120b 只寫了一頁企劃就收尾,驗證器擋下來,
        # 但錯誤訊息會讓人以為是模型不聽話,其實是輸出上限太小。
        mock_urlopen.return_value = self._urlopen_returning(
            {'choices': [{'message': {'content': '{}'}}]})
        ne.call_llm('prompt')
        req = mock_urlopen.call_args[0][0]
        self.assertNotIn('Python-urllib', req.get_header('User-agent') or '')
        self.assertGreaterEqual(json.loads(req.data)['max_tokens'], 4096)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'fake'})
    @patch('next_episode.PLANNER_PROVIDER', 'openai')
    @patch('next_episode.urllib.request.urlopen')
    def test_輸出被切斷時錯誤訊息要點名max_tokens(self, mock_urlopen):
        # 半截 JSON 直接回去,會在 json.loads 那裡丟「Expecting value」,
        # 讓人以為是模型不照格式回。實際發生過:glm-5.2 把 16384 全燒在
        # 推理上還沒寫完企劃。
        mock_urlopen.return_value = self._urlopen_returning(
            {'choices': [{'finish_reason': 'length',
                          'message': {'content': '{"title": "半截'}}]})
        with self.assertRaises(RuntimeError) as cm:
            ne.call_llm('prompt')
        self.assertIn('OPENAI_MAX_TOKENS', str(cm.exception))

    @patch('next_episode.PLANNER_PROVIDER', 'llama-cpp')
    def test_不認得的PLANNER_PROVIDER當場停下來(self):
        # 靜靜 fallback 回 gemini 的話,錯誤會變成「沒有 GEMINI_API_KEY」,
        # 跟真正的原因(名字打錯)差了十萬八千里。
        with self.assertRaises(RuntimeError) as cm:
            ne.call_llm('prompt')
        self.assertIn('llama-cpp', str(cm.exception))

    @patch('next_episode.IMAGE_PROVIDER', 'midjourney')
    def test_不認得的IMAGE_PROVIDER當場停下來(self):
        with self.assertRaises(RuntimeError) as cm:
            ne.generate_image('01', ['style'], 'body', pathlib.Path('/tmp/x.webp'))
        self.assertIn('midjourney', str(cm.exception))

    def test_gemini出圖回應_文字與圖混在一起也挑得出圖(self):
        # 模型很愛先講一句「Here is the image」再給圖,寫死 parts[0] 會挑到文字。
        raw = ne._gemini_image_bytes({'candidates': [{'content': {'parts': [
            {'text': 'Here is the image you asked for'},
            {'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(b'PNGDATA').decode()}},
        ]}}]})
        self.assertEqual(raw, b'PNGDATA')

    def test_gemini出圖回應_底線寫法的inline_data也吃得下(self):
        raw = ne._gemini_image_bytes({'candidates': [{'content': {'parts': [
            {'inline_data': {'data': base64.b64encode(b'WEBPDATA').decode()}}]}}]})
        self.assertEqual(raw, b'WEBPDATA')

    def test_gemini出圖被擋掉時丟RuntimeError帶finishReason(self):
        with self.assertRaises(RuntimeError) as cm:
            ne._gemini_image_bytes({'candidates': [{'finishReason': 'IMAGE_SAFETY'}]})
        self.assertIn('IMAGE_SAFETY', str(cm.exception))



def _plan_with(*texts):
    """只帶對白的最小企劃,給校對測試用。"""
    return {'pages': [{'n': 1, 'panels': [
        {'lines': [{'speaker': 'xiaobai', 'shape': 'OVAL', 'text': t}]} for t in texts]}]}


class TestWordingProblems(unittest.TestCase):
    """對白錯字校對。validate_plan 抓不到這一類——「完旦」是合法字元組成的
    錯詞,寫成程式要有詞庫,而這個 repo 的紅線是不手維護字表。"""

    def test_抓到錯字並帶出正確的詞(self):
        with patch.object(ne, 'call_llm', lambda _: json.dumps({'problems': [
                {'line': 1, 'wrong': '完旦', 'right': '完蛋'}]})):
            errs = ne.wording_problems(_plan_with('完旦了！'))
        self.assertEqual(len(errs), 1)
        self.assertIn('完旦', errs[0])
        self.assertIn('完蛋', errs[0])

    def test_沒問題就是空清單(self):
        with patch.object(ne, 'call_llm', lambda _: '{"problems": []}'):
            self.assertEqual(ne.wording_problems(_plan_with('魔力回來了！')), [])

    def test_原文裡沒有的詞一律丟掉(self):
        # 模型偶爾會回一個原文根本沒出現的詞(實測把「還敢慶祝」讀成「慶視」)。
        # 拿幻覺去擋掉一份好企劃,比漏掉一個錯字更糟。
        with patch.object(ne, 'call_llm', lambda _: json.dumps({'problems': [
                {'line': 1, 'wrong': '慶視', 'right': '慶祝'}]})):
            self.assertEqual(ne.wording_problems(_plan_with('四隻空瓶子，還敢慶祝。')), [])

    def test_校對器自己壞掉不擋整條線(self):
        # 這是加分項,不該讓一話卡在校對器上。
        def boom(_):
            raise RuntimeError('planner down')
        with patch.object(ne, 'call_llm', boom):
            self.assertEqual(ne.wording_problems(_plan_with('完旦了！')), [])
        with patch.object(ne, 'call_llm', lambda _: 'not json at all'):
            self.assertEqual(ne.wording_problems(_plan_with('完旦了！')), [])

    def test_沒有對白就不呼叫模型(self):
        def boom(_):
            raise AssertionError('不該被呼叫')
        with patch.object(ne, 'call_llm', boom):
            self.assertEqual(ne.wording_problems({'pages': []}), [])

    def test_規則沒過就不浪費一次校對呼叫(self):
        calls = []
        with patch.object(ne, 'make_plan', lambda *a: {'nope': True}), \
             patch.object(ne, 'validate_plan', lambda *a: ['頁數不對']), \
             patch.object(ne, 'wording_problems', lambda p: calls.append(p) or []):
            with self.assertRaises(RuntimeError):
                ne.plan_with_retry({}, [], [], 6)
        self.assertEqual(calls, [])


class TestVerifySection(unittest.TestCase):
    """PR 內文的機器驗收段。人是閘門,所以這段的用字要讓人知道「機器說過了」
    不等於「可以直接按 merge」。"""

    PLAN = {'title': 'T', 'desc': 'D', 'beats': ['b1', 'b2', 'b3'],
            'kind': '推進主線',
            'pages': [{'n': '01', 'panels': [], 'world': []}]}

    def test_沒過的頁列在前面而且點名理由(self):
        body = ne.pr_body(self.PLAN, 6, [], None,
                          verdicts=[('01', 'FAIL', 'A 違規＋上格＋小白++戴了眼鏡'),
                                    ('02', 'PASS', '')])
        self.assertIn('## 機器驗收', body)
        self.assertIn('第 01 頁', body)
        self.assertIn('小白++戴了眼鏡', body)
        self.assertNotIn('第 02 頁 `PASS`', body)

    def test_全過也要說這不等於圖畫對了(self):
        body = ne.pr_body(self.PLAN, 6, [], None,
                          verdicts=[('01', 'PASS', ''), ('02', 'PASS', '')])
        self.assertIn('不代表圖畫對了', body)

    def test_沒跑驗收就不生出這一段(self):
        # 沒有 CODEX_IMAGE_KEY 時 verdicts 是空的,不該憑空多一個空標題
        self.assertNotIn('## 機器驗收', ne.pr_body(self.PLAN, 6, [], None, verdicts=[]))

    def test_驗收器自己壞掉會列出來(self):
        # 靜靜跳過等於騙人說這一話沒問題
        body = ne.pr_body(self.PLAN, 6, [], None,
                          verdicts=[('01', 'ERR', '驗收沒跑成功:connection reset')])
        self.assertIn('ERR', body)
        self.assertIn('connection reset', body)


class TestVerifyEpisode(unittest.TestCase):
    def test_沒有金鑰就跳過(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ne.verify_episode(6, {'pages': []}), [])


if __name__ == '__main__':
    unittest.main()
