import ast
import copy


class TranslationTableEntry:
    # Translation table is serialized as a list of entries, where each
    # entry consists of
    # 0: Hex number (as a string) ?
    # 1: Original Japanese text for line
    # 2: Translated text for line
    # 3: 1 if the line contains ruby text, else 0
    # 4: Offset into the script_text.mrg string table for this line
    #    (Note that this value is ONE-INDEXED)
    # 5: Page number this text appears on in the scene
    # 6: List of scene names in which this string appears (?)
    # 7: 1 if this line is glued with other lines, else 0
    # 8: 1 if this line is a choice, else 0

    def __init__(self, line):
        assert len(line) == 9, "Bad translation table entry: '%s'" % line
        self.field_0 = line[0]
        self.jp_text = line[1]
        self.translated_text = line[2]
        self.has_ruby = True if int(line[3]) == 1 else False
        self.string_offset = int(line[4])
        self.page_number = int(line[5])
        self.scene_list = line[6]
        self.is_glued = True if int(line[7]) == 1 else False
        self.is_choice = True if int(line[8]) == 1 else False

    def is_translated(self):
        return self.translated_text != "TRANSLATION"

    def __repr__(self):
        return (
            f"TranslationTableEntry("
            f"field_0={self.field_0}, "
            f"jp_text='{self.jp_text}', "
            f"translated_text='{self.translated_text}', "
            f"has_ruby={self.has_ruby}, "
            f"string_offset={self.string_offset}, "
            f"page_number={self.page_number}, "
            f"scene_list={self.scene_list}, "
            f"is_glued={self.is_glued}, "
            f"is_choice={self.is_choice})"
        )


class MergedTranslationTableEntry:
    # Represents a collection of one or more raw string objects that are
    # treated as a compound sentence for purposes of the UI
    def __init__(self, sub_entries):
        self._sub_entries = copy.deepcopy(sub_entries)

    @property
    def offset_list(self):
        return [e.string_offset for e in self._sub_entries]

    @property
    def jp_text(self):
        return '#'.join([e.jp_text for e in self._sub_entries])

    @property
    def translated_text(self):
        # If none of the sub-strings are translated, return the placeholder
        if not any(e.is_translated() for e in self._sub_entries):
            return 'TRANSLATION'

        # If any of the sub-strings _are_ translated, return an actual
        # conjoined translation
        return '#'.join([e.translated_text for e in self._sub_entries])

    def offset_label(self):
        # If we only contain a single sub-entry, it is just the number
        return ','.join([str(s) for s in self.offset_list])

    def is_translated(self):
        return all(e.is_translated() for e in self._sub_entries)

    def set_translation(self, translation_lines):
        assert len(translation_lines) == len(self._sub_entries)
        for i in range(len(translation_lines)):
            self._sub_entries[i].translated_text = translation_lines[i]

    @property
    def page_number(self):
        # All strings that are merged _should_ have the same page number, so
        # just return the page number of the first string
        return self._sub_entries[0].page_number

    @property
    def scene_list(self):
        # Presumably all sub-entries have the same scene list data
        return self._sub_entries[0].scene_list

    def clear_translation(self):
        for entry in self._sub_entries:
            entry.translated_text = 'TRANSLATION'

    def __repr__(self):
        return f"MergedTranslationTableEntry({self._sub_entries})"


class TranslationTable:
    def __init__(self, filename):
        # Open source file and split out each line
        with open(filename, "r+", encoding="utf-8") as f:
            data = f.read()

        # Split data on newlines
        lines = data.split('\n')

        # Run each element in the table through literal_eval
        # TODO(ross): Cursed
        parsed_lines = [ast.literal_eval(elem) for elem in lines if elem]

        # Wrap each string in a TTableEntry and store in a map indexed by
        # text offset
        self._strings_by_offset = {}
        for line in parsed_lines:
            wrapped = TranslationTableEntry(line)
            self._strings_by_offset[wrapped.string_offset] = wrapped

    def string_offsets(self):
        return self._strings_by_offset.keys()

    def translated_percent(self):
        total_entries = 0
        translated_entries = 0
        for entry in self._strings_by_offset.values():
            total_entries += 1
            if entry.is_translated():
                translated_entries += 1
        return 100.0 * float(translated_entries) / float(total_entries)

    def entry_for_text_offset(self, text_offset):
        # Return a copy to prevent unintentional mutation
        return copy.deepcopy(self._strings_by_offset[text_offset])

    def serialize_to_file(self, filename):
        return
        with open(filename, 'w+', encoding="utf-8") as f:
            for offset in sorted(self._strings_by_offset.keys()):
                f.write(str(self._strings_by_offset[offset]) + "\n")

    def apply_update(self, new_entry):
        assert isinstance(new_entry, MergedTranslationTableEntry)

        # For each sub-entry in this merged entry, overwrite our local
        # data with a copy
        for sub_entry in new_entry._sub_entries:
            self._strings_by_offset[sub_entry.string_offset] = \
                copy.deepcopy(sub_entry)
