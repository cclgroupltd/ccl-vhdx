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
__description__ = "Dumps the allocated areas of the VHDX file into a single or multiple files"
__contact__ = "Alex Caithness"

import sys
import pathlib
import ccl_vhdx

# TODO: define a way for providing fallback metas and possibly the BAT offset?


def main(args):
    in_file_path = pathlib.Path(args[0])
    out_dir_path = pathlib.Path(args[1])
    single_image = "-s" in args[2:] or "--single-image" in args[2:]
    is_resilient_mode = "-r" in args[2:] or "--resilient" in args[2:]
    is_differencing = "-d" in args[2:] or "--is-differencing" in args[2:]

    default_metas = dict(ccl_vhdx.SENSIBLE_FALLBACK_METAS)
    default_metas["HasParent"] = is_differencing

    vhdx = ccl_vhdx.VhdxFile(in_file_path, ignore_faults=is_resilient_mode, fallback_metas=default_metas)

    if out_dir_path.is_dir():
        print(f"ERROR: {out_dir_path} already exists")
    out_dir_path.mkdir()

    out = None
    if single_image:
        out = (out_dir_path / "vhdx_dump_000000000000.bin").open("wb")

    sector_count = vhdx.metas["VirtualDiskSize"] // vhdx.metas["LogicalSectorSize"]
    for sector in range(sector_count):
        if vhdx.is_sector_allocated(sector) or single_image:
            if out is None:
                out = (out_dir_path / f"vhdx_dump_{sector:012}").open("wb")
            out.write(vhdx.get_sector(sector))
        else:
            if out is not None:
                out.close()
                out = None


if __name__ == '__main__':
    if len(sys.argv) < 3:
        me = pathlib.Path(sys.argv[0]).name
        print("Dumps allocated space in the VHDX to files")
        print(f"USAGE: {me} <vhdx_file_path>  <out_dir> [-s | --single-image] "
              f"[-r | --resilient] [-d | --is-differencing]")
        print()
        print("vhdx_file_path:         Path to the VHDX file")
        print("out_dir:                Path to output directory (cannot already exist)")
        print("-s | --single-image:    Dump data to a single (potentially sparse) file")
        print("-r | --resilient:       Attempt to deal with invalid/missing data")
        print("-d | --is-differencing: Input file is a differencing VHDX")
        print()
        exit(0)
    main(sys.argv[1:])
