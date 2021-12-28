import struct

class Mzp:
    MAGIC = b"mrgd00"

    class EntryHeader:
        HEADER_FORMAT = "<HHHH"
        SECTOR_SIZE = 0x800

        def __init__(self, data):
            (self._sector_offset,
             self._byte_offset,
             self._size_sectors,
             self._size_bytes) = struct.unpack(self.HEADER_FORMAT, data[0:8])

        def __repr__(self):
            return f"EntryHeader<{self._sector_offset}, {self._byte_offset}, {self._size_sectors}, {self._size_bytes}>"

        def relative_start_offset(self):
            return self._sector_offset * self.SECTOR_SIZE + self._byte_offset

        def data_size(self):
            upper_bound = self._size_sectors * self.SECTOR_SIZE
            return (upper_bound & ~(0xFFFF)) | self._size_bytes


    def __init__(self, input_path):
        with open(input_path, 'rb') as input_file:
            raw_data = input_file.read()

        # Data are LE
        # 6 byte magic, uint16_t entry count
        (self._magic, self._entry_count) = struct.unpack("<6sH", raw_data[0:8])

        assert self._magic == self.MAGIC, self._magic

        # Parse the headers
        data_view = memoryview(raw_data)
        self.headers = []
        for i in range(self._entry_count):
            self.headers.append(Mzp.EntryHeader(data_view[8 + 8 * i:]))

        # Load the data
        self.data = []
        data_start_offset= 8 + 8 * self._entry_count
        for header in self.headers:
            entry_start = data_start_offset + header.relative_start_offset()
            self.data.append(raw_data[
                entry_start:entry_start+header.data_size()])
