#!/usr/bin/env python3
"""verify_pages.py 的單元測試。只驗純邏輯,不呼叫模型(那要花帳號額度而且慢)。

跑法: python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_pages


class TestVerdict(unittest.TestCase):
    def test_取最後一個判定(self):
        # codex 會把結尾再印一次,取第一個會拿到中途的字樣
        self.assertEqual(verify_pages.verdict_of("VERDICT: FAIL\n...\nVERDICT: FAIL"), "FAIL")
        self.assertEqual(verify_pages.verdict_of("A 合格\nVERDICT: PASS"), "PASS")

    def test_沒有判定就是_ERR(self):
        # 模型被安全機制擋掉、或 codex 自己出錯時會走到這裡,不能默默當成 PASS
        self.assertEqual(verify_pages.verdict_of("connection reset"), "ERR")
        self.assertEqual(verify_pages.verdict_of(""), "ERR")


class TestCases(unittest.TestCase):
    def test_跳過註解與空行(self):
        text = "# 說明\n\nHEAD:images/ep5/02.webp PASS 上線版本\n"
        self.assertEqual(verify_pages.parse_cases(text),
                         [("HEAD:images/ep5/02.webp", "PASS", "上線版本")])

    def test_回歸集有陽性也有負控制(self):
        cases = verify_pages.parse_cases(verify_pages.CASES.read_text(encoding="utf-8"))
        wants = [w for _, w, _ in cases]
        # 只有陽性的回歸集會把「什麼都判 FAIL」當成滿分規則
        self.assertIn("FAIL", wants)
        self.assertIn("PASS", wants)
        self.assertGreaterEqual(wants.count("PASS"), 5)


class TestRules(unittest.TestCase):
    def test_讀得到規則正文(self):
        rules = verify_pages.load_rules()
        self.assertIn("VERDICT: PASS", rules)
        self.assertIn("小鳥不啾", rules)

    def test_規則沒有把毛量當判準(self):
        # 毛量在這個畫風上是反指標:實測會放過出包版、誤殺修好版。
        # 規則裡出現「毛量」只能是在叫模型「不要用」。
        for line in verify_pages.load_rules().splitlines():
            if line.startswith(("A.", "C.", "D.")) and "毛量" in line:
                self.assertIn("不要用毛量", line)


class TestContext(unittest.TestCase):
    """規則 B 要對照劇本才成立,所以劇本是接在規則後面送進去的。"""

    def test_有劇本就接在規則後面(self):
        out = verify_pages._with_context("規則", "PANEL 1: ...")
        self.assertIn("規則", out)
        self.assertIn("這一頁的劇本", out)
        self.assertIn("PANEL 1", out)

    def test_沒有劇本就原樣送(self):
        # 封面沒有對白,回歸集也不帶劇本;這時規則 B 會自己跳過,不能硬塞一個
        # 空的「劇本」進去讓模型拿空表去比對。
        self.assertEqual(verify_pages._with_context("規則", ""), "規則")


if __name__ == "__main__":
    unittest.main()
