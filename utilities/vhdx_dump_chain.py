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
__description__ = "Dumps a full image from a chain of differencing VHDX files"
__contact__ = "Alex Caithness"

import sys
import pathlib
import ccl_vhdx

# TODO: define a way for providing fallback metas?


def main(args):
    out_path = pathlib.Path(args[0])
    is_resilient = True

    virtual_disks = []
    for i, p in enumerate(args[1:]):
        fallback_meta = dict(ccl_vhdx.SENSIBLE_FALLBACK_METAS)
        fallback_meta["HasParent"] = i != 0
        vhdx_path = pathlib.Path(p)
        if not vhdx_path.is_file():
            print(f"ERROR: \"{p}\" does not exist.")
            exit(1)

        v = ccl_vhdx.VhdxFile(vhdx_path, ignore_faults=is_resilient, fallback_metas=fallback_meta)
        if i == 0 and v.metas["HasParent"]:
            print("ERROR: The first VHDX cannot be differencing.")
            exit(1)

        virtual_disks.append(v)

    if not virtual_disks:
        print("ERROR: You must provide at least one VHDX file as input")

    # we take the sector count from the base vhdx
    sector_count = virtual_disks[0].virtual_disk_size // virtual_disks[0].logical_sector_size

    with out_path.open("xb") as out:
        for sector_number in range(sector_count):
            allocated_vhdx = None
            for i in range(len(virtual_disks) - 1, -1, -1):
                if virtual_disks[i].is_sector_allocated(sector_number):
                    allocated_vhdx = virtual_disks[i]
                    break
            if allocated_vhdx is None:
                raise ValueError(f"No disk was allocated for sector {sector_number}")  # should be impossible
            out.write(allocated_vhdx.get_sector(sector_number))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        me = pathlib.Path(sys.argv[0]).name
        print("Dumps allocated data from a chain of VHDX files into an image file, attempting to deal with missing/"
              "invalid data")
        print(f"USAGE: {me} <out_file_path> [vhdx_file 1] [vhdx_file 2] ...")
        print()
        print("out_file_path: Output file (cannot already exist)")
        print("vhdx_file:     One or more VHDX files, ordered parent first")
        print()
        exit(0)
    main(sys.argv[1:])
