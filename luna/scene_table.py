import ast


class SceneTable:
    # Scene table consists of a list of 2-element lists, ehere the first
    # element is the scene name (e.g. '01_00_ARC01_4_1') and the second element
    # is a list of pages, each a list of text offsets that occur in that file.
    # The text offets also contain some format modifiers from the script
    def __init__(self, filename):
        # Open source file and split out each line
        with open(filename, "r+", encoding="utf-8") as f:
            data = f.read()

        # Split data on newlines
        lines = data.split('\n')

        # Run each element in the table through literal_eval
        # TODO(ross): I am screaming
        parsed_lines = [ast.literal_eval(elem) for elem in lines]

        # Convert the data into a map keyed off of scene name
        self._scene_to_text_offsets = {}
        for row in parsed_lines:
            if not row:
                continue
            assert len(row) == 2, "Invalid scene table entry '%s'" % row
            self._scene_to_text_offsets[row[0]] = row[1]

    def scene_names(self):
        return [v for v in self._scene_to_text_offsets.keys()]

    def offsets_for_scene(self, scene_name):
        return self._scene_to_text_offsets.get(scene_name)

    def all_scenes(self):
        return self._scene_to_text_offsets.values()
