import unittest

from luna.ruby_utils import RubyUtils


class LinebreakTests(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxDiff = None

    @staticmethod
    def break_text(text):
        return RubyUtils.linebreak_text(
            RubyUtils.apply_control_codes(text), 55, 0)

    def test_line_break_at_55_chars_text_after(self):
        in_str = (
            "Ambivalent Glasses-kun STRIKE! "
            "And thus you enter this%{n}rescue corner."
        )
        expect_str = (
            "Ambivalent Glasses-kun STRIKE! And thus you enter this\n"
            "rescue corner."
        )
        self.assertEqual(self.break_text(in_str), expect_str)

    def test_line_break_exact(self):
        in_str = (
            "and forcefully grab her by the arm."
        )
        expect_str = (
            "\nand forcefully grab her by the arm."
        )
        result = RubyUtils.linebreak_text(
            RubyUtils.apply_control_codes(in_str), 55, 55)
        self.assertEqual(expect_str, result)

    def test_line_break_at_55_chars_dangling(self):
        in_str = \
            "You, are you perhaps new to this kind of adult corner?%{n}"
        expect_str = \
            "You, are you perhaps new to this kind of adult corner?\n"
        self.assertEqual(self.break_text(in_str), expect_str)

    def test_line_break_resets_counter(self):
        in_str = (
            "How come you're an instructor when it says%{n}"
            "\"sensei\" in the title?"
        )
        expect_str = (
            "How come you're an instructor when it says\n"
            "\"sensei\" in the title?"
        )
        self.assertEqual(self.break_text(in_str), expect_str)

    def test_line_break_literal_percent(self):
        in_str = "This is a % symbol"
        self.assertEqual(self.break_text(in_str), in_str)

    def test_linebreak_with_ruby(self):
        in_str = (
            "<Death by Immolation|B l a z e         >. "
            "<Death by Sickness|S i c k            >. "
            "<Death by Bloodloss|B l a d e          >. "
            "<Death by Collision|B r e a k           >. "
            "<Death of Mind|L o s t        >. "
            "<Death by Torture|P a i n          >. "
            "<Death by Conviction|P u n i s h          >."
        )
        expect_str = (
            "<Death by Immolation|B l a z e         >. "
            "<Death by Sickness|S i c k            >.\n"
            "<Death by Bloodloss|B l a d e          >. "
            "<Death by Collision|B r e a k           >. "
            "<Death of Mind|L o s t        >.\n"
            "<Death by Torture|P a i n          >. "
            "<Death by Conviction|P u n i s h          >."
        )
        self.assertEqual(self.break_text(in_str), expect_str)

    def test_linebreak_single_quote(self):
        in_str = '"'
        out_str = RubyUtils.linebreak_text(in_str, 55, 54)
        self.assertEqual(in_str, out_str)

    def test_linebreak_stupidly_long_word(self):
        in_str = (
            "Haa...haaaaaa, gyarghhhhhhhhhh?! "
            "Sto, stop, I'm sorry, so sorry, I apologize, I apologize, so "
            "pleaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaoaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaase!"
        )
        expect_str = (
            "Haa...haaaaaa, gyarghhhhhhhhhh?! Sto, stop, I'm sorry,\n"
            "so sorry, I apologize, I apologize, so pleaaaaaaaaaaaaa\n"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaoaaaaa\n"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaase!"
        )
        out_str = RubyUtils.linebreak_text(in_str, 55)
        self.assertEqual(expect_str, out_str)

    def test_linebreak_different_stupidly_long_sentence(self):
        in_str = '"Arghhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh!!!!! Sto, stop, stoooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooop! Aghrhhhh, gharkkkkkkkkkkkkkkkkkkkkkkkkkkk!!!!"'
        expect_str = (
            '"Arghhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh\n'
            'hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh!!!!! Sto, stop, stoo\n'
            'ooooooooooooooooooooooooooooooooooooooooooooooooooooooo\n'
            'ooooooooooooooooooop! Aghrhhhh,\n'
            'gharkkkkkkkkkkkkkkkkkkkkkkkkkkk!!!!"'
        )
        out_str = RubyUtils.linebreak_text(in_str, 55)
        self.assertEqual(expect_str, out_str)
