# python-rifx

rifx is a Python module for reading RIFX files. These are files which start with the magic numbers RIFX.

An example is Adobe After Effects .aep project files.

With this library you can interpret the data structure in such a file, modify it and write it out.

## Example

Here's a hasty, ropey little example of swapping out the read and write paths in an .aep:

```
import os
import json

import rifx


def generate_aep(template_path, read_path, write_path, output_path):
    write_dir_path = os.path.dirname(write_path)
    write_file_name = os.path.basename(write_path)
    with open(template_path, "rb") as template_stream, open(output_path, "wb") as output_stream:
        template_reader = rifx.RIFXReader(template_stream)
        output_writer = rifx.RIFXWriter(template_reader.identifier, output_stream)
        utf8_count = 0
        for item in template_reader:
            if isinstance(item, rifx.RIFXChunk):
                if item.identifier == b"alas":
                    if template_reader.current_list_identifier_path == [b"Fold", b"Item", b"Pin ", b"Als2"]:
                        item = rifx.RIFXChunk(item.identifier, json.dumps(dict(fullpath=read_path), separators=(",", ":")).encode("utf-8"))
                    elif template_reader.current_list_identifier_path == [b"LRdr", b"LItm", b"LOm ", b"Als2"]:
                        item = rifx.RIFXChunk(item.identifier, json.dumps(dict(fullpath=write_dir_path)).encode("utf-8"))
                elif item.identifier == b"Utf8" and template_reader.current_list_identifier_path == [b"LRdr", b"LItm", b"LOm "]:
                    utf8_count += 1
                    if utf8_count == 2:
                        item = rifx.RIFXChunk(item.identifier, write_file_name.encode("utf-8"))
            output_writer.write(item)
        output_writer.write(rifx.RIFXListEnd())
        output_stream.write(template_stream.read())
```
