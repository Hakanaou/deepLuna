#!/usr/bin/env python3
import argparse
import re
import os
import sys

import Levenshtein

from luna.translation_db import TranslationDb
from luna.constants import Constants
from luna.ruby_utils import RubyUtils

RubyUtils.ENABLE_PUA_CODES = True


class Color:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    ENDC = '\033[0m'

    def __init__(self, color):
        self.color = color

    def __call__(self, text):
        return f"{self.color}{text}{Color.ENDC}"


class LintResult:

    def __init__(self, linter, scene_name, page, line, message):
        self.linter = linter
        self.filename = scene_name
        self.page = page
        self.line = line
        self.message = message

    def __repr__(self):
        return (
            f"{self.linter}: {self.filename}: {self.page}:\n"
            f"\t\"{self.line}\"\n\t{self.message}"
        )


def ignore_linter(linter_name, line_comment):
    # No comment means no lint-off comment
    if not line_comment:
        return False

    # Does the comment contain a lint-off pragma for this linter?
    comment = line_comment.lower()
    search = f'lint-off:{linter_name}'.lower()
    return search in comment


class LintNameMisspellings:

    BASE_NAMES = [
        "Ahnenerbe",
        "Akiha",
        "Andou",
        "Andrei",
        "Aoko",
        "Arach",
        "Arcueid",
        "Argaleon",
        "Arihiko",
        "Arima",
        "Bestino",
        "Brunestud",
        "Ciel",
        "Gallo",
        "Godbivouac",
        "Gouto",
        "Granfatima",
        "Hisui",
        "Inui",
        "Karius",
        "Kiara",
        "Kisshouin",
        "Kohaku",
        "Makihisa",
        "Mario",
        "Messiaen",
        "Mio",
        "Narbareck",
        "Noel",
        # "Noi", Doesn't come up much and generates too many false positives
        "Roa",
        "Saiki",
        "Satsuki",
        "Seonator",
        "Shiki",
        "Tohno",
        "Vlov",
        "Yumizuka",
    ]

    TYPO_EXCLUDE = set([
        'Miss',  # Triggers false positives on Mio
    ])

    NAME_THRESH = 2

    def __init__(self):
        # Construct name permutations
        # Note that ' is stripped, so posessive and plurals are both covered by
        # the postfix 's'
        self._names = set()
        self._name_freqmaps = {}
        for name in self.BASE_NAMES:
            self._names.add(name)
            self._names.add(name + 's')

        for name in self._names:
            self._name_freqmaps[name] = self.make_freqmap(name)

    def make_freqmap(self, word):
        ret = {}
        for char in word:
            ret[char] = ret.get(char, 0) + 1

        return ret

    def depunctuate(self, word):
        return ''.join([
            c for c in word
            if (c >= 'A' and c <= 'Z')
            or (c >= 'a' and c <= 'z')
        ])

    def multisplit(self, string, sep_list):
        ret = []
        acc = ""
        for c in string:
            if c in sep_list:
                ret.append(acc)
                acc = ""
            else:
                acc += c

        if acc:
            ret.append(acc)

        return ret

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                line = RubyUtils.apply_control_codes(line)
                for raw_word in self.multisplit(line, ' -―\n'):
                    word = self.depunctuate(raw_word)

                    # If it's a correct spelling, skip
                    if word in self._names or word in self.TYPO_EXCLUDE:
                        continue

                    # Check edit distance
                    for name in self._names:
                        if Levenshtein.distance(word, name) < self.NAME_THRESH:
                            errors.append(LintResult(
                                self.__class__.__name__,
                                scene_name,
                                page[0],
                                line,
                                f"Is '{word}' supposed to be '{name}'"
                            ))

                    # Check transpositions
                    word_freqmap = self.make_freqmap(word)
                    for name, freqmap in self._name_freqmaps.items():
                        if word_freqmap == freqmap:
                            errors.append(LintResult(
                                self.__class__.__name__,
                                scene_name,
                                page[0],
                                line,
                                f"Is '{word}' supposed to be '{name}'"
                            ))

        return errors


class LintAmericanSpelling:

    BRIT_TO_YANK = {
        'absent-mindedly': 'absentmindedly',
        'absentminded': 'absent-minded',
        'afterwards': 'afterward',
        'ageing': 'aging',
        'anaesthesia': 'anesthesia',
        'anaesthetics': 'anesthetics',
        'anyways': 'anyway',
        'apologise': 'apologize',
        'apologised': 'apologized',
        'apologising': 'apologizing',
        'behaviour': 'behavior',
        'behaviours': 'behaviors',
        'cafe': 'café',
        'cancelled': 'canceled',
        'cancelling': 'canceling',
        'civilisation': 'civilization',
        'cliche': 'cliché',
        'colour': 'color',
        'colours': 'colors',
        'counselling': 'counseling',
        'counsellor': 'counselor',
        'defence': 'defense',
        'defenceless': 'defenseless',
        'defences': 'defenses',
        'demeanour': 'demeanor',
        'endeavour': 'endeavor',
        'favour': 'favor',
        'favourable': 'favorable',
        'favourite': 'favorite',
        'focussed': 'focused',
        'focussing': 'focusing',
        'forwards': 'forward',
        'fulfil': 'fulfill',
        'fulfilment': 'fulfillment',
        'furore': 'furor',
        'grey': 'gray',
        'grovelling': 'groveling',
        'hand-made': 'handmade',
        'harbour': 'harbor',
        'honour': 'honor',
        'honours': 'honors',
        'jeez': 'geez',
        'judgement': 'judgment',
        'labelled': 'labeled',
        'laboured': 'labored',
        'leaped': 'leapt',  # Exception since leaped looks dumb
        'levelled': 'leveled',
        'licence': 'license',
        'licence': 'license',
        'lifeform': 'life-form',
        'light-hearted': 'lighthearted',
        'lightheaded': 'light-headed',
        'lightheadedness': 'light-headedness',
        'marvelled': 'marveled',
        'marvelling': 'marveling',
        'mesmerised': 'mesmerized',
        'miniscule': 'minuscule',
        'mobile phone': 'cell phone',
        'modelled': 'modeled',
        'naive': 'naïve',
        'naivete': 'naïveté',
        'neighbourhood': 'neighborhood',
        'neighbouring': 'neighboring',
        'neighbouring': 'neighboring',
        'offence': 'offense',
        'realise': 'realize',
        'realising': 'realizing',
        'revelled': 'reveled',
        'rumour': 'rumor',
        'rumours': 'rumors',
        'saviour': 'savior',
        'self-defence': 'self-defense',
        'self-defence': 'self-defense',
        'shrivelling': 'shriveling',
        'signalling': 'signaling',
        'skilful': 'skillful',
        'skilfully': 'skillfully',
        'speciality': 'specialty',
        'spiralling': 'spiraling',
        'street light': 'streetlight',
        'theatre': 'theater',
        'towards': 'toward',
        'travelled': 'traveled',
        'travelling': 'traveling',
        'unravelling': 'unraveling',
        'washroom': 'bathroom',
        'woah': 'whoa',
    }

    def strip_irrelevant_punct(self, word):
        return ''.join([
            c for c in word
            if (c >= 'A' and c <= 'Z')
            or (c >= 'a' and c <= 'z')
            or c in '-'
        ])

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                for raw_word in line.split(' '):
                    word = self.strip_irrelevant_punct(raw_word)
                    if word.lower() in self.BRIT_TO_YANK:
                        subs = self.BRIT_TO_YANK[word.lower()]
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Replace '{word}' with '{subs}'"
                        ))

        return errors


class LintEmDashes:
    # Dangling interruptions are 3x CJK dash
    # Em-dashes within sentences are 2x CJK dash

    CJK_DASH = '―'

    PUNCTUATION = set("\"\' .―")

    def __call__(self, db, scene_name, pages):
        errors = []

        # Grab the actual scripting for this scene so we can detect glue cases
        script_cmds = db.lines_for_scene(scene_name)

        cmd_idx = 0
        while cmd_idx < len(script_cmds):
            # Fetch the translation
            page_number = script_cmds[cmd_idx].page_number
            line = db.tl_line_for_cmd(script_cmds[cmd_idx])
            line_text = line.en_text or ''
            cmd_idx += 1

            # Continue to append any subsequent cmds if they are glued
            lint_off = ignore_linter(self.__class__.__name__, line.comment)
            while cmd_idx < len(script_cmds) and script_cmds[cmd_idx].is_glued:
                line = db.tl_line_for_cmd(script_cmds[cmd_idx])
                lint_off = (
                    lint_off or
                    ignore_linter(self.__class__.__name__, line.comment)
                )
                line_text += line.en_text or ''
                cmd_idx += 1

            # If any of the included lines has a lint-off, skip
            if lint_off:
                continue

            # Save a copy of the original text for messages
            raw_line_text = line_text

            # If this line isn't translated, we can't lint properly
            if not line_text:
                continue

            # Does this line not contain any u2015?
            if self.CJK_DASH not in line_text:
                continue

            # Strip out any game engine control codes / newlines
            line_text = re.sub('%{[\w/]*}', '', line_text)
            line_text = re.sub('@.', '', line_text)
            line_text = re.sub('\n', ' ', line_text)

            # Strip leading spaces since it's valid to have padded triple
            # dash lead-ins, as well as any trailing spaces since lines can't
            # have trailing whitespace
            line_text = line_text.strip()

            # Does it consist of _only_ dashes or punctuation?
            chars = set(line_text)
            if chars.difference(self.PUNCTUATION) == set():
                continue

            # Strip out any quotes and exclamation marks from this text because
            # leading/trailing dashes inside quotes / ?! still count
            line_text = ''.join([c for c in line_text if c not in set("\"'?!")])

            # If it ends with one, check how many it ends with
            # If it _does_ contain dashes, filter them into groups of inter-text
            # and post-text
            ending_dash_count = 0
            if line_text.endswith(self.CJK_DASH):
                for i in range(len(line_text), 0, -1):
                    if line_text[i - 1] == self.CJK_DASH:
                        ending_dash_count += 1
                    else:
                        break

                if ending_dash_count != 3:
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page_number,
                        raw_line_text,
                        "Line should end with 3x CJK dash, not "
                        f"'{line_text[-ending_dash_count:]}'"
                    ))

            # Now do the same again for starting dashes
            starting_dash_count = 0
            if line_text.startswith(self.CJK_DASH):
                for i in range(len(line_text)):
                    if line_text[i] == self.CJK_DASH:
                        starting_dash_count += 1
                    else:
                        break

                if starting_dash_count != 3:
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page_number,
                        raw_line_text,
                        "Line should start with 3x CJK dash, not "
                        f"'{raw_line_text[:starting_dash_count]}'"
                    ))


            # Snip those off so we con't count em again
            remaining_text = line_text
            if ending_dash_count:
                remaining_text = remaining_text[:-ending_dash_count]
            if starting_dash_count:
                remaining_text = remaining_text[starting_dash_count:]

            # Now split that text into any other groups of CJK dashes that exist
            dash_groups = []
            acc = ''
            for c in remaining_text:
                if c == self.CJK_DASH:
                    # Beginning of new dash group
                    acc += c
                    continue

                # If this ends the group, is the group a 2x?
                if acc and len(acc) != 2:
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page_number,
                        raw_line_text,
                        "Em-dashes should be represented as 2x CJK dash, "
                        f"not {len(acc)}"
                    ))

                acc = ''

        return errors

class LintBannedPhrases:
    # Map of (search, case_sensitive) -> replace
    BANNED_PHRASES = {
        ('curry bread', False): 'curry bun',
        ('head to head', False): 'head-to-head',
        ('pile driver', False): 'pile bunker',
        ('piledriver', False): 'pile bunker',
        ('pile-driver', False): 'pile bunker',
        ('white woman', False): 'woman in white',
        ('white avatar', False): 'avatar in white',
        ('blonde boy', False): 'blond boy',
        ('face to face', False): 'face-to-face',
        ('hard-headed', False): 'hardheaded',
        ('sub-par', False): 'subpar',
        ('get-up', False): 'getup',
        ('cold-hearted', False): 'coldhearted',
        ('sugar coat', False): 'sugarcoat',
        ('after-effects', False): 'aftereffects',
        ('off-beat', False): 'offbeat',
        ('brand new', False): 'brand-new',
        ('shockwave', False): 'shock wave',

        # Need to handle sentence start explicitly on these since we're case-sen
        ('what on Earth', True): 'what on earth',
        ('What on Earth', True): 'What on earth',
        ('how on Earth', True): 'how on earth',
        ('How on Earth', True): 'How on earth',
        ('down to Earth', True): 'down to earth',
        ('Down to Earth', True): 'Down to earth',

        # Lore terms that must be capitalized
        ('acting presbyter', True): 'Acting Presbyter',
        ('baptismal rite', True): 'Baptismal Rite',
        ('black key', True): 'Black Key',
        ('black keys', True): 'Black Keys',
        ('burial agency', True): 'Burial Agency',
        ('conceptual weapon', True): 'Conceptual Weapon',
        ('dead apostle', True): 'Dead Apostle',
        (' ether ', True): 'Ether',  # Too fragmentary to be effective
        ('executor', True): 'Executor',
        ('Grand Magecraft', True): 'grand magecraft',
        ('hemonomic principle', True): 'Hemonomic Principle',
        ('holy church', True): 'Holy Church',
        ('inversion impulse', True): 'Inversion Impulse',
        ('lifescale', True): 'Lifescale',
        ('mages association', True): 'Mages Association',
        ('magic circuit', True): 'Magic Circuit',
        ('marble phantasm', True): 'Marble Phantasm',
        ('mystic code ', True): 'Mystic Code',
        ('mystic eyes', True): 'Mystic Eyes',
        ('nightkin', True): 'Nightkin',
        ('numeromancy', True): 'Numeromancy',
        ('plating effect', True): 'Plating Effect',
        ('sacrament assembly', True): 'Sacrament Assembly',
        ('scriptural weapon', True): 'Scriptural Weapon',
        ('scriptural weapons', True): 'Scriptural Weapons',
        ('suzerain', True): 'Suzerain',
        ('true ancestor', True): 'True Ancestor',

        # 南口 / 北口 are really more like areas than points in space.
        # They should be blended more fluently with the sentence.
        ('north gate', False): 'plaza north of the station, etc.',
        ('south gate', False): 'plaza south of the station, etc.',

        # Uncomment when everything else has been merged down
        ('...!', False): 'No ellipses before exclamation marks.',
        ('...?!', False): 'No ellipses before exclamation marks.',
    }

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                lower_line = line.lower()
                for findspec, replace in self.BANNED_PHRASES.items():
                    needle, case_sensitive = findspec
                    if needle in (line if case_sensitive else lower_line):
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Replace '{needle}' with '{replace}'"
                        ))

        return errors


class LintInterrobang:
    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                if '!?' in line:
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page[0],
                        line,
                        "Replace '!?' with '?!'"
                    ))

        return errors


class LintUnclosedQuotes:
    def __call__(self, db, scene_name, pages):
        # For each page, just do a dumb check that the quote count is matched
        errors = []
        for page in pages:
            # If any of the lines aren't actually translated, just abort
            if any([line is None for line, comment in page]):
                continue

            # If any of the lines in the page contain a lint-off pragma, skip
            lint_ignored = any([
                ignore_linter(self.__class__.__name__, comment)
                for (line, comment) in page
            ])
            if lint_ignored:
                continue

            raw_text = [line for line, _comment in page if line]
            quote_count = len([c for c in ''.join(raw_text) if c == '"'])
            if quote_count & 1:
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    page[0],
                    '\n'.join(f"\t> {line}" for line, _comment in page),
                    f"Found odd number of quotes ({quote_count})"
                ))

        return errors


class LintBrokenFormatting:
    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue

                if ignore_linter(self.__class__.__name__, comment):
                    continue

                try:
                    RubyUtils.apply_control_codes(
                        line, enable_asserts=True)
                except AssertionError as e:
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page[0],
                        line,
                        e.args[0]
                    ))

        return errors


class LintChoices:

    # Full line is 55 chars, subtract 2 for choice number
    MAX_CHOICE_LEN = 53

    def __call__(self, db, scene_name, pages):
        errors = []

        # Get the actual script cmds for this one
        script_cmds = db.lines_for_scene(scene_name)

        # Filter for choices
        choice_cmds = [cmd for cmd in script_cmds if cmd.is_choice]

        # Scan for lint breakers
        for cmd in choice_cmds:
            line = db.tl_line_for_cmd(cmd)
            if not line.en_text:
                continue

            # No leading space?
            if line.en_text[0] != ' ':
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    cmd.page_number,
                    line.en_text,
                    "Choice text must begin with leading space"
                ))

            # Starts with an ellipsis?
            if line.en_text.strip().startswith('...'):
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    cmd.page_number,
                    line.en_text,
                    "Choice text should not begin with ellipsis"
                ))

            # Too long?
            # Auto-ignore this one if it's the last choice in the scene, in
            # which case it doesn't overflow onto anything
            is_last_choice = cmd == choice_cmds[-1]
            line_len = RubyUtils.noruby_len(
                RubyUtils.apply_control_codes(line.en_text))
            is_overlong = line_len > self.MAX_CHOICE_LEN
            if not is_last_choice and is_overlong:
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    cmd.page_number,
                    line.en_text,
                    f"Choice too long, must be < {self.MAX_CHOICE_LEN} chars"
                ))

        return errors


class LintPageOverflow:

    MAX_LINES_PER_PAGE = 12

    def __init__(self, db):
        # Pregenerate text map so we don't incur it on every __call__
        self._text_map = db.generate_linebroken_text_map()

    def __call__(self, db, scene_name, _pages):
        errors = []

        # Ignore the orphan line file
        if scene_name == 'ORPHANED_LINES':
            return errors

        # Get the script cmds
        script_cmds = db.lines_for_scene(scene_name)

        # Paginate
        page_cmds = paginate(script_cmds)

        # For each page, check if when linebroken it ends up too long
        for page in page_cmds:
            # Do we skip this page?
            is_lint_ignored = any([
                ignore_linter(self.__class__.__name__,
                              db.tl_line_for_cmd(cmd).comment)
                for cmd in page
            ])
            if is_lint_ignored:
                continue

            # Consolidate the page text into one string
            page_text = ""
            for cmd in page:
                # Fetch the matching string
                line = self._text_map[cmd.offset]

                # Remove any game control codes from the front of the string
                while line[0] == '@':
                    line = line[2:]

                # For glued lines, erase the trailing \n on the line before
                if cmd.is_glued:
                    page_text = page_text[:-2] + line
                else:
                    page_text += line

            # Don't count the trailing newline
            page_text = page_text.rstrip()

            page_lines = len(page_text.split("\n"))
            if page_lines > self.MAX_LINES_PER_PAGE:
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    page[0].page_number,
                    page_text,
                    f"Page too long (is {page_lines}, "
                    f"max is {self.MAX_LINES_PER_PAGE})"
                ))

        return errors


class LintTranslationHoles:
    """
    If a file is _mostly_ translated but has some untranslated strings in it
    it's possible they got skipped by accident.
    """

    LIKELY_TRANSLATED_THRESH = 0.8

    def __call__(self, db, scene_name, pages):
        # What % of lines in this scene are TL'd?
        total_tl_count = 0
        total_line_count = 0
        for page in pages:
            for line, comment in page:
                total_line_count += 1
                if line:
                    total_tl_count += 1

        # If this file doesn't look translated, or is 100% tl'd, just return
        translation_ratio = total_tl_count / total_line_count
        mostly_translated = translation_ratio > self.LIKELY_TRANSLATED_THRESH
        fully_translated = total_tl_count == total_line_count
        if not mostly_translated or fully_translated:
            return []

        # Go accumulate the lines that aren't TLd, have to actually re-fetch
        # from DB to get the line IDs
        script_cmds = db.lines_for_scene(scene_name)
        untranslated_cmds = []
        for cmd in script_cmds:
            line = db.tl_line_for_cmd(cmd)
            if not line.en_text:
                untranslated_cmds.append(cmd)

        line_report = (
            f'Scene is {translation_ratio*100:.1f}% translated, but has '
            f'{total_line_count - total_tl_count} missing lines'
        )
        for cmd in untranslated_cmds:
            if line_report:
                line_report += "\n"
            line_report += f"\t Sha: {cmd.jp_hash}, Offset: {cmd.offset}"

        # If this file is mostly translated but has holes, warn about it
        return [
            LintResult(
                self.__class__.__name__,
                scene_name,
                None,
                f'Scene {scene_name} has translation holes',
                line_report
            )
        ]


class LintDanglingCommas:
    def __call__(self, db, scene_name, pages):
        # QA has a lot of false positives for this, so maybe ignore for now
        if scene_name.startswith("QA_"):
            return []

        # If any of the lines aren't actually translated, just abort
        for page in pages:
            if any([line is None for line, comment in page]):
                return []

        # Check to see if the final line of the page ends in a , (or ,")
        errors = []
        for page in pages:
            last_line, last_comment = page[-1]
            if ignore_linter(self.__class__.__name__, last_comment):
                continue
            if last_line.endswith(",") or last_line.endswith(",\""):
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    page[0],
                    last_line,
                    "Final line ends in trailing ',', replace with CJK dashes '―――'"
                ))

        return errors


class LintConsistency:

    def __init__(self):
        # Compile regex for consistency check pragmas
        self._regex = re.compile(r'LintConsistency:(\d+)')

    def __call__(self, db, scene_name, pages):
        errors = []

        for page in pages:
            for line, comment in page:
                if not line or not comment:
                    continue

                # Check each referenced consistency point is in fact consistent
                for offset in self._regex.findall(comment):
                    other_jp_hash = db.tl_line_for_offset(int(offset))

                    # Need to make sure that we handle overrides correctly,
                    # since fetching those by hash won't work
                    other_line = db.tl_override_for_offset(int(offset)) or \
                        db.tl_line_with_hash(other_jp_hash)

                    if other_line.en_text != line:
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Line not consistent with offset {offset}:\n"
                            f"\t{other_line.en_text}"
                        ))

        return errors

class LintStartingEllipsis:

    PUNCTUATION = set("\"'.?!")

    def __call__(self, db, scene_name, pages):
        errors = []

        for page in pages:
            for line, comment in page:
                if not line:
                    continue

                if ignore_linter(self.__class__.__name__, comment):
                    continue

                # If there's no ellipsis in this line, skip it
                if '...' not in line:
                    continue

                # If it doesn't begin with an ellipsis (potentially in quotes)
                # then skip it
                starts_with_ellipsis = any([
                    line.startswith('...'),
                    line.startswith('"...'),
                    line.startswith('\'...'),
                ])
                if not starts_with_ellipsis:
                    continue

                # If this line starts with an ellipsis, but consists of nothing
                #_more_ than an ellipsis, let it slide
                if set(line).difference(self.PUNCTUATION) == set():
                    continue

                # If we got this far, it's a lint error
                errors.append(LintResult(
                    self.__class__.__name__,
                    scene_name,
                    page[0],
                    line,
                    "Lines should not start with ellipses"
                ))

        return errors

class LintEllipses:

    def __call__(self, db, scene_name, pages):
        errors = []

        for page in pages:
            for line, comment in page:
                if not line:
                    continue

                if ignore_linter(self.__class__.__name__, comment):
                    continue

                # Test lines for non-multiple-of-three periods
                consecutive_dots = 0
                for c in line:
                    if c == '.':
                        consecutive_dots += 1
                    if c != '.':
                        if consecutive_dots > 1 and consecutive_dots % 3 != 0:
                            errors.append(LintResult(
                                self.__class__.__name__,
                                scene_name,
                                page[0],
                                line,
                                "Non-multiple-of-three ellipsis"
                            ))
                        consecutive_dots = 0

                # Handle end-of-line case
                if consecutive_dots > 1 and consecutive_dots % 3 != 0:
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page[0],
                        line,
                        "Non-multiple-of-three ellipsis"
                    ))

        return errors


class LintVerbotenUnicode:
    VERBOTEN = {
        '　': ' ',
        '…': '...',
        '“': '"',
        '”': '"',
        '’': '\'',
        '、': ',',
        '！': '!',
        '？': '?',
    }

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                for find, replace in self.VERBOTEN.items():
                    if find in line:
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Replace '{find}' with '{replace}'"
                        ))

        return errors


class LintTimeFormat:

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue

                # Does this line have a colon-delimited time in it?
                matches = re.findall(r"(\d+:\d\d)", line)
                if not matches:
                    continue

                # Just assert that there's at least something in there
                if matches and not ('AM' in line or 'PM' in line):
                    errors.append(LintResult(
                        self.__class__.__name__,
                        scene_name,
                        page[0],
                        line,
                        f"Missing AM/PM marker on time {matches[0]}"
                    ))

        return errors


class LintRubyUnicode:
    """
    Text spacing inside ruby follows a different codepath, just prevent
    people using non-ascii in lolwer ruby blocks
    """

    @staticmethod
    def extract_ruby_pairs(line):
        pairs = []
        in_ruby_lower = False
        in_ruby_upper = False
        cur_lower = None
        cur_upper = None
        for c in line:
            if in_ruby_lower:
                if c == '|':
                    in_ruby_lower = False
                    in_ruby_upper = True
                    continue

                cur_lower += c
                continue

            if in_ruby_upper:
                if c == '>':
                    pairs.append((cur_lower, cur_upper))
                    in_ruby_upper = False
                    continue

                cur_upper += c
                continue

            if c == '<':
                in_ruby_lower = True
                cur_lower = ""
                cur_upper = ""

        return pairs

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue

                # Apply control codes so that we can detect font effects
                # inside ruby
                line = RubyUtils.apply_control_codes(line)

                # Find all ruby pairs in this line
                pairs = self.extract_ruby_pairs(line)
                for subtext, ruby in pairs:

                    unicode_chars = []
                    for c in subtext:
                        if ord(c) >= 128:
                            unicode_chars.append(c)

                    # Kinda OK if the top part has it, since ruby double-spaces
                    # things anyway
                    # for c in ruby:
                    #     if ord(c) >= 128:
                    #         unicode_chars.append(c)

                    if unicode_chars:
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Ruby '<{subtext}|{ruby}>' contains unicode "
                            f"({unicode_chars})"
                        ))

        return errors


class LintUnspacedRuby:
    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                pairs = re.findall(r"<([\w\s]+)\|([\w\s]+)>", line)
                for subtext, ruby in pairs:
                    spaced_ok = True
                    for i in range(len(ruby)-1):
                        if ruby[i] != ' ' and ruby[i+1] != ' ':
                            spaced_ok = False
                            break
                    if not spaced_ok:
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Ruby '{ruby}' is not 's p a c e d' properly"
                        ))

        return errors


class LintDupedWord:
    @staticmethod
    def alpha_only(word):
        return ''.join([
            c for c in word
            if (c >= 'A' and c <= 'Z')
            or (c >= 'a' and c <= 'z')
        ])

    def __call__(self, db, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue

                line = RubyUtils.remove_ruby_text(
                    RubyUtils.apply_control_codes(line)
                ).replace('\n', ' ')
                words = line.split(' ')
                for i in range(len(words)-1):
                    w_a = self.alpha_only(words[i])
                    w_b = self.alpha_only(words[i+1])
                    if not w_a or not w_b:
                        continue
                    word_same = w_a == w_b
                    first_word_punctuated = (
                        words[i][-1] == '.' or
                        words[i][-1] == '?' or
                        words[i][-1] == '!' or
                        words[i][-1] == ','
                    )
                    if word_same and not first_word_punctuated:
                        errors.append(LintResult(
                            self.__class__.__name__,
                            scene_name,
                            page[0],
                            line,
                            f"Word '{words[i]}' doubled up"
                        ))

        return errors


def paginate(script_cmds):
    pages = []
    page_acc = []
    current_page = None
    for cmd in script_cmds:
        if cmd.page_number != current_page:
            if page_acc:
                pages.append(page_acc)
            page_acc = []
            current_page = cmd.page_number

        page_acc.append(cmd)

    if page_acc:
        pages.append(page_acc)

    return pages


def process_scene(tl_db, linters, scene):
    # Convert the scene to a list of pages, where each page
    # is a list of strings
    script_cmds = tl_db.lines_for_scene(scene)
    paged_script_cmds = paginate(script_cmds)

    script_pages = [
        [(tl_db.tl_line_for_cmd(cmd).en_text,
          tl_db.tl_line_for_cmd(cmd).comment) for cmd in page]
        for page in paged_script_cmds
    ]

    lint_results = []
    for linter in linters:
        lint_results += linter(tl_db, scene, script_pages)

    return lint_results


def report_results(lint_results):
    if not lint_results:
        return

    for result in lint_results:
        indent = "\t" if (result.line and result.line[0] != '\t') else ""
        # Replace all PUA characters with normal ones for readability
        printable_line = ''.join([
            (c if ord(c) < 0xE000 else chr(ord(c) % 128)) for c in result.line
        ])
        printable_message = ''.join([
            (c if ord(c) < 0xE000 else chr(ord(c) % 128)) for c in result.message
        ])
        print(
            Color(Color.RED)(
                f"{result.linter}: {result.filename}: {result.page}\n") +
            f"{indent}" +
            Color(Color.YELLOW)(f"{printable_line}\n") +
            Color(Color.CYAN)(f"\t{printable_message}\n")
        )

    # Tally total hits for each linter
    linter_hits = {}
    for result in lint_results:
        linter_hits[result.linter] = linter_hits.get(result.linter, 0) + 1

    print("Total stats:")
    for linter, hits in linter_hits.items():
        print(f"\t{linter}: {hits}")


def main():
    # Arg parsing
    parser = argparse.ArgumentParser(
        description="deepLuna CLI"
    )
    parser.add_argument(
        '--db-path',
        dest='db_path',
        action='store',
        help="Path to translation DB file",
        default=Constants.DATABASE_PATH,
        required=True
    )
    parser.add_argument(
        '--script-path',
        dest='script_path',
        action='store',
        help="Path to translation DB file",
        default=Constants.DATABASE_PATH,
        required=True
    )

    # Load the DB
    args = parser.parse_args(sys.argv[1:])
    tl_db = TranslationDb.from_file(args.db_path)

    # Search for files to import
    candidate_files = []
    for basedir, dirs, files in os.walk(args.script_path):
        for filename in files:
            # Ignore non-text files
            if not filename.endswith(".txt"):
                continue

            candidate_files.append(os.path.join(basedir, filename))

    # Generate a diff
    import_diff = tl_db.parse_update_file_list(
        candidate_files, ignore_errors=False)

    # Apply non-conflict data immediately
    tl_db.apply_diff(import_diff)

    # If there are conflicts, well that's a lint error
    lint_results = []
    if import_diff.any_conflicts():
        for sha, entry_group in import_diff.entries_by_sha.items():
            # Ignore the non-conflicting entries
            if entry_group.is_unique():
                continue

            # Count the occurrences of each option
            deduped = {}  # (tl, comment) -> list(instances)
            for entry in entry_group.entries:
                key = (entry.en_text, entry.comment)
                if key not in deduped:
                    deduped[key] = []
                deduped[key].append(entry)

            line = tl_db.tl_line_with_hash(sha)
            msg = "Imported candidates:\n"
            for tl, comment in deduped:
                entry_list = deduped[(tl, comment)]
                entry = entry_list[0]
                extras = (
                    f" (and {len(entry_list)-1} others)"
                    if len(entry_list) > 1 else ""
                )
                basename = os.path.basename(entry.filename)
                msg += (
                    f"\t{basename}:L{entry.line}{extras}: "
                    f"{entry.en_text} "
                    f"// {entry.comment.rstrip()}\n"
                    if entry.comment else
                    f"\t{basename}:L{entry.line}{extras}: "
                    f"{entry.en_text}\n"
                )
            lint_results.append(LintResult(
                'LintImportConflicts',
                sha,
                len(entry_group.entries),
                f"JP line: {line.jp_text.rstrip()}",
                msg[:-1]
            ))

    # Run linter setup
    linters = [
        LintAmericanSpelling(),
        LintUnclosedQuotes(),
        LintDanglingCommas(),
        LintVerbotenUnicode(),
        LintUnspacedRuby(),
        LintTranslationHoles(),
        LintChoices(),
        LintPageOverflow(tl_db),
        LintNameMisspellings(),
        LintDupedWord(),
        LintBrokenFormatting(),
        LintEllipses(),
        LintStartingEllipsis(),
        LintConsistency(),
        LintInterrobang(),
        LintBannedPhrases(),
        LintEmDashes(),
        LintRubyUnicode(),
        LintTimeFormat(),
    ]

    # Iterate each scene
    for scene in tl_db.scene_names():
        lint_results += process_scene(tl_db, linters, scene)

    report_results(lint_results)
    sys.exit(1 if lint_results else 0)


if __name__ == '__main__':
    main()
