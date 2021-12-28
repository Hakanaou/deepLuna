import hashlib
import json
import struct

from luna.mrg_parser import Mzp

class TranslationDb:
    """
    Consolidated storage for translation information.
    The DB stores 2 main groups of data:
        - The scene table:
            A map of scene name (string) to list of string offsets (int) into
            the script_text mrg.
        - The proxy table:
            A map of MRG string offset to content hash. If the game is updated,
            only this and the scene table need to be re-generated, and already
            translated lines may be re-associated by hash.
        - Content-addressed strings:
            Each JP text line, indexed by hash, associated with a translation
            and any additional comments or context left by translators
    """

    def __init__(self, path):
        with open(path, 'rb') as input_file:
            raw_db = input_file.read()
        self._data = json.loads(raw_db)

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
        def __init__(self, jp_text, en_text=None, comment=None,
                     has_ruby=False, is_glued=False, is_choice=False):
            self._content_hash = hashlib.sha1(jp_text.encode('utf-8'))
            self._jp_text = jp_text
            self._en_text = en_text
            self._comment = comment
            self._has_ruby = has_ruby
            self._is_glued = is_glued
            self._is_choice = is_choice

        def content_hash(self):
            return self._content_hash

        @classmethod
        def from_json(cls, jsonb):
            return cls(
                jsonb.get('content_hash'),
                jsonb.get('jp_text'),
                jsonb.get('en_text', None),
                jsonb.get('comment', None),
                jsonb.get('has_ruby', False),
                jsonb.get('is_glued', False),
                jsonb.get('is_choice', False),
            )

        def as_json(self):
            return {
                'content_hash': self._content_hash,
                'jp_text': self._jp_text,
                'en_text': self._en_text,
                'comment': self._comment,
                'has_ruby': self._has_ruby,
                'is_glued': self._is_glued,
                'is_choice': self._is_choice,
            }
