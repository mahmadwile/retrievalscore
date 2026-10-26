"""retrievalscore —— 自检测试。

按查询词覆盖、来源可信度与新鲜度给检索结果打分，输出每一项的得分构成。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import retrievalscore  # noqa: E402


class TestRetrievalScore(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"title": "时间戳格式", "text": "iso 8601 时间戳 格式 解析",
             "url": "https://docs.python.org/library/datetime.html",
             "timestamp": 1760000000},
            {"title": "别博客", "text": "时间戳随便记",
             "url": "https://blog.example.com/time",
             "timestamp": 1600000000},
        ]

    def test_ranking_is_ordered_by_score(self):
        results = retrievalscore.rank("时间戳 格式", self.candidates, retrievalscore.DEFAULT_CONFIG)
        self.assertEqual(results[0]["rank"], 1)
        self.assertIn("docs.python.org", results[0]["url"])

    def test_score_parts_are_exposed(self):
        results = retrievalscore.rank("时间戳", self.candidates, retrievalscore.DEFAULT_CONFIG)
        parts = results[0]["parts"]
        for key in ("coverage", "credibility", "freshness"):
            self.assertIn(key, parts)
            self.assertIn("score", parts[key])
            self.assertIn("detail", parts[key])

    def test_credibility_falls_back_to_default(self):
        score, source = retrievalscore.credibility_score("https://unknown.example/x",
                                                 retrievalscore.DEFAULT_CONFIG)
        self.assertEqual(source, "未登记的来源")
        self.assertAlmostEqual(score, retrievalscore.DEFAULT_CONFIG["credibility"]["default"])

    def test_unknown_source_is_not_awarded_top_score(self):
        """防呆：没登记的来源不能拿到最高可信度。"""
        score, _ = retrievalscore.credibility_score("https://unknown.example/x",
                                            retrievalscore.DEFAULT_CONFIG)
        best = max(v for k, v in retrievalscore.DEFAULT_CONFIG["credibility"].items()
                   if k != "default")
        self.assertLess(score, best)

    def test_empty_candidate_list(self):
        results = retrievalscore.rank("x", [], retrievalscore.DEFAULT_CONFIG)
        self.assertEqual(results, [])
