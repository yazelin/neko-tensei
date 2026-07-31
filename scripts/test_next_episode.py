#!/usr/bin/env python3
"""pipeline 的單元測試。只驗純邏輯,不打任何外部服務。

跑法: python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""
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


if __name__ == '__main__':
    unittest.main()
