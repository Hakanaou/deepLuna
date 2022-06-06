#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import time

from luna.constants import Constants
from luna.translation_db import TranslationDb
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="deepLuna CLI"
    )

    parser.add_argument(
        '--db-path',
        dest='db_path',
        action='store',
        help="Path to translation DB file",
        default=Constants.DATABASE_PATH
    )

    parser.add_argument(
        '--extract-mrg',
        dest='do_extract',
        action='store_true',
        help="Regenerate DB from MRG files"
    )

    parser.add_argument(
        '--import',
        dest='import_path',
        action='store',
        help="Import update files from the specified path"
    )
    parser.add_argument(
        '--legacy-import',
        dest='legacy_import_path',
        action='store',
        help="Import legacy-style update files from the specified path"
    )
    parser.add_argument(
        '--reset-overrides',
        dest='reset_overrides',
        action='store_true',
        help='Clear offset override table before import'
    )
    parser.add_argument(
        '--interactive-import',
        dest='interactive_import',
        action='store_true',
        help='Prompt to resolve import conflicts'
    )
    parser.add_argument(
        '--strict-import',
        dest='strict_import',
        action='store_true',
        help="Exit with error if import has conflicts"
    )
    parser.add_argument(
        '--delete',
        dest='delete',
        action='store_true',
        help="Delete files after importing"
    )

    parser.add_argument(
        '--inject',
        dest='do_inject',
        action='store_true',
        help="Inject the current translation DB into a new script_text.mrg"
    )
    parser.add_argument(
        '--inject-output',
        dest='inject_output',
        action='store',
        help="Output path for the injected script text"
    )
    parser.add_argument(
        '--enable-pua',
        dest='enable_pua',
        action='store_true',
        help="Enable font effects using PUA code region"
    )

    parser.add_argument(
        '--export',
        dest='export_path',
        action='store',
        help="Output path for the exported script text"
    )

    parser.add_argument(
        '--no-save',
        dest='no_save',
        action='store_true',
        help="Do not save the luna database after processing"
    )

    return parser.parse_args(sys.argv[1:])


def import_mergetool(tl_db, import_diff):
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

        # Generate candidate list
        line = tl_db.tl_line_with_hash(sha)
        msg = "Imported candidates:\n"
        idx = 0
        numbered_choices = []
        for tl, comment in deduped:
            entry_list = deduped[(tl, comment)]
            entry = entry_list[0]
            extras = (
                f" (and {len(entry_list)-1} others)"
                if len(entry_list) > 1 else ""
            )
            basename = os.path.basename(entry.filename)
            msg += (
                f"{idx}. {basename}:L{entry.line}{extras}: "
                f"{entry.en_text} "
                f"// {entry.comment.rstrip()}\n"
                if entry.comment else
                f"{idx}. {basename}:L{entry.line}{extras}: "
                f"'{entry.en_text}'\n"
            )
            numbered_choices.append(entry)
            idx += 1

        print(
            Color(Color.RED)(f"Import conflict for line {sha}:\n") +
            Color(Color.YELLOW)(f"JP: {line.jp_text.rstrip()}\n") +
            Color(Color.CYAN)(f"{msg}")
        )
        while True:
            sys.stdout.write(f"TL to keep [0, {idx-1}]: ")
            user_choice = input()
            try:
                choice_int = int(user_choice)
            except ValueError:
                print(f"Invalid selection '{user_choice}'")
                continue
            if choice_int >= 0 and choice_int < idx:
                # Commit the relevant line back to the DB
                selected_tl = numbered_choices[choice_int]
                tl_db.set_translation_and_comment_for_hash(
                    sha, selected_tl.en_text, selected_tl.comment)
                print(Color(Color.GREEN)(
                    f"Picked #{choice_int}: {selected_tl.en_text}\n"))
                break
            else:
                print(f"Invalid selection '{user_choice}'")


def perform_import(tl_db, args):
    candidate_files = []
    for basedir, dirs, files in os.walk(args.import_path):
        for filename in files:
            # Ignore non-text files
            if not filename.endswith(".txt"):
                continue

            candidate_files.append(os.path.join(basedir, filename))

    # Generate a diff
    import_diff = tl_db.parse_update_file_list(
        candidate_files, ignore_errors=not args.strict_import)

    # Apply non-conflict data immediately
    tl_db.apply_diff(import_diff)

    # If there are conflicts, and we're in interactive mode,
    # try and resolve them
    if args.interactive_import:
        import_mergetool(tl_db, import_diff)
    else:
        # If we aren't going to resolve, just print
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
                print(
                    Color(Color.RED)(f"Import conflict for line {sha}:\n") +
                    Color(Color.YELLOW)(f"JP: {line.jp_text.rstrip()}\n") +
                    Color(Color.CYAN)(f"{msg}")
                )

    # If we had conflicts and are in strict mode, bail
    if import_diff.any_conflicts() and args.strict_import:
        print("Conflicts found, aborting")
        raise SystemExit(-1)

    # Clean up afterwards?
    if args.delete:
        # Clear out the input files
        for basedir, dirs, files in os.walk(args.import_path):
            for dirname in dirs:
                shutil.rmtree(os.path.join(basedir, dirname))
            for filename in files:
                os.unlink(os.path.join(basedir, filename))


def perform_legacy_import(tl_db, args):
    # Search for text files in the import tree
    for basedir, dirs, files in os.walk(args.legacy_import_path):
        for filename in files:
            # Ignore non-text files
            if not filename.endswith(".txt"):
                continue

            try:
                tl_db.import_legacy_update_file(
                    os.path.join(basedir, filename))
            except AssertionError as e:
                if args.strict_import:
                    raise e
                else:
                    print(e)

    # Clean up afterwards?
    if args.delete:
        for basedir, dirs, files in os.walk(args.legacy_import_path):
            for dirname in dirs:
                shutil.rmtree(os.path.join(basedir, dirname))
            for filename in files:
                os.unlink(os.path.join(basedir, filename))


def perform_inject(tl_db, args):
    # Work out what to call the file
    current_time = time.strftime('%Y%m%d-%H%M%S')
    output_filename = \
        args.inject_output or f"script_text_translated{current_time}.mrg"

    # Export the script as an MZP
    mzp_data = tl_db.generate_script_text_mrg()

    # Write to file
    with open(output_filename, 'wb+') as f:
        f.write(mzp_data)

    print(f"Wrote script to '{output_filename}'")


def perform_export(tl_db, args):
    for scene in tl_db.scene_names():
        tl_db.export_scene(scene, args.export_path)


def main():
    args = parse_args()

    # Do we need to extract the DB?
    tl_db = None
    if args.do_extract:
        tl_db = TranslationDb.from_mrg("allscr.mrg", "script_text.mrg")
    else:
        tl_db = TranslationDb.from_file(args.db_path)

    # Cl offset override table?
    if args.reset_overrides:
        tl_db.clear_offset_overrides()

    # Import anything?
    if args.import_path:
        perform_import(tl_db, args)
    if args.legacy_import_path:
        perform_legacy_import(tl_db, args)

    # Use PUA?
    if args.enable_pua:
        RubyUtils.ENABLE_PUA_CODES = True

    # Inject anything?
    if args.do_inject:
        perform_inject(tl_db, args)

    if args.export_path:
        perform_export(tl_db, args)

    if not args.no_save:
        tl_db.to_file(args.db_path)


if __name__ == '__main__':
    main()
