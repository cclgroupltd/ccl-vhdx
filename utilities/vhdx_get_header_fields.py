"""
Copyright 2019, CCL (SOLUTIONS) Group Ltd.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = "0.1.0"
__description__ = "Prints header fields from a VHDX file"
__contact__ = "Alex Caithness"

import sys
import pathlib
import uuid
import ccl_vhdx

# TODO: define a way for providing fallback metas?


def main(args):
    in_path = pathlib.Path(args[0])
    print(in_path)

    try:
        vhdx = ccl_vhdx.VhdxFile(in_path, ignore_faults=True, fallback_metas=ccl_vhdx.SENSIBLE_FALLBACK_METAS)
    except ccl_vhdx.VhdxError as e:
        print("Couldn't read VHDX using standard methods")
        print(f"Error: {e}")
        exit(1)
        return

    no_log = vhdx.header.log_guid == b"\x00" * 16

    print(f"SequenceNumber: {vhdx.header.sequence_number}")
    print(f"FileWriteGuid: {uuid.UUID(bytes_le=vhdx.header.file_write_guid)} ({vhdx.header.file_write_guid.hex()})")
    print(f"DataWriteGuid: {uuid.UUID(bytes_le=vhdx.header.data_write_guid)} ({vhdx.header.data_write_guid.hex()})")
    print(f"LogGuid: {uuid.UUID(bytes_le=vhdx.header.log_guid)} ({vhdx.header.log_guid.hex()})" +
          " (no log to replay)" if no_log else "")
    print(f"LogVersion: {vhdx.header.log_version}")
    print(f"Version: {vhdx.header.version}")
    print(f"LogLength: {vhdx.header.log_length}")
    print(f"LogOffset: {vhdx.header.log_offset}")
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        me = pathlib.Path(sys.argv[0]).name
        print("Gets header information from the VHDX file")
        print(f"USAGE: {me} <vhdx_file_path>")
        print()
        print("vhdx_file_path: Path to the VHDX file")
        print()
        exit(0)
    main(sys.argv[1:])
