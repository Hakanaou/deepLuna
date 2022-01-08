import unittest
from collections import defaultdict

from luna.translation_db import TranslationDb


class LinebreakTests(unittest.TestCase):

    TC = TranslationDb.TextCommand
    JPS = 'a jp string'
    HASH = 'a content hash'

    def assert_parse_match(self, test_cmds, expected_output):
        cmds = TranslationDb.parse_script_cmds(
            test_cmds.encode('utf-8'),
            defaultdict(lambda: TranslationDb.TLLine('a jp string')),
            defaultdict(lambda: 'a content hash')
        )
        self.assertEqual(cmds, expected_output)

    def test_forced_newline_subsequent_line(self):
        self.assert_parse_match(
            "_ZMbc419($043897^$043898@n);",
            [
                self.TC(43897, self.HASH, 0, modifiers=["@n"],
                        has_forced_newline=True),
                self.TC(43898, self.HASH, 0, modifiers=["@n"])
            ]
        )

    def test_forced_newline_subsequent_line_glue(self):
        self.assert_parse_match(
            "_ZMbc419($043897^$043898@n);_MSAD($014370);",
            [
                self.TC(43897, self.HASH, 0, modifiers=["@n"],
                        has_forced_newline=True),
                self.TC(43898, self.HASH, 0, modifiers=["@n"]),
                self.TC(14370, self.HASH, 0, is_glued=True),
            ]
        )

    def test_forced_newline_dangling_glue(self):
        self.assert_parse_match(
            "_ZMbc419($043897^@n);_MSAD($014370);",
            [
                self.TC(43897, self.HASH, 0, modifiers=["@n"],
                        has_forced_newline=True),
                self.TC(14370, self.HASH, 0, is_glued=False),
            ]
        )

    def test_msad_glue(self):
        self.assert_parse_match(
            "_ZMbc419($043897@n);_MSAD($014370);",
            [
                self.TC(43897, self.HASH, 0, modifiers=["@n"],
                        has_forced_newline=False),
                self.TC(14370, self.HASH, 0, is_glued=True),
            ]
        )

    def test_x_glue(self):
        self.assert_parse_match(
            "_ZM0349a($001493@k@e);_ZM0349b(@x$001494);",
            [
                self.TC(1493, self.HASH, 0, modifiers=["@k", "@e"]),
                self.TC(1494, self.HASH, 0, modifiers=["@x"],
                        is_glued=True),
            ]
        )
