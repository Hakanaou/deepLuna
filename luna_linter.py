#!/usr/bin/env python3
import argparse
import re
import os
import sys

from luna.translation_db import TranslationDb
from luna.constants import Constants


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


class LintAmericanSpelling:

    BRIT_TO_YANK = {
        'rumour': 'rumor',
        'rumours': 'rumors',
        'colour': 'color',
        'colours': 'colors',
        'defence': 'defense',
        'offence': 'offense',
        'speciality': 'specialty',
        'realise': 'realize',
        'realising': 'realizing',
        'woah': 'whoa',
        'favourable': 'favorable',
        'favour': 'favor',
        'towards': 'toward',
        'leaped': 'leapt',  # Exception since leaped looks dumb
        'anyways': 'anyway',
    }

    def __call__(self, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                for word in line.split(' '):
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
    def __call__(self, scene_name, pages):
        # For each page, just do a dumb check that the quote count is matched
        errors = []
        for page in pages:
            # If any of the lines aren't actually translated, just abort
            if any([line is None for line, comment in page]):
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


class LintDanglingCommas:
    def __call__(self, scene_name, pages):
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
    }

    def __call__(self, scene_name, pages):
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
    def __call__(self, scene_name, pages):
        errors = []
        for page in pages:
            for line, comment in page:
                if not line:
                    continue
                if ignore_linter(self.__class__.__name__, comment):
                    continue
                match = re.search(r"<([\w\s]+)\|([\w\s]+)>", line)
                if match:
                    ruby = match.group(2)
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


def process_scene(tl_db, scene):
    # Convert the scene to a list of pages, where each page
    # is a list of strings
    script_cmds = tl_db.lines_for_scene(scene)
    pages = []
    page_acc = []
    current_page = None
    for cmd in script_cmds:
        if cmd.page_number != current_page:
            if page_acc:
                pages.append(page_acc)
            page_acc = []
            current_page = cmd.page_number

        page_acc.append((
            tl_db.tl_line_with_hash(cmd.jp_hash).en_text,
            tl_db.tl_line_with_hash(cmd.jp_hash).comment,
        ))

    if page_acc:
        pages.append(page_acc)

    # Run it through each of the linters
    linters = [
        LintAmericanSpelling(),
        LintUnclosedQuotes(),
        LintDanglingCommas(),
        LintVerbotenUnicode(),
        LintUnspacedRuby(),
    ]

    lint_results = []
    for linter in linters:
        lint_results += linter(scene, pages)

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

    # Import the script
    candidate_files = []
    for basedir, dirs, files in os.walk(args.script_path):
        for filename in files:
            # Ignore non-text files
            if not filename.endswith(".txt"):
                continue

            candidate_files.append(os.path.join(basedir, filename))

    (consolidated_diff, conflicts) = \
        tl_db.parse_update_file_list(candidate_files)

    # Apply non-conflict data immediately
    tl_db.apply_diff(consolidated_diff, allow_creation=True)

    # If there are conflicts, well that's a lint error
    lint_results = []
    if conflicts:
        for sha, candidates in conflicts.items():
            line = tl_db.tl_line_with_hash(sha)
            msg = f"JP Line: {line.jp_text.rstrip()}\n\tImported candidates:\n"
            for filename, en_text, comment in candidates:
                msg += (
                    f"\t{os.path.basename(filename)}: {en_text} "
                    f"// {comment.rstrip()}\n"
                    if comment else
                    f"\t{os.path.basename(filename)}: {en_text}\n"
                )
            lint_results.append(LintResult(
                'LintImportConflicts',
                'None',
                -1,
                f"Conflict for line {sha}:",
                msg[:-1]
            ))

    # Iterate each scene
    for scene in tl_db.scene_names():
        lint_results += process_scene(tl_db, scene)

    report_results(lint_results)
    sys.exit(1 if lint_results else 0)


if __name__ == '__main__':
    main()