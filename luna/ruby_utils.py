class RubyUtils:

    ENABLE_PUA_CODES = False

    @staticmethod
    def unicode_aware_len(string):
        # Any non-ASCII character takes up 2 spaces instead of one.
        length = 0
        for c in string:
            # PUA codes are treated as single-width
            if ord(c) >= 0xE000:
                length += 1
            # All non-EASCII is double-wide
            elif ord(c) > 256:
                length += 2
            else:
                length += 1

        return length

    @classmethod
    def noruby_len(cls, line):
        # Get the length of a line as if it did not contain any ruby text
        try:
            return cls.unicode_aware_len(cls.remove_ruby_text(line))
        except AssertionError as e:
            # There are non-conformant lines in the current script.
            # Fail gracefully
            print(e)
            return cls.unicode_aware_len(line)

    @staticmethod
    def ruby_aware_split_words(line):
        # Split a line into words, but consider ruby groups to be a
        # single word.
        ret = []
        acc = ""
        processing_ruby = False
        for c in line:
            # Begin ruby group?
            if c == '<':
                assert not processing_ruby, \
                    f"Encountered repeated ruby-start in line '{line}'"
                processing_ruby = True

            # End ruby group?
            if c == '>':
                assert processing_ruby, \
                    f"Encountered ruby-end without ruby-start in line '{line}'"
                processing_ruby = False

            # If we see a space and are _not_ inside a ruby group, copy the
            # accumulator to the output list and zero it out
            if (c == ' ' or c == '\n') and not processing_ruby:
                ret.append(acc)
                # Preserve line breaks
                if c == '\n':
                    ret.append("\n")
                acc = ""
                continue

            # If this is not a space, or is a space but we are inside a
            # ruby group, append to current word accumulator.
            acc = acc + c

        # If the accumulator is non-empty, append to the return vector
        if acc:
            ret.append(acc)

        return ret

    @staticmethod
    def remove_ruby_text(line):
        # Ruby text consists of <bottom|top> text.
        # This function strips formatting characters and top text to get only
        # the baseline-level characters in a sentence.
        ret = ""
        processing_ruby = False
        seen_midline = False

        # Iterate each character in the line
        for c in line:

            # Is this the start of a ruby?
            if c == '<':
                # Sequential starts are likely an error in the input
                assert not processing_ruby, \
                    "Repeated ruby-start encountered in line '{line}'"

                processing_ruby = True
                seen_midline = False
                continue

            # Is this a ruby midline?
            if c == '|':
                assert processing_ruby, \
                    f"Found ruby-delimiter in non-ruby text for line '{line}'"
                seen_midline = True
                continue

            # Is this a ruby end?
            if c == '>':
                assert processing_ruby, \
                    f"Found ruby-end outside ruby context for line '{line}'"
                assert seen_midline, \
                    f"Found ruby-end without ruby-delimiter for line '{line}'"
                processing_ruby = False
                seen_midline = True
                continue

            # If this is a normal character, then append it to the output IFF
            # - We are outside a ruby context _or_
            # - We are indisde a ruby context but are before the midline
            if not processing_ruby or not seen_midline:
                ret = ret + c

        return ret

    @classmethod
    def apply_control_codes(cls, text, enable_asserts=False):
        # Convert any custom control codes into the appropriate
        # characters/control modes.
        #
        # %{n}: Force newline
        # %{s}: Force space
        # %{i}/%{/i}: Begin/end italics
        # %{r}/%{/r}: Begin/end reverse
        # %{ri}/%{/ri}: Begin/end reverse italics
        # %{g}/%{/g}: Begin/end Antiqua font
        PUA_OFFSET = 0xE000

        processed_line = ""
        has_pct = False  # Did we see a % that might open a cc
        in_cc = False  # Are we inside a control code segment
        cc_acc = ""
        glyph_offset = None
        for c in text:
            # Handle control mode entry
            if c == '%':
                has_pct = True
                continue

            # If we see percent then {, open a command context
            # If we see percent then anything else, the percent was literal.
            if has_pct:
                if c == '{':
                    in_cc = True
                    has_pct = False
                    cc_acc = ""
                    continue
                else:
                    in_cc = False
                    has_pct = False
                    cc_acc = ""
                    processed_line += "%" + c
                    continue

            # If we hit the end of a control code, see what the command was
            if in_cc and c == '}':
                in_cc = False

                # What was the acc?
                if cc_acc == 'n':
                    # Forced newline
                    processed_line += "\n"
                elif cc_acc == 's':
                    # Forced space
                    processed_line += " "
                elif cc_acc == 'nothing':
                    # Used as a token to allow empty lines
                    processed_line += ""
                elif cc_acc == 'force_glue':
                    # Handled in tl_db, non-printing.
                    processed_line += ""
                elif cc_acc == 'i':
                    # Offset ascii glyphs into the italic text region
                    assert not enable_asserts or glyph_offset is None, \
                        f"Illegal nested i in line {text}"
                    if cls.ENABLE_PUA_CODES:
                        glyph_offset = PUA_OFFSET + 128 * 0
                elif cc_acc == 'r':
                    # Offset ascii glyphs into the reverso text region
                    assert not enable_asserts or glyph_offset is None, \
                            f"Illegal nested r in line {text}"
                    if cls.ENABLE_PUA_CODES:
                        glyph_offset = PUA_OFFSET + 128 * 1
                elif cc_acc == 'ri':
                    # Offset ascii glyphs into the reversed italics text region
                    assert not enable_asserts or glyph_offset is None, \
                        f"Illegal nested ri in line {text}"
                    if cls.ENABLE_PUA_CODES:
                        glyph_offset = PUA_OFFSET + 128 * 2
                elif cc_acc == 'g':
                    # Offset ascii glyphs into the antiqua region
                    assert not enable_asserts or glyph_offset is None, \
                        f"Illegal nested g in line {text}"
                    if cls.ENABLE_PUA_CODES:
                        glyph_offset = PUA_OFFSET + 128 * 3
                elif cc_acc[0] == '/':
                    is_in_tag = \
                        not cls.ENABLE_PUA_CODES or glyph_offset is not None
                    assert not enable_asserts or is_in_tag, \
                        f"Unmatched closing tag {cc_acc} in line {text}"
                    glyph_offset = None
                else:
                    assert False, \
                        f"Unhandled control code '{cc_acc}' in line '{text}'"

                continue

            # Non-control mode: just append character to output buffer
            if not in_cc:
                # If we have a glyph offset and this is a non-whitespace ASCII
                # char, map it to the right font region
                is_whitespace = c == ' ' or c == '\n'
                if glyph_offset and ord(c) < 128 and not is_whitespace:
                    processed_line += chr(ord(c) + glyph_offset)
                else:
                    processed_line += c
            else:
                # CC mode: accumulate cc chars until cc end
                cc_acc += c

        assert not enable_asserts or glyph_offset is None, \
            f"Unclosed tag on line {text}"

        return processed_line

    @classmethod
    def linebreak_text(cls, line, max_linelen, start_cursor_pos=0):
        # If the line is already shorter than the desired length, just return
        if cls.noruby_len(line) + start_cursor_pos <= max_linelen:
            return(line)

        # Split the line into a list of words, where ruby groups count
        # as a single word
        splitLine = cls.ruby_aware_split_words(line)

        # If the length of the longest element in the line is larger than our
        # allotted limit, we can't break this line
        if max_linelen < max([cls.noruby_len(elem) for elem in splitLine]):
            return(line)

        # Actually break up the line
        broken_lines = []
        acc = ""
        first_word = True
        for word in splitLine:
            # If adding the next word would overflow, break the line.
            len_if_added = cls.noruby_len(acc + ' ' + word) + start_cursor_pos
            if len_if_added > max_linelen:
                broken_lines.append(acc)
                # If we line break _right_ at 55 chars, and the next char is
                # a _forced_ linebreak, we'd end up double-breaking.
                if word == "\n":
                    acc = ""
                    first_word = True
                else:
                    acc = word
                    first_word = False
                start_cursor_pos = 0
                continue

            # If we run into a raw \n, that directly breaks the line
            if word == '\n':
                broken_lines.append(acc)
                acc = ""
                start_cursor_pos = 0
                first_word = True
                continue

            # If we did't just break, then append this word to the line
            acc = acc + ' ' + word if not first_word else word
            first_word = False

        # If there is a trailing accumulator, append it now.
        # If the final character in the string was a newline, the accumulator
        # will be empty but still meaningful, so keep it.
        if acc or splitLine[-1] == '\n':
            broken_lines.append(acc)

        # Join our line fragments back together with \n
        ret = '\n'.join(broken_lines)
        return ret
