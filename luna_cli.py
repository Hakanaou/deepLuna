#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import time

from luna.constants import Constants
from luna.translation_db import TranslationDb


def parse_args():
    parser = argparse.ArgumentParser(
        description="deepLuna CLI"
    )
    parser.add_argument(
        '--db_path',
        dest='db_path',
        action='store',
        help="Path to translation DB file",
        default=Constants.DATABASE_PATH
    )
    parser.add_argument(
        '--import',
        dest='import_path',
        action='store',
        help="Import update files from the specified path"
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
    return parser.parse_args(sys.argv[1:])


def perform_import(tl_db, args):
    candidate_files = []
    for basedir, dirs, files in os.walk(args.import_path):
        for filename in files:
            # Ignore non-text files
            if not filename.endswith(".txt"):
                continue

            candidate_files.append(os.path.join(basedir, filename))

    (consolidated_diff, conflicts) = \
        tl_db.parse_update_file_list(candidate_files)

    # Apply non-conflict data immediately
    tl_db.apply_diff(consolidated_diff)

    # Print conflict info
    for sha, candidates in conflicts.items():
        line = tl_db.tl_line_with_hash(sha)
        print(
            f"Conflict for line {sha}:\n"
            f"  JP:    {line.jp_text.rstrip()}\n"
            f"  DB EN: {line.en_text}\n"
            "  Imported candidates:"
        )
        for en_text, comment in candidates:
            print(
                f"    {en_text} // {comment.rstrip()}"
                if comment else
                f"    {en_text}"
            )

    # If we had conflicts and are in strict mode, bail
    if conflicts and args.strict_import:
        print("Conflicts found, aborting")
        raise SystemExit(-1)

    # Write back changes to disk
    with open(args.db_path, 'wb+') as output:
        output.write(tl_db.as_json().encode('utf-8'))

    # Clean up afterwards?
    if args.delete:
        for dirent in os.listdir(args.import_path):
            shutil.rmtree(os.path.join(args.import_path, dirent))


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


def main():
    args = parse_args()

    # Try and load the TL DB
    tl_db = TranslationDb.from_file(args.db_path)

    # Import anything?
    if args.import_path:
        perform_import(tl_db, args)

    # Inject anything?
    if args.do_inject:
        perform_inject(tl_db, args)


if __name__ == '__main__':
    main()
