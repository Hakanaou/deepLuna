import os
import struct
from io import BytesIO


class Mzx:
    CMD_RLE = 0
    CMD_BACKREF = 1
    CMD_RINGBUF = 2
    CMD_LITERAL = 3

    @classmethod
    def decompress(cls, data, invert=True):
        # Check header
        (magic, decompressed_size) = struct.unpack("<4sI", data[0:8])
        assert magic == b"MZX0", magic

        # Output buffer
        ret = BytesIO()

        # Last written short
        last_short = b'\xff\xff' if invert else 0x0000

        # Prev data ringbuffer
        ring_buffer_write_offset = 0
        ring_buffer = [b'\xff\xff' if invert else b'\x00\x00'] * 64

        # Input file read index. Start after the fixed-size header.
        read_offset = 8

        # While we have not decompressed all data
        while ret.tell() < decompressed_size:
            # Read the cmd/len from the next input byte
            len_cmd = data[read_offset]
            read_offset += 1

            # Extract the actual command and length
            cmd = len_cmd & 0b11
            length = len_cmd >> 2

            if cmd == cls.CMD_RLE:
                # Repeat last 2 bytes len+1 times
                ret.write(last_short * (length + 1))

            if cmd == cls.CMD_BACKREF:
                # How far back are we referencing
                lookback_dist = 2 * (data[read_offset] + 1)
                read_offset += 1

                # Copy len shorts from backreference
                for _ in range(length+1):
                    ret.seek(-lookback_dist, os.SEEK_CUR)
                    last_short = ret.read(2)
                    ret.seek(0, os.SEEK_END)
                    ret.write(last_short)

            if cmd == cls.CMD_RINGBUF:
                last_short = ring_buffer[length]
                ret.write(last_short)

            if cmd == cls.CMD_LITERAL:
                for _ in range(length+1):
                    # Read next short literal from input
                    literal = data[read_offset:read_offset+2]
                    read_offset += 2

                    # Convert to byte string
                    literal_bytes = bytes([
                        byte ^ (0xFF if invert else 0x00) for byte in literal
                    ])

                    # Update last / ring buffer
                    last_short = literal_bytes
                    ring_buffer[ring_buffer_write_offset] = literal_bytes
                    ring_buffer_write_offset = (
                        (ring_buffer_write_offset + 1) % 64
                    )

                    # Write data to output
                    ret.write(last_short)

        ret.truncate(decompressed_size)
        ret.seek(0)
        return ret.read()
