import hashlib
import json
import multiprocessing
import re
import struct
import sys

from luna.mrg_parser import Mzp
from luna.mzx import Mzx

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
    """

    def __init__(self, scene_map, line_by_hash):
        self._scene_map = scene_map
        self._line_by_hash = line_by_hash

    def scene_names(self, include_empty=False):
        all_scenes = list(self._scene_map.keys())
        if include_empty:
            return all_scenes

        return [scene for scene in all_scenes if self._scene_map[scene]]

    def lines_for_scene(self, scene_name):
        return self._scene_map[scene_name]

    def tl_line_with_hash(self, jp_hash):
        return self._line_by_hash[jp_hash]

    def set_translation_and_comment_for_hash(self, jp_hash, en_text, comment):
        self._line_by_hash[jp_hash].en_text = en_text
        self._line_by_hash[jp_hash].comment = comment

    def translated_percent(self):
        total_lines = 0
        translated_lines = 0
        for line in self._line_by_hash.values():
            total_lines += 1
            if line.en_text:
                translated_lines += 1

        return float(translated_lines) * 100.0 / float(total_lines)

    def as_json(self):
        return json.dumps({
            'scene_map': {
                k: [e.as_json() for e in v]
                for k, v in self._scene_map.items()
            },
            'line_by_hash': {
                k: v.as_json() for k, v in self._line_by_hash.items()
            }
        }, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, jsonb):
        scene_map = {
            k: [cls.TextCommand.from_json(e) for e in v]
            for k, v in jsonb['scene_map'].items()
        }
        line_by_hash = {
            k: cls.TLLine.from_json(v) for k, v in jsonb['line_by_hash'].items()
        }
        return cls(scene_map, line_by_hash)

    @classmethod
    def from_file(cls, path):
        with open(path, 'rb') as input_file:
            raw_db = input_file.read()
        return cls.from_json(json.loads(raw_db))

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
            if i < offset_count - 1:
                (data_end,) = struct.unpack('>I', string_offsets_raw[(i+1)*4:(i+1)*4+4])
                data = string_table_raw[data_start:data_end]
            else:
                data = string_table_raw[data_start:]
            strings_by_offset[i] = data.decode('utf-8')

        # Hash those strings to build initial content table and offset -> hash table
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
            page_number = 0
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
                        # Glue if the previous line ends in an @n
                        jp_line = strings_by_content_hash[content_hash_by_offset[offset]]
                        jp_text = jp_line.jp_text
                        is_glued = bool(text_offsets) and bool('@n' in text_offsets[-1].modifiers)
                        has_ruby = '<' in jp_text
                        text_offsets.append(cls.TextCommand(
                            offset, content_hash_by_offset[offset], page_number,
                            has_ruby=has_ruby,
                            is_glued=is_glued,
                            is_choice=is_selr,
                            modifiers=text_modifiers
                        ))
                        visited_offsets.add(offset)

            scene_map[scene_name] = text_offsets

        # Reparent any text lines that exist but aren't referenced by the
        # allscr scripts
        orphan_lines = []
        for offset, sha in content_hash_by_offset.items():
            if offset in visited_offsets:
                continue

            orphan_lines.append(cls.TextCommand(offset, sha, -1))

        scene_map['ORPHANED_LINES'] = orphan_lines

        return cls(scene_map, strings_by_content_hash)


    class TextCommand:
        def __init__(self, offset, jp_hash, page_number, has_ruby=False,
                     is_glued=False, is_choice=False, modifiers=None):
            self.offset = offset
            self.jp_hash = jp_hash
            self.page_number = page_number
            self.has_ruby = has_ruby
            self.is_glued = is_glued
            self.is_choice = is_choice
            self.modifiers = modifiers or []

        @classmethod
        def from_json(cls, jsonb):
            return cls(
                jsonb['offset'],
                jsonb['jp_hash'],
                jsonb['page_number'],
                jsonb.get('has_ruby', False),
                jsonb.get('is_glued', False),
                jsonb.get('is_choice', False),
                jsonb.get('modifiers')
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

            return ret

        def __repr__(self):
            return (
                f"TextCommand: {self.offset} {self.jp_hash} {self.has_ruby} "
                f"{self.is_glued} {self.is_choice} {self.modifiers}"
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
