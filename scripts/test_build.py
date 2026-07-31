#!/usr/bin/env python3
"""build.py 的單元測試。只驗純邏輯,不動 episodes.json/ep/*.html 這些真的
會被網站用到的檔案——寫進 ep/ 的測試輸出用完就刪。

跑法: python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""
import html
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import build as bd


class TestBuildAltEscape(unittest.TestCase):
    """code review 抓到的 Important:alt 文字沒跳脫就直接寫進 <img alt="…">,
    對白裡的雙引號會從屬性跳出去,LLM 生成內容(可能受社群許願字面影響)
    因此有一條直通已發佈網站的注入路徑。修法在 build.py(輸出端),用標準
    函式庫 html.escape(alt, quote=True)。
    """

    def _build_and_read(self, alt):
        ep = {'n': 999999, 'title': 'x', 'date': '2026-01-01', 'desc': 'd',
              'credit': 'c', 'pages': [{'f': '00-cover.webp', 'alt': alt}]}
        out_path = ROOT / 'ep' / '999999.html'
        try:
            bd.build_episode(ep, None, None)
            return out_path.read_text('utf-8')
        finally:
            if out_path.exists():
                out_path.unlink()

    def test_alt含雙引號與onerror不會從屬性跳出去(self):
        bad_alt = '"backdoor" onerror=alert(1)'
        out = self._build_and_read(bad_alt)
        # 沒跳脫的話,raw 雙引號會提早關掉 alt 屬性,onerror 變成 <img> 的
        # 另一個真實屬性——這正是 review 實測出來的注入路徑,要斷言它不存在。
        self.assertNotIn(f'alt="{bad_alt}">', out)
        # 跳脫後要能在輸出裡找到,不是整段被吃掉或改寫成別的東西。
        self.assertIn(html.escape(bad_alt, quote=True), out)
        self.assertIn(f'alt="{html.escape(bad_alt, quote=True)}">', out)

    def test_alt含尖括號不會被當成新標籤(self):
        bad_alt = '</title><script>alert(1)</script>'
        out = self._build_and_read(bad_alt)
        self.assertNotIn('<script>alert(1)</script>', out)
        self.assertIn(html.escape(bad_alt, quote=True), out)

    def test_正常alt跳脫後內容不變(self):
        # 既有兩話的 alt 都不含特殊字元,跳脫前後應該一模一樣——這條是
        # 回歸測試,防止「加了跳脫結果連正常字都被改掉」這種副作用。
        normal_alt = '深夜十一點的科技公司，四位工程師還在加班'
        out = self._build_and_read(normal_alt)
        self.assertIn(f'alt="{normal_alt}">', out)


class TestCacheVersionDigest(unittest.TestCase):
    """sw.js 的快取版號改成內容 hash 之後,人不再手動 bump。這幾條就是那個
    保證:內容變一定變、內容沒變一定不變。任一條壞掉,讀者就會拿到舊快取
    (或白抓一次十幾 MB),而且兩種都難從表面看出來。
    """

    def _in_tmp(self, fn):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            old = bd.ROOT
            bd.ROOT = root
            try:
                fn(root)
            finally:
                bd.ROOT = old

    def test_同樣內容算兩次一樣_且與清單順序無關(self):
        def check(root):
            (root / 'a.txt').write_bytes(b'one')
            (root / 'b.txt').write_bytes(b'two')
            v = bd.digest(['a.txt', 'b.txt'])
            self.assertEqual(v, bd.digest(['a.txt', 'b.txt']))
            self.assertEqual(v, bd.digest(['b.txt', 'a.txt']))
        self._in_tmp(check)

    def test_檔案內容變版號就變(self):
        def check(root):
            (root / 'a.txt').write_bytes(b'one')
            v = bd.digest(['a.txt'])
            (root / 'a.txt').write_bytes(b'ONE')
            self.assertNotEqual(v, bd.digest(['a.txt']))
        self._in_tmp(check)

    def test_清單增刪版號就變(self):
        def check(root):
            (root / 'a.txt').write_bytes(b'one')
            (root / 'b.txt').write_bytes(b'two')
            self.assertNotEqual(bd.digest(['a.txt']), bd.digest(['a.txt', 'b.txt']))
        self._in_tmp(check)

    def test_內容一樣但改名也算變動(self):
        # 路徑有進 hash。改名等於清單變了,快取鍵也該跟著換。
        def check(root):
            (root / 'a.txt').write_bytes(b'same')
            (root / 'b.txt').write_bytes(b'same')
            self.assertNotEqual(bd.digest(['a.txt']), bd.digest(['b.txt']))
        self._in_tmp(check)


if __name__ == '__main__':
    unittest.main()
