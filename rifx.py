import struct

_RIFX_MAGIC_NUMBERS = b"RIFX"
_LIST_CHUNK_ID = b"LIST"


class RIFXListBegin:
    def __init__(self, identifier):
        self.identifier = identifier


class RIFXListEnd:
    def __init__(self, identifier=None):
        self.identifier = identifier


class RIFXChunk:
    def __init__(self, identifier, data):
        self.identifier = identifier
        self.data = data


class RIFXReader:
    def __init__(self, stream):
        self.stream = stream
        self.current_list_identifier_path = []
        self._list_end_stack = []

        header = self.stream.read(12)
        magic_numbers, size, self.identifier = struct.unpack(">4sI4s", header)
        if magic_numbers != _RIFX_MAGIC_NUMBERS:
            raise TypeError(
                f"Wrong magic numbers: {magic_numbers}, should be {_RIFX_MAGIC_NUMBERS}"
            )

        self._list_end_stack.append(size + 8)

    def __iter__(self):
        return self

    def __next__(self):
        current_position = self.stream.tell()
        current_list_end = self._list_end_stack[-1]
        if current_position > current_list_end:
            raise ValueError(
                f"read further than current list size: {current_position} > {current_list_end}"
            )
        if current_position == current_list_end:
            self._list_end_stack.pop()
            if not self.current_list_identifier_path:
                raise StopIteration()
            return RIFXListEnd(self.current_list_identifier_path.pop())
        chunk_id, chunk_size = struct.unpack(">4sI", self.stream.read(8))
        read_size = _ensure_even(chunk_size)
        if chunk_id == _LIST_CHUNK_ID:
            self._list_end_stack.append(self.stream.tell() + read_size)
            list_id = self.stream.read(4)
            self.current_list_identifier_path.append(list_id)
            return RIFXListBegin(list_id)
        else:
            return RIFXChunk(chunk_id, self.stream.read(read_size)[:chunk_size])


class RIFXWriter:
    def __init__(self, identifier, stream):
        self.stream = stream
        self._list_size_position_stack = []

        self.stream.write(struct.pack(">4sI4s", _RIFX_MAGIC_NUMBERS, 0, identifier))

        self._list_size_position_stack.append(4)

    def write(self, obj):
        if isinstance(obj, RIFXChunk):
            chunk_size = len(obj.data)
            self.stream.write(
                struct.pack(">4sI", obj.identifier, chunk_size)
                + obj.data
                + (b"\0" if chunk_size % 2 else b"")
            )
        elif isinstance(obj, RIFXListBegin):
            self._list_size_position_stack.append(self.stream.tell() + 4)
            self.stream.write(struct.pack(">4sI4s", _LIST_CHUNK_ID, 0, obj.identifier))
        elif isinstance(obj, RIFXListEnd):
            list_size_position = self._list_size_position_stack.pop()
            current_position = self.stream.tell()
            self.stream.seek(list_size_position)
            self.stream.write(
                struct.pack(">I", current_position - (list_size_position + 4))
            )
            self.stream.seek(current_position)


def _ensure_even(num):
    return (num + 1) & ~1


def rifx_to_tree(stream):
    reader = RIFXReader(stream)
    root = []
    tree = (reader.identifier, root)
    current = root
    ascendants = []
    for event in reader:
        if isinstance(event, RIFXListBegin):
            ascendants.append(current)
            descendants = []
            current.append((event.identifier, descendants))
            current = descendants
        elif isinstance(event, RIFXListEnd):
            current = ascendants.pop()
        else:
            current.append((event.identifier, event.data))
    return tree


def tree_to_rifx(tree, stream):
    writer = RIFXWriter(tree[0], stream)
    _write_tree_list(tree[1], writer)
    writer.write(RIFXListEnd())


def _write_tree_list(list_, writer):
    for item in list_:
        if isinstance(item[1], bytes):
            writer.write(RIFXChunk(item[0], item[1]))
            continue
        writer.write(RIFXListBegin(item[0]))
        _write_tree_list(item[1], writer)
        writer.write(RIFXListEnd())
