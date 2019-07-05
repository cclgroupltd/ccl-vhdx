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
__description__ = "Prints metadata from a VHDX file"
__contact__ = "Alex Caithness"

import sys
import pathlib
import uuid
import ccl_vhdx


def print_metas(metas):
    for key in metas:
        if key == "Page83Data":
            print(f"{key}:\t{uuid.UUID(bytes_le=metas[key])} ({metas[key].hex()})")
        elif key == "HasParent":
            print(f"{key} (is differencing):\t{metas[key]}")
        elif key == "ParentLocator":
            print(f"{key}:")
            for subkey in metas[key]:
                print(f"\t{subkey}:\t{metas[key][subkey]}")
        else:
            print(f"{key}:\t{metas[key]}")


def main(args):
    in_path = pathlib.Path(args[0])
    print(in_path)

    metas = None

    try:
        vhdx = ccl_vhdx.VhdxFile(in_path)
        metas = vhdx.metas

    except ccl_vhdx.VhdxError as e:
        print("Couldn't read VHDX using standard methods")
        print(f"Error: {e}")

    if metas:
        print_metas(metas)

    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        me = pathlib.Path(sys.argv[0]).name
        print("Gets metadata from a VHDX file")
        print(f"USAGE: {me} <vhdx_file_path>")
        print()
        print("vhdx_file_path: Path to the VHDX file")
        print()
        exit(0)
    main(sys.argv[1:])
