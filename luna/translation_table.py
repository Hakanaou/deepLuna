import ast
import copy


class TranslationTableEntry:
    # Translation table is serialized as a list of entries, where each
    # entry consists of
    # 0: Hex number (as a string) ?
    # 1: Original Japanese text for line
    # 2: Translated text for line
    # 3: ?
    # 4: Offset into the script_text.mrg string table for this line
    #    (Note that this value is ONE-INDEXED)
    # 5: ?
    # 6: List of scene names in which this string appears (?)
    # 7: ?
    # 8: ?

    def __init__(self, line):
        assert len(line) == 9, "Bad translation table entry: '%s'" % line
        self.field_0 = line[0]
        self.jp_text = line[1]
        self.translated_text = line[2]
        self.field_3 = int(line[3])
        self.string_offset = int(line[4])
        self.field_5 = int(line[5])
        self.scene_list = line[6]
        self.field_7 = int(line[7])
        self.field_8 = int(line[8])

    def is_translated(self):
        return self.translated_text != "TRANSLATION"

    def __repr__(self):
        return (
            f"TranslationTableEntry({self.field_0}, '{self.jp_text}', "
            f"'{self.translated_text}', {self.field_3}, {self.string_offset}, "
            f"{self.field_5}, {self.scene_list}, {self.field_7}, "
            f"{self.field_8})"
        )


class MergedTranslationTableEntry:
    # Represents a collection of one or more raw string objects that are
    # treated as a compound sentence for purposes of the UI
    def __init__(self, sub_entries):
        self._sub_entries = sub_entries

        self.offset_list = [
            e.string_offset for e in self._sub_entries]
        self.jp_text = '#'.join([
            e.jp_text for e in self._sub_entries])
        self.translated_text = '#'.join([
            e.translated_text for e in self._sub_entries])

    def offset_label(self):
        # If we only contain a single sub-entry, it is just the number
        return ','.join([str(s) for s in self.offset_list])

    def is_translated(self):
        return all(e.is_translated() for e in self._sub_entries)

    @property
    def field_5(self):
        # I don't know what field 5 is, so just return the one
        # from the first entry
        return self._sub_entries[0].field_5

    @property
    def scene_list(self):
        # Presumably all sub-entries have the same scene list data
        return self._sub_entries[0].scene_list

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
