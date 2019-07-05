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
__description__ = "Dumps information about the BAT, optionally printing an allocation map"
__contact__ = "Alex Caithness"

import sys
import pathlib
import ccl_vhdx

# TODO: define a way for providing fallback metas and possibly the BAT offset?


def main(args):
    in_path = pathlib.Path(args[0])
    print(in_path)

    vhdx = ccl_vhdx.VhdxFile(in_path, ignore_faults=True, fallback_metas=ccl_vhdx.SENSIBLE_FALLBACK_METAS)
    bat_offset = vhdx.region_table[ccl_vhdx.guid_to_blob(ccl_vhdx.REGION_GUID_BAT)].offset
    bat_length = vhdx.region_table[ccl_vhdx.guid_to_blob(ccl_vhdx.REGION_GUID_BAT)].length

    print(f"BAT offset: {bat_offset}")
    print(f"BAT region length (bytes): {bat_length}")
    print(f"BAT entry count (max): {bat_length // 8}")

    allocated_block_count = 0
    allocation = []
    for entry in vhdx.iter_bat_payload_entries():
        if entry.state in (ccl_vhdx.BatPayloadBlockState.BAT_PAYLOAD_BLOCK_FULLY_PRESENT,
                           ccl_vhdx.BatPayloadBlockState.BAT_PAYLOAD_BLOCK_PARTIALLY_PRESENT):
            allocated_block_count += 1
            allocation.append(True)
        else:
            allocation.append(False)
    print(f"Allocated* Payload Block Count: {allocated_block_count}")
    print()
    print("*at least partially")
    print()

    if "-m" in args[1:] or "--map" in args[1:]:
        print("Allocation Map:")
        line_length = 128
        for i in range(0, bat_length // 8, line_length):
            print("".join("1" if x else "0" for x in allocation[i:i+line_length]))

        print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        me = pathlib.Path(sys.argv[0]).name
        print("Gets information about the BAT, optionally printing an allocation map")
        print(f"USAGE: {me} <vhdx_file_path> [-m | --map]")
        print()
        print("vhdx_file_path: Path to the VHDX file")
        print("-m | --map:     Print an allocation map")
        print()
        exit(0)

    main(sys.argv[1:])
