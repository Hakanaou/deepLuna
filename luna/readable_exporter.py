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

    If the translated text spans multiple lines, those line breaks _WILL NOT_ be
    included when the text is imported.

        Note that _leading_ spaces are not stripped from translation lines

    However, _trailing_ spaces WILL be stripped. Account for manual spacing only
    at the front of translations.
    }
    """

    class ParseError(Exception):
        def __init__(self, *args, **kwargs):
            super(ReadableExporter.ParseError, self).__init__(*args, **kwargs)

    class LexState:
        EXPECT_BLOCK = 0
        PARSE_CONTENT_HASH = 1
        EXPECT_OPEN_BLOCK = 2
        DEFAULT_BLOCK = 3
        PARSE_MACHINE_COMMENT = 4
        PARSE_HUMAN_COMMENT = 5

    @classmethod
    def import_text(cls, file_text):
        # Generates a map of hash -> TLLine
        ret = {}

        state = cls.LexState.EXPECT_BLOCK
        cmd_acc = ""
        active_content_hash = None
        line_counter = 0
        brace_count = 0
        translated_text = ""
        human_comments = ""
        for i in range(len(file_text)):
            c = file_text[i]
            if c == '\n':
                line_counter += 1

            # Are we waiting for the start of a block?
            if state == cls.LexState.EXPECT_BLOCK:
                # Ignore whitespace
                if c in "\r\n ":
                    continue

                # If we get an open content hash spec '[', transition states
                if c == '[':
                    state = cls.LexState.PARSE_CONTENT_HASH
                    cmd_acc = ""
                    continue

                raise cls.ParseError(
                    f"Unexpected token '{c}' on "
                    f"line {line_counter} while in state EXPECT_BLOCK"
                )

            # Are we processing the content-hash specifier for a block?
            if state == cls.LexState.PARSE_CONTENT_HASH:
                # Ignore whitespace
                if c in "\r\n ":
                    continue

                # End of block?
                if c == ']':
                    # Hit the end of the [] block - the accumulator now holds
                    # the content hash context for the next scoped region.
                    state = cls.LexState.EXPECT_OPEN_BLOCK
                    active_content_hash = cmd_acc
                    cmd_acc = ""
                    continue

                # All content hashes must be valid lowercase hex
                if c not in '0123456789abcdef':
                    raise cls.ParseError(
                        f"Invalid character '{c}' in "
                        f"content hash on line {line_counter}"
                    )

                # Accumulate the character onto the cmd_acc buffer
                cmd_acc += c

            # Consume whitespace chars until we get to an open-brace
            if state == cls.LexState.EXPECT_OPEN_BLOCK:
                # Ignore whitespace
                if c in "\r\n ":
                    continue

                # Open block?
                if c == '{':
                    # Now properly inside a context block
                    brace_count += 1
                    state = cls.LexState.DEFAULT_BLOCK
                    cmd_acc = ""
                    continue

                raise cls.ParseError(
                    "Expected open-block after block-specifier "
                    f"but found '{c}' on line {line_counter}"
                )

            # Consume until we hit a close-block '}'. Accumulate lines into
            # cmd_acc until we hit either a newline or comment char, at which
            # point we would latch the buffer and transition to the next
            # appropriate state
            if state == cls.LexState.DEFAULT_BLOCK:
                # Hit a newline?
                if c == '\n':
                    # If there is a valid line in the input buffer, add it to
                    # the translation text
                    rstrip_acc = cmd_acc.rstrip()
                    if rstrip_acc:
                        translated_text += rstrip_acc
                    # Reset the accumulator
                    cmd_acc = ""
                    continue

                # Track open-brace chars so that if any show up in the
                # translated text we match them and don't get confused
                if c == '{':
                    brace_count += 1

                # Hit an end-brace?
                if c == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # This is a terminating brace - process the accumulated
                        # command buffer and transition back to default state
                        rstrip_acc = cmd_acc.rstrip()
                        if rstrip_acc:
                            translated_text += rstrip_acc
                        cmd_acc = ""

                        # Create a new entry in our return map
                        # If there is no valid tl or comments, use None instead
                        # of empty string as an indicator
                        ret[active_content_hash] = (
                            translated_text or None,
                            human_comments or None
                        )
                        translated_text = ""
                        human_comments = ""

                        # Move back to default state
                        state = cls.LexState.EXPECT_BLOCK
                        continue

                # Is this the second char in a -- quote?
                if c == '-' and cmd_acc and cmd_acc[-1] == '-':
                    # Bank any translation text, excluding the prev '-'
                    rstrip_acc = cmd_acc[:-1].rstrip()
                    if rstrip_acc:
                        translated_text += rstrip_acc
                    cmd_acc = ""

                    # Open machine comment context
                    state = cls.LexState.PARSE_MACHINE_COMMENT
                    continue

                # Is this the second char in a // quote?
                if c == '/' and cmd_acc and cmd_acc[-1] == '/':
                    # Bank any translation text, excluding prev '/'
                    rstrip_acc = cmd_acc[:-1].rstrip()
                    if rstrip_acc:
                        translated_text += rstrip_acc
                    cmd_acc = ""

                    # Open human comment context
                    state = cls.LexState.PARSE_HUMAN_COMMENT
                    continue

                # If nothing special is going on, just add this char to the buf
                cmd_acc += c

            # Currently reading a machine comment. Discard until we see EOL
            if state == cls.LexState.PARSE_MACHINE_COMMENT:
                if c == '\n':
                    state = cls.LexState.DEFAULT_BLOCK
                    cmd_acc = ""

            # Currently reading a human comment. Accumulate characters until
            # we hit EOL, then append to comment block
            if state == cls.LexState.PARSE_HUMAN_COMMENT:
                if c == '\n':
                    # If the comment was non-empty, save it
                    strip_acc = cmd_acc.strip()
                    if strip_acc:
                        human_comments += strip_acc + "\n"
                    cmd_acc = ""

                    state = cls.LexState.DEFAULT_BLOCK
                    continue

                # Append the character to the cmd_buf
                cmd_acc += c

        return ret

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
