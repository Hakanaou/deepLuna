class ReadableExporter:
    """
    Human-readable export format is as follows:

    // Each line context block is opened with a
    [baa173e] { // Where the value in the [] is the content hash of a jp line
    // Any lines prefixed with a '//' are kept as human readable comments
    -- Any lines prefixed with a '--' are automatically generated comments,
    -- and will not be re-imported to the comment field
    Any lines that are not prefixed with a comment marker are considered to
    be translated text.

    // Comments may be interspersed with the translation, either on their own line
    This is translation text// Or after a specific line of the translation
    // However, when imported and reexported, all comments will be consolidated at
    // the top of the context block.

    If the translated text spans multiple lines, those line breaks _WILL_ be
    included when the text is imported.

        Note that _leading_ spaces are not stripped from translation lines

    However, _trailing_ spaces WILL be stripped. Account for manual spacing only
    at the front of translations.
    }
    """

    @staticmethod
    def import_text(file_text):
        pass

    @staticmethod
    def export_text(translation_db, scene_name):
        # Get the line info for this scene
        scene_lines = translation_db.lines_for_scene(scene_name)

        ret = ""

        # Start accumulating context blocks
        for line in scene_lines:
            # Get the associated TL line
            tl_info = translation_db.tl_line_with_hash(line.jp_hash)

            # Automated context comments
            glued = " Glued." if line.is_glued else ""
            choice = " Choice." if line.is_choice else ""
            mods = " Mods: %s." % ', '.join(line.modifiers) if line.modifiers else ""
            generated_comment = (
                f"-- Page {line.page_number}, Offset {line.offset}."
                f"{glued}{choice}{mods}\n"
                f"-- {tl_info.jp_text.strip()}"
            )

            # Collate human comments and prepend //
            human_comment = ""
            if tl_info.comment:
                for comment in tl_info.comment.split("\n"):
                    human_comment += f"// {comment}\n"

            # If there is no translation, leave a machine comment
            tl_text = (
                tl_info.en_text if tl_info.en_text
                else '-- TRANSLATION HERE'
            )

            ret += (
                f"[{line.jp_hash}]"
                 "{\n"
                f"{generated_comment}\n"
                f"{human_comment}"
                f"{tl_text}\n"
                 "}\n"
            )

        return ret
