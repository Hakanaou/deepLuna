import io
import copy
import hashlib
import json
import multiprocessing
import os
import re
import struct
import sys

from luna.constants import Constants
from luna.mrg_parser import Mzp
from luna.mzx import Mzx
from luna.readable_exporter import ReadableExporter
from luna.ruby_utils import RubyUtils


class TranslationDb:
    """
    Consolidated storage for translation information.
    The DB stores 2 main groups of data:
        - The scene table:
            A map of scene name (string) to list of text emission command
            information read from the allscr. These data contain the context
            of the line (choice, glue) as well as the MRG offset and hash of
            the JP text.
        - Content-addressed strings:
            Each JP text line, indexed by hash, associated with a translation
            and any additional comments or context left by translators
        - Offset override strings:
            It is not always the case that we want to use the same EN
            translation for all instances of a JP string, notably for
            exclamations or other short phrases.
            For these cases, allow storing overrides for a line.
    """

    def __init__(self, scene_map, line_by_hash, overrides_by_offset,
                 charswap_map=None):
        self._scene_map = scene_map
        self._line_by_hash = line_by_hash
        self._overrides_by_offset = overrides_by_offset
        self._charswap_map = charswap_map or {}

    def scene_names(self, include_empty=False):
        all_scenes = list(self._scene_map.keys())
        if include_empty:
            return all_scenes

        return [scene for scene in all_scenes if self._scene_map[scene]]

    def lines_for_scene(self, scene_name):
        return self._scene_map[scene_name]

    def tl_line_with_hash(self, jp_hash):
        return self._line_by_hash[jp_hash]

    def tl_override_for_offset(self, offset):
        assert isinstance(offset, int)
        return self._overrides_by_offset.get(offset)

    def set_translation_and_comment_for_hash(self, jp_hash, en_text, comment):
        self._line_by_hash[jp_hash].en_text = en_text
        self._line_by_hash[jp_hash].comment = comment

    def tl_line_for_cmd(self, cmd):
        return self.tl_override_for_offset(cmd.offset) or \
            self.tl_line_with_hash(cmd.jp_hash)

    def tl_line_for_offset(self, offset):
        # Not a hot path, so just iterate the scene map
        for scene in self._scene_map.values():
            for line in scene:
                if line.offset == offset:
                    return line.jp_hash

        return None

    def override_translation_and_comment_for_offset(
            self, offset, en_text, comment):
        assert isinstance(offset, int)
        if offset not in self._overrides_by_offset:
            # Default the override data to the proper hash line at this offset
            jp_hash = self.tl_line_for_offset(offset)
            if jp_hash not in self._line_by_hash:
                print(f"Unknown hash {jp_hash}")
                return
            base = copy.deepcopy(self._line_by_hash[jp_hash])
            self._overrides_by_offset[offset] = base

        self._overrides_by_offset[offset].en_text = en_text
        self._overrides_by_offset[offset].comment = comment

    def clear_offset_overrides(self):
        self._overrides_by_offset = {}

    def translated_percent(self):
        total_lines = 0
        translated_lines = 0
        for line in self._line_by_hash.values():
            total_lines += 1
            if line.en_text:
                translated_lines += 1

        return float(translated_lines) * 100.0 / float(total_lines)

    def get_charswap_map(self):
        return self._charswap_map

    def set_charswap_map(self, swap_map):
        self._charswap_map = swap_map

    def as_json(self):
        return json.dumps({
            'scene_map': {
                k: [e.as_json() for e in v]
                for k, v in self._scene_map.items()
            },
            'line_by_hash': {
                k: v.as_json() for k, v in self._line_by_hash.items()
            },
            'override_by_offset': {
                k: v.as_json() for k, v in self._overrides_by_offset.items()
            },
            'charswap_map': self._charswap_map
        }, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, jsonb):
        scene_map = {
            k: [cls.TextCommand.from_json(e) for e in v]
            for k, v in jsonb['scene_map'].items()
        }
        line_by_hash = {
            k: cls.TLLine.from_json(v)
            for k, v in jsonb['line_by_hash'].items()
        }
        overrides_by_offset = {
            int(k): cls.TLLine.from_json(v)
            for k, v in jsonb.get('override_by_offset', {}).items()
        }
        charswap_map = jsonb.get('charswap_map')

        return cls(scene_map, line_by_hash, overrides_by_offset, charswap_map)

    def export_scene(self, scene_name, output_basedir):
        if scene_name not in self.scene_names():
            return

        # Generate the full export path
        is_arc_scene = '_ARC' in scene_name
        is_ciel_scene = '_CIEL' in scene_name
        is_qa_scene = 'QA' in scene_name
        is_common_scene = not any([is_arc_scene, is_ciel_scene, is_qa_scene])
        export_path = [output_basedir]
        if is_arc_scene or is_ciel_scene:
            day = int(scene_name.split('_')[0])
            export_path += [
                'Arcueid' if is_arc_scene else 'Ciel',
                f'Day {day}'
            ]
        elif is_qa_scene:
            export_path += ['QA']
        elif is_common_scene:
            export_path += ['Common']

        # Ensure the export dir exists
        output_basedir = os.path.join(*export_path)
        try:
            os.makedirs(output_basedir)
        except FileExistsError:
            pass

        # Export
        output_filename = os.path.join(
            output_basedir, f"{scene_name}.txt")
        with open(output_filename, "wb+") as output_file:
            output_file.write(
                ReadableExporter.export_text(
                    self, scene_name
                ).encode('utf-8')
            )

    def generate_script_text_mrg(self, perform_charswap=False):
        offset_to_string = self.generate_linebroken_text_map(perform_charswap)
        return self.pack_linebroken_text_to_mrg(offset_to_string)

    def generate_linebroken_text_map(self, perform_charswap=False):
        # Iterate each scene in the translation DB, apply line breaking
        # and control codes and stick the result into a map of offset -> string
        offset_to_string = {}

        for scene_name, scene_commands in self._scene_map.items():
            cursor_position = 0
            prev_page_number = None
            scene_is_qa = scene_name.startswith('QA')
            # We need some amount of lookahead for glue lines, so iterate
            # by offset here
            for cmd_offset in range(len(scene_commands)):
                command = scene_commands[cmd_offset]

                # Pull the translated text for this line from the SHA-addressed
                # translation table
                tl_line = self._line_by_hash[command.jp_hash]

                # If there is an explicit override for this line, pull that
                # instead
                if command.offset in self._overrides_by_offset:
                    tl_line = self._overrides_by_offset[command.offset]

                # If the line is not actually translated, fall back to the
                # original JP text instead.
                if not tl_line.en_text:
                    offset_to_string[command.offset] = tl_line.jp_text
                    continue

                # Get the english text.
                tl_text = tl_line.en_text

                # The translation text may contain linebreaks, as allowed by
                # the import/export format. Remove these now. Linebreaks
                # intended for display in-game must be coded for using %{n}
                tl_text = tl_text.replace('\n', '')

                # If this line is not glued to the line that came before it,
                # reset the accumulated cursor position
                # However, if this is a QA scene, _all_ lines count as glued
                # due to modifications to the allscr.
                force_glue = '%{force_glue}' in tl_text
                if not (command.is_glued or force_glue) and not scene_is_qa:
                    cursor_position = 0

                # If we have turned the page, we also want to rezero the
                # cursor position
                if command.page_number != prev_page_number:
                    prev_page_number = command.page_number
                    cursor_position = 0

                # Reify any custom control codes present in the line
                coded_text = RubyUtils.apply_control_codes(tl_text)

                # If we are performing a charswap, do so now
                if perform_charswap:
                    coded_text = ''.join([
                        self._charswap_map.get(c, c) for c in coded_text
                    ])

                # If this line is glued, and would start with a space, but the
                # preceding line ended in a newline, drop the leading space.
                if coded_text and command.is_glued and cmd_offset - 1 >= 0:
                    prev_cmd = scene_commands[cmd_offset-1]
                    # Need to strip the padding \r\n from lines
                    prev_broken_line = offset_to_string[
                        prev_cmd.offset].replace("\r\n", "")
                    if prev_broken_line[-1] == '\n' and coded_text[0] == ' ':
                        coded_text = coded_text[1:]

                # Break the text, unless this is a QA scene in which case
                # it's all manual
                linebroken_text = (
                    coded_text if scene_is_qa else
                    RubyUtils.linebreak_text(
                        coded_text,
                        Constants.CHARS_PER_LINE,
                        start_cursor_pos=cursor_position
                    )
                )

                # Check if the broken text contains any newlines, and update
                # the new cursor position accordingly
                did_break_line = len(linebroken_text.split('\n')) > 1
                final_broken_line = linebroken_text.split('\n')[-1]
                old_cursor_position = cursor_position
                if did_break_line:
                    cursor_position = RubyUtils.noruby_len(final_broken_line)
                else:
                    cursor_position += RubyUtils.noruby_len(final_broken_line)
                    cursor_position = \
                        cursor_position % Constants.CHARS_PER_LINE

                # Test to see if the next line is glued
                if cmd_offset + 1 < len(scene_commands):
                    next_cmd = scene_commands[cmd_offset+1]
                    if next_cmd.is_glued and linebroken_text:
                        # Need to check if glueing this line screws anything up
                        # - If next line starts with space, and current line is
                        #   precicely 55 chars, force newline at the end of
                        #   this current line
                        next_line = self._line_by_hash[next_cmd.jp_hash]
                        next_tl = next_line.en_text or tl_line.jp_text
                        if next_tl and next_tl[0] == ' ' \
                                and linebroken_text[-1] != '\n':
                            if cursor_position == 0:
                                linebroken_text += "\n"
                                cursor_position = 0

                        # If next line does not start with a space, re-break
                        # this line accounting for the glue characters as
                        # part of the final word IF it would cause a linebreak
                        # when added
                        next_word_len = RubyUtils.noruby_len(
                            next_tl.split(' ')[0])
                        next_word_would_break = False
                        if did_break_line:
                            next_word_would_break = \
                                RubyUtils.noruby_len(final_broken_line) + \
                                next_word_len > Constants.CHARS_PER_LINE
                        else:
                            next_word_would_break = \
                                old_cursor_position + \
                                RubyUtils.noruby_len(final_broken_line) + \
                                next_word_len > Constants.CHARS_PER_LINE
                        if next_tl and next_tl[0] != ' ' \
                                and linebroken_text[-1] != '\n' \
                                and next_word_would_break:
                            # If the broken line contains spaces, change
                            # the final space to a newline
                            if ' ' in linebroken_text:
                                fragments = linebroken_text.split(' ')
                                linebroken_text = ' '.join(
                                    fragments[:-2] +
                                    ['\n'.join(fragments[-2:])])
                            else:
                                # If there's no space we can repurpose,
                                # we would have to go back to the _previous_
                                # line to find a natural break. We can't, so
                                # crash here and force the editor to go put in
                                # a manual %{n} or %{s} somewhere.
                                raise RuntimeError(
                                    f"Fixing glue for offset {command.offset} "
                                    "requires too much backtracking. "
                                    "Insert extra whitespace to allow first "
                                    "order line breaks."
                                )

                            # Re-calc new cursor position
                            final_broken_line = linebroken_text.split('\n')[-1]
                            cursor_position = RubyUtils.noruby_len(
                                final_broken_line)

                # Append trailing \r\n if the original text had it
                processed_string = linebroken_text + (
                    "\r\n"
                    if tl_line.jp_text.endswith("\r\n")
                    and not linebroken_text.endswith("\r\n")
                    else "")

                # Stick the processed string into our map
                offset_to_string[command.offset] = processed_string

        return offset_to_string

    def pack_linebroken_text_to_mrg(self, offset_to_string):
        # Now that we have processed all the strings, iterate from 0 to
        # max_offset and write each string entry into an MZP.
        max_offset = max(offset_to_string.keys())
        offset_table = io.BytesIO()
        string_table = io.BytesIO()
        for offset in range(max_offset + 1):
            # There are a handful of null strings that mark EOF
            # Just write FFs to the offset table, no string data for these
            if not offset_to_string.get(offset, ''):
                continue

            # Write the offset of this string to the offset table
            offset_table.write(struct.pack(">I", string_table.tell()))

            # Write the string data to the string table
            string_table.write(
                offset_to_string.get(offset, '').encode('utf-8'))

        # Finalize the offset table by writing the final offset twice,
        # followed by 12 bytes of 0xFF
        offset_table.write(struct.pack(">I", string_table.tell()))
        offset_table.write(struct.pack(">I", string_table.tell()))
        offset_table.write(struct.pack(">I", 0xFFFFFFFF))

        offset_table.seek(0, io.SEEK_SET)
        string_table.seek(0, io.SEEK_SET)
        offset_table_str = offset_table.read()
        string_table_str = string_table.read()

        # For whatever reason, the MZP also contains 4 offset/string table
        # pairs consisting of just '  \r\n' . Regenerate these tables too
        # in case they actually mean something.
        newline_offset_table = io.BytesIO()
        newline_string_table = io.BytesIO()
        for i in range(max_offset + 1):
            newline_offset_table.write(
                struct.pack(">I", newline_string_table.tell()))
            newline_string_table.write(b"  \r\n")

        # Finalize
        newline_string_table_end = newline_string_table.tell()
        newline_offset_table.write(struct.pack(">I", newline_string_table_end))
        newline_offset_table.write(struct.pack(">I", newline_string_table_end))
        newline_offset_table.write(struct.pack(">I", 0xFFFFFFFF))

        newline_offset_table.seek(0, io.SEEK_SET)
        newline_string_table.seek(0, io.SEEK_SET)
        newline_offset_table_str = newline_offset_table.read()
        newline_string_table_str = newline_string_table.read()

        # Space tables
        space_offset_table = io.BytesIO()
        space_string_table = io.BytesIO()
        for i in range(max_offset + 1):
            space_offset_table.write(
                struct.pack(">I", space_string_table.tell()))
            space_string_table.write("\u3000\r\n".encode('utf-8'))

        # Finalize
        space_string_table_end = space_string_table.tell()
        space_offset_table.write(struct.pack(">I", space_string_table_end))
        space_offset_table.write(struct.pack(">I", space_string_table_end))
        space_offset_table.write(struct.pack(">I", 0xFFFFFFFF))

        space_offset_table.seek(0, io.SEEK_SET)
        space_string_table.seek(0, io.SEEK_SET)
        space_offset_table_str = space_offset_table.read()
        space_string_table_str = space_string_table.read()

        # Pack the MZP
        return Mzp.pack([
            # Actual translation data
            offset_table_str, string_table_str,
            # 4 copies of newlines
            newline_offset_table_str, newline_string_table_str,
            space_offset_table_str, space_string_table_str,
            space_offset_table_str, space_string_table_str,
            space_offset_table_str, space_string_table_str,
        ])

    @classmethod
    def from_file(cls, path):
        with open(path, 'rb') as input_file:
            raw_db = input_file.read()
        return cls.from_json(json.loads(raw_db))

    def to_file(self, path):
        with open(path, 'wb+') as output:
            output.write(self.as_json().encode('utf-8'))

    def import_update_file(self, filename):
        # Parse diff
        diff = self.parse_update_file(filename)

        # If we get a good result, apply the changes to the DB
        self.apply_diff(diff)

    def apply_diff(self, diff):
        for sha, entry_group in diff.entries_by_sha.items():
            # Ignore entries with conflicts
            if not entry_group.is_unique():
                continue

            # Just directly apply non-conflicting diff items
            self.set_translation_and_comment_for_hash(
                sha,
                entry_group.entries[0].en_text,
                entry_group.entries[0].comment,
            )

        for offset, entry_group in diff.entries_by_offset.items():
            # If there's duplicate offset entries somehow, they gotta fix that
            if not entry_group.is_unique():
                continue

            # Commit the override
            self.override_translation_and_comment_for_offset(
                offset,
                entry_group.entries[0].en_text,
                entry_group.entries[0].comment,
            )

    def parse_update_file(self, filename):
        # Try to parse it to a diff
        return ReadableExporter.import_text(filename)

    def parse_update_file_list(self, filenames, ignore_errors=True):
        # Load diffs for each file
        diff = ReadableExporter.Diff()
        for filename in filenames:
            try:
                diff.append_diff(self.parse_update_file(filename))
            except ReadableExporter.ParseError as e:
                print(
                    f"Failed to apply updates from {filename}: "
                    f"{e}"
                )
                if not ignore_errors:
                    raise e

        return diff

    def import_legacy_update_file(self, filename):
        # Can we determine the appropriate scene from this filename?
        basename = os.path.basename(filename)
        scene_name = basename[:-4]
        if scene_name not in self._scene_map:
            print(f"Cannot match file '{basename}' to a scene")
            return

        # Load the file
        with open(filename, "rb") as f:
            file_text = f.read().decode('utf-8')

        # Split into lines and delete page/choice markers
        raw_lines = [
            line.replace("C:>", "") for line in file_text.split('\n')
            if line and not line.startswith('<Page')
        ]

        # Since the old format glued lines, we need to split them back apart.
        # Just duplicate comments on glued lines to all members.
        lines = []
        for line in raw_lines:
            # Split into tl and comment
            split_line = line.split('//')
            glued_en_text = split_line[0]
            comment_text = split_line[1] if len(split_line) > 1 else None

            # If the TL is actually multiple lines (glued), break it up
            split_en_text = glued_en_text.split('#')
            for fragment in split_en_text:
                lines.append((fragment, comment_text))

        # Get the scene info for this file
        scene_lines = self._scene_map[scene_name]

        # Assert that then number of lines in the file to import matches the
        # expected number of lines in the scene
        assert len(scene_lines) == len(lines), \
            f"File {basename} has {len(lines)} strings, " \
            f"but scene expects {len(scene_lines)} lines."

        # Zip and update
        for scene_line, (tl_text, comment_text) in zip(scene_lines, lines):
            self.set_translation_and_comment_for_hash(
                scene_line.jp_hash, tl_text, comment_text
            )

    @classmethod
    def parse_script_cmds(cls, script, strings_by_content_hash,
                          content_hash_by_offset):
        # Split script into commands
        raw_cmds = [
            cmd.strip() for cmd in script.decode('utf-8').split(';')
            if cmd.strip()
        ]

        # Regex to parse command name/args
        command_regex = re.compile(
            r"_(\w+)\(([\w 　a-zA-Z0-9-,`@$:.+^_]*)\)\Z")

        # Parse each script command
        script_commands = []
        for cmd in raw_cmds:
            # Try and match regex
            match = command_regex.match(cmd)
            if not match:
                sys.stderr.write(f"Failed to parse command {cmd}\n")
                continue

            groups = match.groups()
            script_commands.append(
                cls.AllscrCmd(groups[0])
                if len(groups) == 1
                else cls.AllscrCmd(groups[0], groups[1].split(','))
            )

        # Now iterate the script commands and extract any that reference
        # script lines
        text_offsets = []
        visited_offsets = set()
        page_number = 0
        seen_offsets = set()
        for cmd in script_commands:
            # If it's a PGST, take argv0 the page counter
            if cmd.opcode == 'PGST':
                page_number = int(cmd.arguments[0])
                continue

            # If it's not a text scripting command, ignore
            is_zm = cmd.opcode.startswith('ZM')
            is_msad = cmd.opcode == 'MSAD'
            is_selr = cmd.opcode == 'SELR'
            if not any([is_zm, is_msad, is_selr]):
                continue

            # If it has no arguments, ignore
            if not cmd.arguments:
                continue

            # If it does have args, match all instances of text references
            for arg in cmd.arguments:
                text_refs = re.compile(r"(\$\d+)").findall(arg)
                text_modifiers = re.compile(r"(\@\w)").findall(arg)
                offsets = [int(ref[1:]) for ref in text_refs]
                for offset in offsets:
                    # If we already saw this offset in the file, just skip
                    if offset in seen_offsets:
                        continue

                    # Does this offset have a forced linebreak after it?
                    # Get the position of the offset in the full cmd line
                    fmt_off = f"${offset:06}"
                    offset_pos = arg.find(fmt_off)
                    # If there is a ^ between this offset and the $ of a
                    # subsequent offset, we have a trailing newline.
                    next_offset_pos = arg.find("$", offset_pos + len(fmt_off))
                    caret_pos = arg.find("^", offset_pos, next_offset_pos)
                    has_forced_newline = caret_pos != -1

                    # Work out whether this line is glued to the previous
                    # line. A line is glued if any of:
                    #  - It has an @x modifier on it
                    #  - It is an MSAD command
                    # and NONE of the following are true:
                    #  - The previous text command contains an explicit
                    #    linebreak (^) control code after it
                    has_x_modifier = '@x' in text_modifiers
                    prev_line_forces_break = (
                        # Is there a previous line
                        bool(text_offsets)
                        # Is it on the same page as this
                        and text_offsets[-1].page_number == page_number
                        # Does it contain a forced newline at the end
                        and text_offsets[-1].has_forced_newline
                    )
                    is_glued = (
                        (is_msad or has_x_modifier)
                        and not prev_line_forces_break
                    )

                    # Does the line contain any ruby text?
                    jp_line = strings_by_content_hash[
                        content_hash_by_offset[offset]]
                    jp_text = jp_line.jp_text
                    has_ruby = '<' in jp_text

                    seen_offsets.add(offset)
                    text_offsets.append(cls.TextCommand(
                        offset,
                        content_hash_by_offset[offset],
                        page_number,
                        has_ruby=has_ruby,
                        is_glued=is_glued,
                        is_choice=is_selr,
                        modifiers=text_modifiers,
                        has_forced_newline=has_forced_newline
                    ))
                    visited_offsets.add(offset)

        return text_offsets

    @classmethod
    def from_mrg(cls, allscr_path, script_text_path):
        script_text_mzp = Mzp(script_text_path)

        # First script text MZP entry is the string offsets, second is
        # the string data
        string_offsets_raw = script_text_mzp.data[0]
        string_table_raw = script_text_mzp.data[1]

        # For each 32 bit offset in the offset table, extract the associated
        # JP text
        offset_count = len(string_offsets_raw) // 4
        strings_by_offset = {}
        for i in range(offset_count):
            (data_start,) = struct.unpack('>I', string_offsets_raw[i*4:i*4+4])
            (data_end,) = struct.unpack(
                '>I', string_offsets_raw[(i+1)*4:(i+1)*4+4])

            # Zero-len string marks end of offset table
            if data_start == data_end:
                break

            # If it's non-zero, extract the associated string data
            data = string_table_raw[data_start:data_end]
            strings_by_offset[i] = data.decode('utf-8')

        # Hash those strings to build initial content table and
        # offset -> hash table
        content_hash_by_offset = {}
        strings_by_content_hash = {}
        for offset, jp_text in strings_by_offset.items():
            tl_line = cls.TLLine(jp_text)
            content_hash_by_offset[offset] = tl_line.content_hash()
            strings_by_content_hash[tl_line.content_hash()] = tl_line

        # Parse the scene map from allscr
        allscr_mzp = Mzp(allscr_path)

        # Zeroth entry is the script filenames. Each 32 byte chunk is one
        # string, delete excess \0 chars and arrayize
        script_nam_raw = allscr_mzp.data[0]
        script_names = [
            script_nam_raw[i:i + 32].decode('utf-8').replace('\0', '').strip()
            for i in range(0, len(script_nam_raw), 32)
        ]

        # Entries 1/2 are unknown, 3+ are the game script files
        compressed_script_files = allscr_mzp.data[3:]

        # Decompress all the script files
        with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
            decompressed_script_files = pool.map(
                Mzx.decompress,
                compressed_script_files
            )

        # For each scene, extract the list of text offsets
        scene_map = {}
        visited_offsets = set()
        for scene_name, script \
                in zip(script_names, decompressed_script_files):
            scene_map[scene_name] = cls.parse_script_cmds(
                script,
                strings_by_content_hash,
                content_hash_by_offset
            )
            for cmd in scene_map[scene_name]:
                visited_offsets.add(cmd.offset)

        # Reparent any text lines that exist but aren't referenced by the
        # allscr scripts
        orphan_lines = []
        for offset, sha in content_hash_by_offset.items():
            if offset in visited_offsets:
                continue

            orphan_lines.append(cls.TextCommand(offset, sha, -1))

        scene_map['ORPHANED_LINES'] = orphan_lines

        return cls(scene_map, strings_by_content_hash, {})

    class TextCommand:
        def __init__(self, offset, jp_hash, page_number, has_ruby=False,
                     is_glued=False, is_choice=False, modifiers=None,
                     has_forced_newline=False):
            self.offset = offset
            self.jp_hash = jp_hash
            self.page_number = page_number
            self.has_ruby = has_ruby
            self.is_glued = is_glued
            self.is_choice = is_choice
            self.modifiers = modifiers or []
            self.has_forced_newline = has_forced_newline

        def __eq__(self, other):
            # Default impl doesn't work for whatever reason
            compare_attrs = [
                'offset', 'jp_hash', 'page_number', 'has_ruby',
                'is_glued', 'is_choice', 'modifiers', 'has_forced_newline'
            ]
            for attr in compare_attrs:
                if getattr(self, attr) != getattr(other, attr):
                    return False
            return True

        @classmethod
        def from_json(cls, jsonb):
            return cls(
                jsonb['offset'],
                jsonb['jp_hash'],
                jsonb['page_number'],
                jsonb.get('has_ruby', False),
                jsonb.get('is_glued', False),
                jsonb.get('is_choice', False),
                jsonb.get('modifiers'),
                jsonb.get('has_forced_newline')
            )

        def as_json(self):
            ret = {
                'offset': self.offset,
                'jp_hash': self.jp_hash,
                'page_number': self.page_number,
            }

            # Only include non-default flags to keep the db cleaner
            if self.has_ruby:
                ret['has_ruby'] = True

            if self.is_glued:
                ret['is_glued'] = True

            if self.is_choice:
                ret['is_choice'] = True

            if self.modifiers:
                ret['modifiers'] = self.modifiers

            if self.has_forced_newline:
                ret['has_forced_newline'] = self.has_forced_newline

            return ret

        def __repr__(self):
            return (
                f"TextCommand: "
                f"{self.offset} "
                f"{self.jp_hash} "
                f"{self.page_number} "
                f"{self.has_ruby} "
                f"{self.is_glued} "
                f"{self.is_choice} "
                f"{self.modifiers} "
                f"{self.has_forced_newline}"
            )

    class AllscrCmd:
        def __init__(self, opcode, arguments=None):
            # Opcode is the text keyword for this command, e.g. WKST or PGST
            # This is stored WITHOUT leading underscore
            self.opcode = opcode

            # Arguments is a list of string encoded arguments to this command
            # Arguments must be joined by commas when packing scripts
            self.arguments = arguments

        def __repr__(self):
            # Convert a script command to a string for emission
            return "_%s(%s);" % (self.opcode, ','.join(self.arguments or []))

    class TLScene:
        def __init__(self, scene_name, content_hashes):
            self._scene_name = scene_name
            self._content_hashes = content_hashes

        @classmethod
        def from_json(cls, jsonb):
            return cls(jsonb['scene_name'], jsonb['content_hashes'])

        def as_json(self):
            return {
                'scene_name': self._scene_name,
                'content_hashes': self._content_hashes,
            }

    class TLLine:
        def __init__(self, jp_text, en_text=None, comment=None):
            self.jp_text = jp_text
            self.en_text = en_text
            self.comment = comment

        def __repr__(self):
            return f"TLLine({self.jp_text} {self.en_text} {self.comment})"

        def content_hash(self):
            return hashlib.sha1(self.jp_text.encode('utf-8')).hexdigest()

        @classmethod
        def from_json(cls, jsonb):
            return cls(
                jsonb.get('jp_text'),
                jsonb.get('en_text', None),
                jsonb.get('comment', None),
            )

        def as_json(self):
            return {
                'jp_text': self.jp_text,
                'en_text': self.en_text,
                'comment': self.comment,
            }
