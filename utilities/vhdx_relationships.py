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
__description__ = "Prints the fields related to determining relationships between VHDX files for files in a directory " \
                  "tree"
__contact__ = "Alex Caithness"

import sys
import pathlib
import os
import ccl_vhdx


def slash_r(path: os.PathLike):
    root = pathlib.Path(path)
    stack = [root]
    while stack:
        current = stack.pop(-1)
        for p in current.iterdir():
            if p.is_file():
                yield p
            elif p.is_dir():
                stack.append(p)


def check_header(path: os.PathLike):
    with pathlib.Path(path).open("rb") as f:
        header = f.read(len(ccl_vhdx.VHDX_MAGIC))
        if header == ccl_vhdx.VHDX_MAGIC:
            return True
        return False


def main(args):
    root = pathlib.Path(args[0])
    ignore_faults = "-r" in args[1:] or "--resilient" in args[1:]

    # pass one get the files
    files = []
    for p in slash_r(root):
        if check_header(p):
            files.append(p)

    # pass two get metadata
    details = []
    for p in files:
        vhdx = ccl_vhdx.VhdxFile(p, fallback_metas=ccl_vhdx.SENSIBLE_FALLBACK_METAS, ignore_faults=ignore_faults)
        if not vhdx.header.data_write_guid:
            print(f"File \"{p}\" does not have a DataWriteGuid set.")
            print()
        metas = None
        if vhdx.used_fallback_metas:
            print(f"File \"{p}\" used fallback metadata")
            print()
        else:
            metas = vhdx.metas

        details.append((p, vhdx.header, metas))

    print("Report starts:")
    print("--------------")

    print(",".join(["Local Path", "Data Write GUID", "Sequence Number",
                    "Has Parent?", "Parent Data Write GUID", "Parent Volume Path"]))

    for detail in details:
        if not detail[2]:
            parent_linkage = "?"
            volume_path = "?"
        elif "ParentLocator" not in detail[2]:
            parent_linkage = "-"
            volume_path = "-"
        else:
            parent_linkage = ccl_vhdx.guid_to_blob(detail[2]["ParentLocator"]["parent_linkage"].strip("{}")).hex()
            volume_path = detail[2]["ParentLocator"]["volume_path"]

        print(",".join(str(x) for x in [
            detail[0],  # path
            detail[1].data_write_guid.hex(),
            detail[1].sequence_number,
            detail[2]["HasParent"] if detail[2] else "?",
            parent_linkage,
            volume_path
        ]))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        me = pathlib.Path(sys.argv[0]).name
        print("Prints the fields related to determining relationships between VHDX files for files in a directory tree")
        print(f"USAGE: {me} <root_dir> [-r | --resilient]")
        print()
        print("vhdx_file_path: Root of directory structure containing VHDX files")
        print("-m | --map:       Print an allocation map")
        print("-r | --resilient: Attempt to deal with invalid/missing data")
        print()
        exit(0)
    main(sys.argv[1:])
