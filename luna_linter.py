#!/usr/bin/env python3
import argparse
import re
import os
import sys

import Levenshtein

from luna.translation_db import TranslationDb
from luna.constants import Constants
from luna.ruby_utils import RubyUtils


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
        "Akiha",
        "Ando",
        "Aoko",
        "Arach",
        "Arcueid",
        "Arihiko",
        "Arima",
        "Ciel",
        "Gouto",
        "Hisui",
        "Karius",
        "Kohaku",
        "Makihisa",
        "Mario",
        "Mio",
        "Noel",
        "Roa",
        "Saiki",
        "Satsuki",
        "Shiki",
        "Tohno",
        "Vlov",
        "Yumizuka",
    ]

    TYPO_EXCLUDE = set([
        'And',   # Triggers false positives on Ando
        'undo',  # Triggers false positives on Ando
        'Miss',  # Triggers false positives on Mio
    ])

    NAME_THRESH = 2

    def __init__(self):
        # Construct name permutations
        # Note that ' is stripped, so posessive and plurals are both covered by
        # the postfix 's'
        self._names = set()
        for name in self.BASE_NAMES:
            self._names.add(name)
            self._names.add(name + 's')

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

                    for name in self._names:

                        if Levenshtein.distance(word, name) < self.NAME_THRESH:
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
        'rumour': 'rumor',
        'rumours': 'rumors',
        'colour': 'color',
        'colours': 'colors',
        'defence': 'defense',
        'self-defence': 'self-defense',
        'offence': 'offense',
        'speciality': 'specialty',
        'realise': 'realize',
        'realising': 'realizing',
        'woah': 'whoa',
        'favourable': 'favorable',
        'favour': 'favor',
        'favourite': 'favorite',
        'towards': 'toward',
        'leaped': 'leapt',  # Exception since leaped looks dumb
        'anyways': 'anyway',
        'licence': 'license',
        'behaviour': 'behavior',
        'behaviours': 'behaviors',
        'honour': 'honor',
        'honours': 'honors',
        'focussing': 'focusing',
        'apologise': 'apologize',
        'apologising': 'apologizing',
        'apologised': 'apologized',
        'licence': 'license',
        'afterwards': 'afterward',
        'mobile phone': 'cell phone',
        'demeanour': 'demeanor',
        'street light': 'streetlight',
        'focussed': 'focused',
        'fulfil': 'fulfill',
        'fulfilment': 'fulfillment',
        'neighbouring': 'neighboring',
        'neighbouring': 'neighboring',
        'marvelled': 'marveled',
        'marvelling': 'marveling',
        'ageing': 'aging',
        'judgement': 'judgment',
    }

    def alpha_only(self, word):
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
                for raw_word in line.split(' '):
                    word = self.alpha_only(raw_word)
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


class LintChoiceLeadingSpace:
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
                # For glued lines, erase the trailing \n on the line before
                if cmd.is_glued:
                    page_text = page_text[:-2] + self._text_map[cmd.offset]
                else:
                    page_text += self._text_map[cmd.offset]

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


class LintVerbotenUnicode:
    VERBOTEN = {
        '　': ' ',
        '…': '...',
        '“': '"',
        '”': '"',
        '’': '\'',
        '、': ',',
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
                    if not words[i]:
                        continue
                    word_same = words[i] == words[i + 1]
                    word_punctuated = (
                        words[i][-1] == '.' or
                        words[i][-1] == '?' or
                        words[i][-1] == '!' or
                        words[i][-1] == ','
                    )
                    if word_same and not word_punctuated:
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
        print(
            Color(Color.RED)(
                f"{result.linter}: {result.filename}: {result.page}\n") +
            f"{indent}" +
            Color(Color.YELLOW)(f"{result.line}\n") +
            Color(Color.CYAN)(f"\t{result.message}\n")
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
        LintChoiceLeadingSpace(),
        LintPageOverflow(tl_db),
        LintNameMisspellings(),
        LintDupedWord(),
    ]

    # Iterate each scene
    for scene in tl_db.scene_names():
        lint_results += process_scene(tl_db, linters, scene)

    report_results(lint_results)
    sys.exit(1 if lint_results else 0)


if __name__ == '__main__':
    main()
