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

import struct
import os
import io
import typing
import enum
import pathlib

import ccl_log

__version__ = "0.1.0"
__description__ = "A module for reading from VHDX files that attempts to be resilient to damaged files"
__contact__ = "Alex Caithness"

DEBUG = True
DEBUG_TO_STDOUT = False
_l = ccl_log.Log(ccl_log.create_unique_log_name("vhdx"), show_caller=True) if DEBUG else lambda *x, **y: None

VHDX_MAGIC = b"vhdxfile"
CREATOR_LENGTH = 512

HEAD_MAGIC = b"head"

REGION_TABLE_MAGIC = b"regi"

REGION_GUID_BAT = "2DC27766-F623-4200-9D64-115E9BFD4A08"
REGION_GUID_METADATA = "8B7CA206-4790-4B9A-B8FE-575F050F886E"

METADATA_TABLE_MAGIC = b"metadata"

METADATA_FILE_PARAMETERS = "CAA16737-FA36-4D43-B3B6-33F0AA44E76B"
METADATA_VIRTUAL_DISK_SIZE = "2FA54224-CD1B-4876-B211-5DBED83BF4B8"
METADATA_PAGE_83_DATA = "BECA12AB-B2E6-4523-93EF-C309E000C746"
METADATA_LOGICAL_SECTOR_SIZE = "8141BF1D-A96F-4709-BA47-F233A8FAAB5F"
METADATA_PHYSICAL_SECTOR_SIZE = "CDA348C7-445D-4471-9CC9-E9885251C556"
METADATA_PARENT_LOCATOR = "A8D35F2D-B30B-454D-ABF7-D3D84834AB0C"

LOG_HEADER_MAGIC = b"loge"

SENSIBLE_FALLBACK_METAS = {
    "LogicalSectorSize": 512,
    "PhysicalSectorSize": 4096,
    "BlockSize": 1 << 20,
}

PARENT_LOCATOR_TYPE_VHDX = "B04AEFB7-D19E-4A81-B789-25B8E9445913"

BAT_SB_BLOCK_NOT_PRESENT = 0
BAT_SB_BLOCK_PRESENT = 6

MAX_INFERRED_SIZE = 0x8000000000


def guid_to_blob(guid_string: str):
    x = bytes.fromhex(guid_string.replace("-", ""))
    if len(x) != 16:
        raise ValueError("invalid length for a guid string")
    return x[3::-1] + x[5:3:-1] + x[7:5:-1] + x[8:]


def read_raw(f: typing.BinaryIO, count) -> bytes:
    raw = f.read(count)
    if len(raw) < count:
        raise ValueError(f"Tried to read {count} bytes at offset {f.tell() - len(raw)}, but only got {len(raw)}.")
    return raw


def read_uint16(f: typing.BinaryIO) -> int:
    return struct.unpack("<H", read_raw(f, 2))[0]


def read_uint32(f: typing.BinaryIO) -> int:
    return struct.unpack("<I", read_raw(f, 4))[0]


def read_uint64(f: typing.BinaryIO) -> int:
    return struct.unpack("<Q", read_raw(f, 8))[0]


def read_guid(f: typing.BinaryIO) -> bytes:
    return read_raw(f, 16)  # TODO: return something sensible


class VhdxError(Exception):
    pass


class VhdxHeaderError(VhdxError):
    pass


class VhdxMetadataError(VhdxError):
    pass


class Header:
    def __init__(self, checksum: int, seq_number: int, file_write_guid: bytes, data_write_guid: bytes,
                 log_guid: bytes, log_version: int, version: int, log_length: int, log_offset: int):
        self._seq_number = seq_number
        self._file_write_guid = file_write_guid
        self._data_write_guid = data_write_guid
        self._log_guid = log_guid
        self._log_version = log_version
        self._log_length = log_length
        self._log_offset = log_offset
        self._version = version

    @property
    def file_write_guid(self):
        return self._file_write_guid

    @property
    def data_write_guid(self):
        return self._data_write_guid

    @property
    def log_guid(self):
        return self._log_guid

    @property
    def log_version(self):
        return self._log_version

    @property
    def log_length(self):
        return self._log_length

    @property
    def log_offset(self):
        return self._log_offset

    @property
    def sequence_number(self):
        return self._seq_number

    @property
    def version(self):
        return self._version

    @classmethod
    def from_stream(cls, stream: typing.BinaryIO, *, ignore_faults=False):
        _l("Reading header", debug=True, to_stdout=DEBUG_TO_STDOUT)
        header_raw = read_raw(stream, 4096)
        f = io.BytesIO(header_raw)
        magic = read_raw(f, 4)
        if magic != HEAD_MAGIC:
            if ignore_faults:
                _l(f"WARNING: Invalid header magic (Expected: {HEAD_MAGIC.hex()}; got: {magic.hex()}",
                   to_stdout=DEBUG_TO_STDOUT)
            else:
                raise VhdxHeaderError(f"Invalid header magic (Expected: {HEAD_MAGIC.hex()}; got: {magic.hex()}")
        checksum = read_uint32(f)  # TODO: should we validate this as it's a way to explain failure?
        seq_number = read_uint64(f)
        file_write_guid = read_guid(f)
        data_write_guid = read_guid(f)
        log_guid = read_guid(f)
        log_version = read_uint16(f)
        version = read_uint16(f)
        log_length = read_uint32(f)
        log_offset = read_uint64(f)

        stream.seek(1024 * 60, os.SEEK_CUR)  # skip rest of this block

        if version != 1:
            if ignore_faults:
                _l(f"WARNING: Invalid version in the header (Expected: 1; got: {version})", to_stdout=DEBUG_TO_STDOUT)
            else:
                raise VhdxHeaderError(f"Invalid version in the header (Expected: 1; got: {version})")

        return cls(checksum, seq_number, file_write_guid, data_write_guid, log_guid, log_version,
                   version, log_length, log_offset)


class RegionTableEntry:
    def __init__(self, guid, file_offset: int, length: int, required: bool):
        self._guid = guid
        self._offset = file_offset
        self._length = length
        self._required = required

    @property
    def guid(self):
        return self._guid

    @property
    def offset(self):
        return self._offset

    @property
    def length(self):
        return self._length

    @classmethod
    def from_stream(cls, f: typing.BinaryIO):
        guid = read_guid(f)
        file_offset = read_uint64(f)
        length = read_uint32(f)
        flags = read_uint32(f)
        reserved = (flags & 0x01) != 0

        return cls(guid, file_offset, length, reserved)

    def __eq__(self, other: "RegionTableEntry"):
        if not isinstance(other, RegionTableEntry):
            return TypeError(f"Cannot compare RegionTableEntry with {type(other)}")

        return self.guid == other.guid and self.length == other.length and self.offset == other.offset


class RegionTable:
    def __init__(self, table_entries: dict):
        self._table_entries = table_entries

    def __len__(self):
        return len(self._table_entries)

    def __getitem__(self, item):
        return self._table_entries[item]

    def __iter__(self):
        yield from self._table_entries.keys()

    def __contains__(self, item):
        return item in self._table_entries

    @classmethod
    def from_stream(cls, stream: typing.BinaryIO, *, ignore_faults=False):
        _l("Reading region table", debug=True, to_stdout=DEBUG_TO_STDOUT)
        region_table_raw = read_raw(stream, 1024 * 64)
        f = io.BytesIO(region_table_raw)
        magic = read_raw(f, 4)
        if magic != REGION_TABLE_MAGIC:
            if ignore_faults:
                _l(f"Invalid region table magic (Expected: {REGION_TABLE_MAGIC.hex()}; got: {magic.hex()}",
                   to_stdout=DEBUG_TO_STDOUT)
            raise VhdxHeaderError(
                f"Invalid region table magic (Expected: {REGION_TABLE_MAGIC.hex()}; got: {magic.hex()}")
        checksum = read_uint32(f)  # TODO: should we validate this as it's a way to explain failure?
        entry_count = read_uint32(f)
        if entry_count > 2047:
            if ignore_faults:
                _l("WARNING: Region table entry count over 2047, setting to 2047 - expect invalid data",
                   to_stdout=DEBUG_TO_STDOUT)
            else:
                raise VhdxHeaderError("WARNING: Region table entry count over 2047")
        reserved = read_uint32(f)  # reserved. obviously.

        _l(f"Reading {entry_count} region table entries", to_stdout=DEBUG_TO_STDOUT)

        table_entries = {}
        for i in range(entry_count):
            entry = RegionTableEntry.from_stream(f)
            if entry.guid in table_entries:
                if ignore_faults:
                    _l("WARNING: Multiple Region Table entries with the same key", to_stdout=DEBUG_TO_STDOUT)
                else:
                    raise VhdxHeaderError("Multiple Region Table entries with the same key")
            table_entries[entry.guid] = entry

        return cls(table_entries)


class MetadataTableEntry:
    def __init__(self, item_id, offset, length, is_user, is_virtual_disk, is_required):
        self._item_id = item_id
        self._offset = offset
        self._length = length

    @property
    def item_id(self):
        return self._item_id

    @property
    def offset(self):
        return self._offset

    @property
    def length(self):
        return self._length

    @classmethod
    def from_stream(cls, f: typing.BinaryIO):
        guid = read_guid(f)
        offset = read_uint32(f)
        length = read_uint32(f)
        flags = read_uint32(f)
        reserved = read_uint32(f)
        is_user = (flags & 0x01) != 0
        is_virtual_disk = (flags & 0x02) != 0
        is_required = (flags & 0x04) != 0

        return cls(guid, offset, length, is_user, is_virtual_disk, is_required)


class Metadata:
    @staticmethod
    def parse_file_parameters(data):
        with io.BytesIO(data) as f:
            yield "BlockSize", read_uint32(f)
            flags = read_uint32(f)
            yield "LeaveBlocksAllocated", (flags & 1) != 0
            yield "HasParent", (flags & 2) != 0

    @staticmethod
    def parse_virtual_disk_size(data):
        with io.BytesIO(data) as f:
            yield "VirtualDiskSize", read_uint64(f)

    @staticmethod
    def parse_page_83_data(data):
        with io.BytesIO(data) as f:
            yield "Page83Data", read_guid(f)

    @staticmethod
    def parse_logical_sector_size(data):
        with io.BytesIO(data) as f:
            yield "LogicalSectorSize", read_uint32(f)

    @staticmethod
    def parse_physical_sector_size(data):
        with io.BytesIO(data) as f:
            yield "PhysicalSectorSize", read_uint32(f)

    @staticmethod
    def parse_parent_locator(data):
        with io.BytesIO(data) as f:
            locator_type = read_guid(f)
            if locator_type != guid_to_blob(PARENT_LOCATOR_TYPE_VHDX):
                _l("WARNING: Unexpected Parent locator type", to_stdout=DEBUG_TO_STDOUT)
            reserved = read_uint16(f)
            key_value_count = read_uint16(f)
            entries = []
            for i in range(key_value_count):
                # KeyOffset, ValueOffset, KeyLength, ValueLength
                entries.append((read_uint32(f), read_uint32(f), read_uint16(f), read_uint16(f)))

            locator_fields = {}
            for key_offset, value_offset, key_length, value_length in entries:
                f.seek(key_offset)
                key = read_raw(f, key_length).decode("utf-16-le")
                f.seek(value_offset)
                value = read_raw(f, value_length).decode("utf-16-le")
                locator_fields[key] = value

            yield "ParentLocator", locator_fields

    @staticmethod
    def parse_metadata_entry(data: bytes, item_id: bytes):
        yield from {
            guid_to_blob(METADATA_FILE_PARAMETERS): Metadata.parse_file_parameters,
            guid_to_blob(METADATA_VIRTUAL_DISK_SIZE): Metadata.parse_virtual_disk_size,
            guid_to_blob(METADATA_PAGE_83_DATA): Metadata.parse_page_83_data,
            guid_to_blob(METADATA_LOGICAL_SECTOR_SIZE): Metadata.parse_logical_sector_size,
            guid_to_blob(METADATA_PHYSICAL_SECTOR_SIZE): Metadata.parse_physical_sector_size,
            guid_to_blob(METADATA_PARENT_LOCATOR): Metadata.parse_parent_locator
        }[item_id](data) 


class MetadataTable:
    def __init__(self, entries_raw, entries):
        self._entities_raw = entries_raw
        self._entries = entries

    @property
    def raw_entries(self):
        yield from self._entities_raw

    def __len__(self):
        return len(self._entries)

    def __getitem__(self, item):
        return self._entries[item]

    def __iter__(self):
        yield from self._entries.keys()

    def __contains__(self, item):
        return item in self._entries

    def get(self, key, default=None):
        return self[key] if key in self else default

    @classmethod
    def from_stream(cls, stream: typing.BinaryIO, *, ignore_faults=False):
        origin = stream.tell()
        magic = read_raw(stream, len(METADATA_TABLE_MAGIC))
        if magic != METADATA_TABLE_MAGIC:
            if ignore_faults:
                _l(f"WARNING: Invalid Metadata table magic (Expected: {METADATA_TABLE_MAGIC.hex()}; got: {magic.hex()}",
                   to_stdout=DEBUG_TO_STDOUT)
            else:
                raise VhdxMetadataError(
                    f"WARNING: Invalid Metadata table magic (Expected: {METADATA_TABLE_MAGIC.hex()}; got: {magic.hex()}")

        reserved1 = read_uint16(stream)
        entry_count = read_uint16(stream)
        reserved2 = read_raw(stream, 20)

        entries = []
        for i in range(entry_count):
            entries.append(MetadataTableEntry.from_stream(stream))

        metas = {}
        for entry in entries:
            stream.seek(origin + entry.offset)
            data = read_raw(stream, entry.length)
            for meta_item_key, meta_item_value in Metadata.parse_metadata_entry(data, entry.item_id):
                if meta_item_key in metas:
                    raise ValueError("Duplicate metadata keys")  # should not happen
                metas[meta_item_key] = meta_item_value

        return cls(entries, metas)


class BatPayloadBlockState(enum.IntEnum):
    BAT_PAYLOAD_BLOCK_NOT_PRESENT = 0  # Not contained in this vhdx
    BAT_PAYLOAD_BLOCK_UNDEFINED = 1  # Not live data - if location is set, it may contain unallocated data
    BAT_PAYLOAD_BLOCK_ZERO = 2  # Area of virtual disk is zeros
    BAT_PAYLOAD_BLOCK_UNMAPPED = 3  # Area of virtual disk had UNMAP command applied to it
    BAT_PAYLOAD_BLOCK_FULLY_PRESENT = 6  # Area fully allocated with live data
    BAT_PAYLOAD_BLOCK_PARTIALLY_PRESENT = 7  # (valid only for differencing) payload block contains *some* live data


class BatEntry:
    def __init__(self, state: BatPayloadBlockState, file_offset_mb: int):
        self._state = state
        self._file_offset = file_offset_mb * (1 << 20)

    def __repr__(self):
        return f"<BatEntry file_offset: {self._file_offset}; state: {self._state.name} ({self._state.value})>"

    @property
    def state(self):
        return self._state

    @property
    def offset(self):
        return self._file_offset

    @classmethod
    def from_stream(cls, stream: typing.BinaryIO):
        block_raw = read_uint64(stream)
        state = block_raw & 0x07
        file_offset_mb = (block_raw >> 20) & 0xfffffffffff
        return cls(BatPayloadBlockState(state), file_offset_mb)


class LogEntry:  # TODO
    def __init__(self):
        pass

    @classmethod
    def from_stream(cls, stream: typing.BinaryIO):
        pass


class FileIdentifier:
    def __init__(self, creator: bytes):
        self._creator = creator

    @classmethod
    def from_stream(cls, f: typing.BinaryIO, *, ignore_faults=False):
        _l("Reading file header section", debug_only=True, to_stdout=DEBUG_TO_STDOUT)
        magic = read_raw(f, len(VHDX_MAGIC))
        if magic != VHDX_MAGIC and not ignore_faults:
            raise VhdxHeaderError(
                f"WARNING: Invalid header section magic (Expected: {VHDX_MAGIC.hex()}; got: {magic.hex()}")
        creator = read_raw(f, CREATOR_LENGTH)
        f.seek((1024 * 64) - CREATOR_LENGTH - len(VHDX_MAGIC), os.SEEK_CUR)  # to next 64k boundary

        return cls(creator)


"""
fallback_metas must define keys for;
    LogicalSectorSize
    PhysicalSectorSize
    BlockSize
A sensible fallback metas object is provided in SENSIBLE_FALLBACK_METAS
"""
class VhdxFile:
    def __init__(self, in_path, *, ignore_faults=False, fallback_metas=None):
        self._file_path = pathlib.Path(in_path)
        # TODO: If fallback_metas present check that the required keys are there
        with self._file_path.open("rb") as f:

            file_identifier = FileIdentifier.from_stream(f, ignore_faults=ignore_faults)

            header_a = Header.from_stream(f)
            header_b = Header.from_stream(f)
            current_header = header_a if header_a.sequence_number > header_b.sequence_number else header_b
            # TODO: is the older header worth anything? And should we validate the crcs?
            _l(f"The {'first' if current_header is header_b else 'second'} header is current.",
               to_stdout=DEBUG_TO_STDOUT)

            # TODO: which one is current? should we consult the log?
            region_table_a = RegionTable.from_stream(f)
            region_table_b = RegionTable.from_stream(f)
            # for now we'll just compare...
            if len(region_table_a) != len(region_table_b):
                raise ValueError("region tables do not match")
            for key in region_table_a:
                if region_table_a[key] != region_table_b[key]:
                    raise ValueError("region tables do not match")

            # if they match just use the first
            region_table = region_table_a
            self._header = current_header
            self._region_table = region_table

            metas = None
            if guid_to_blob(REGION_GUID_METADATA) in self._region_table:
                meta_info = self._region_table[guid_to_blob(REGION_GUID_METADATA)]
                _l(f"Metadata region at offset {meta_info.offset}", to_stdout=DEBUG_TO_STDOUT)
                f.seek(meta_info.offset)
                metas = MetadataTable.from_stream(f, ignore_faults=ignore_faults)
            else:
                if ignore_faults and fallback_metas:
                    _l("WARNING: No metadata block defined, falling back to provided metadata",
                       to_stdout=DEBUG_TO_STDOUT)
                    metas = fallback_metas
                else:
                    raise VhdxHeaderError("No metadata block defined")

            # Fallback if we couldn't get the metas and didn't crash out
            self._using_fallback_metas = False
            if not metas and fallback_metas:
                _l("WARNING: Couldn't get metadata, falling back to provided metadata",
                   to_stdout=DEBUG_TO_STDOUT)
                metas = dict(fallback_metas)  # Politely take a copy
                # guess VirtualDiskSize from BAT size

                if "VirtualDiskSize" not in metas:
                    _l("WARNING: Inferring VirtualDiskSize from BAT size")
                    raw_bat_entry_count = self._region_table[guid_to_blob(REGION_GUID_BAT)].length // 8
                    chunk_ratio = ((1 << 23) * metas["LogicalSectorSize"]) // metas["BlockSize"]
                    payload_block_count = raw_bat_entry_count - (raw_bat_entry_count // chunk_ratio)
                    # The following will err on the side of being slightly too big, if the BAT is valid
                    inferred_size = payload_block_count * metas["BlockSize"]
                    if inferred_size > MAX_INFERRED_SIZE:
                        raise ValueError(f"Inferred size of VirtualDiskSize ({inferred_size}) was over" +
                                         f"{MAX_INFERRED_SIZE} (increase MAX_INFERRED_SIZE if required)")
                    metas["VirtualDiskSize"] = inferred_size
                    _l(f"VirtualDiskSize inferred size: {inferred_size}")
                self._using_fallback_metas = True

            # TODO: "user" should have to define defaults for more stuff if things fail
            # TODO: Try to infer differencing if we don't have metadata either way (sector bitmap and
            #  partially allocated payload BAT entries might help)

            self._metas = metas

            self._logical_sector_size = self._metas["LogicalSectorSize"]
            self._physical_sector_size = self._metas["PhysicalSectorSize"]
            self._block_size = self._metas["BlockSize"]

            self._chunk_ratio = ((1 << 23) * self._logical_sector_size) // self._block_size
            _l(f"Chunk Ratio = (2**23 * LogicalSectorSize) / BlockSize", debug_only=True, to_stdout=DEBUG_TO_STDOUT)
            _l(f"Chunk Ratio = (2**23 * {self._logical_sector_size}) / {self._block_size} = {self._chunk_ratio}",
               to_stdout=DEBUG_TO_STDOUT)

            self._sector_bitmap_cache = {}  # chunk number : sector bitmap page
            self._empty_block = b"\x00" * self._block_size  # this could actually be up to 256 MB
            self._empty_sector = b"\x00" * self._logical_sector_size

    def _get_bat_index_for_logical_sector(self, sector_number: int):
        if sector_number > self.metas["VirtualDiskSize"] // self.metas["LogicalSectorSize"] or sector_number < 0:
            raise ValueError("Sector number out of range")
        raw_index = (sector_number * self._logical_sector_size) // self._block_size
        # add on the number of sector-bitmap entries in the way:
        actual_index = raw_index + (raw_index // self._chunk_ratio)
        return actual_index

    def get_bat_entry_for_logical_sector(self, sector_number: int):
        with self._file_path.open("rb") as f:
            if sector_number > self.metas["VirtualDiskSize"] // self.metas["LogicalSectorSize"] or sector_number < 0:
                raise ValueError("Sector number out of range")
            bat_offset = self._region_table[guid_to_blob(REGION_GUID_BAT)].offset
            entry_offset = self._get_bat_index_for_logical_sector(sector_number) * 8
            f.seek(bat_offset + entry_offset, os.SEEK_SET)
            return BatEntry.from_stream(f)

    def get_block(self, bat_entry: BatEntry):
        if bat_entry.state == BatPayloadBlockState.BAT_PAYLOAD_BLOCK_ZERO:
            return self._empty_block
        elif bat_entry.state in (BatPayloadBlockState.BAT_PAYLOAD_BLOCK_NOT_PRESENT,
                                 BatPayloadBlockState.BAT_PAYLOAD_BLOCK_UNDEFINED,
                                 BatPayloadBlockState.BAT_PAYLOAD_BLOCK_UNMAPPED) and bat_entry.offset == 0:
            return self._empty_block
        with self._file_path.open("rb") as f:
            f.seek(bat_entry.offset, os.SEEK_SET)
            return f.read(self.metas["BlockSize"])

    def iter_bat_payload_entries(self):
        with self._file_path.open("rb") as f:
            f.seek(self._region_table[guid_to_blob(REGION_GUID_BAT)].offset)
            # the below value is based on the size of the region
            # TODO: should I use the equations for the different vhdx types?
            raw_entry_count = self._region_table[guid_to_blob(REGION_GUID_BAT)].length // 8
            for i in range(raw_entry_count):
                if i > 0 and i % (self._chunk_ratio + 1) == 0:
                    BatEntry.from_stream(f)  # skip sector bitmap
                yield BatEntry.from_stream(f)

    def is_sector_allocated(self, sector_number):
        if sector_number > self.metas["VirtualDiskSize"] // self.metas["LogicalSectorSize"] or sector_number < 0:
            raise ValueError("Sector number out of range")

        if not self.is_differencing:
            return True

        bat_index = (sector_number * self._logical_sector_size) // self._block_size
        chunk_index = bat_index // self._chunk_ratio
        bat_index_for_sector_bitmap = chunk_index + ((1 + chunk_index) * self._chunk_ratio)

        if chunk_index in self._sector_bitmap_cache:
            sector_bitmap = self._sector_bitmap_cache[chunk_index]
        else:
            with self._file_path.open("rb") as f:
                f.seek(self._region_table[guid_to_blob(REGION_GUID_BAT)].offset + (bat_index_for_sector_bitmap * 8))
                sector_bitmap_bat_entry = BatEntry.from_stream(f)

            if sector_bitmap_bat_entry.state == BAT_SB_BLOCK_NOT_PRESENT:
                self._sector_bitmap_cache[chunk_index] = None
                sector_bitmap = None
            elif sector_bitmap_bat_entry.state == BAT_SB_BLOCK_PRESENT:
                with self._file_path.open("rb") as f:
                    f.seek(sector_bitmap_bat_entry.offset,  os.SEEK_SET)
                    sector_bitmap = f.read(1 << 23)  # always a microsoft megabyte
                self._sector_bitmap_cache[chunk_index] = sector_bitmap
            else:
                raise ValueError(f"Invalid Sector Bitmap BAT entry state {sector_bitmap_bat_entry.state}")

        if sector_bitmap is None:
            return False
        else:
            sectors_per_bitmap = 1 << 23
            index_in_sb = sector_number % sectors_per_bitmap
            byte_offset = index_in_sb // 8
            bit_offset = index_in_sb % 8

            return (sector_bitmap[byte_offset] >> bit_offset) & 1 != 0

    def get_sector(self, sector_number: int):
        if sector_number > self.metas["VirtualDiskSize"] // self.metas["LogicalSectorSize"] or sector_number < 0:
            raise ValueError("Sector number out of range")
        bat_entry = self.get_bat_entry_for_logical_sector(sector_number)
        if self.is_sector_allocated(sector_number):
            block = self.get_block(bat_entry)
            sectors_per_block = self.block_size // self.logical_sector_size
            sector_index_in_block = sector_number % sectors_per_block
            sector_data = block[sector_index_in_block * self.metas["LogicalSectorSize"]:
                                (1 + sector_index_in_block) * self.metas["LogicalSectorSize"]:]
            if len(sector_data) != self.metas["LogicalSectorSize"]:
                raise ValueError("Couldn't get full sector from block")  # should never happen. hence exception.

            return sector_data
        else:
            return self._empty_sector

    def get_meta_entry(self, key):
        return self._metas[key]

    @property
    def header(self):
        return self._header

    @property
    def region_table(self):
        return self._region_table

    @property
    def metas(self):
        return self._metas

    @property
    def logical_sector_size(self):
        return self._logical_sector_size

    @property
    def physical_sector_size(self):
        return self._physical_sector_size

    @property
    def block_size(self):
        return self._block_size

    @property
    def used_fallback_metas(self):
        return self._using_fallback_metas

    @property
    def is_differencing(self):
        return self.metas["HasParent"]

    @property
    def virtual_disk_size(self):
        return self.metas["VirtualDiskSize"]


def main(args):
    pass


if __name__ == '__main__':
    import sys
    DEBUG_TO_STDOUT = True
    main(sys.argv[1:])
