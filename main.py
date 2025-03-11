#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import struct

###############################################################################
#  Hash Function (equivalent to DatHash.iGetHash in the C# code)
###############################################################################
def ce_hash(input_string: str) -> int:
    """
    Python translation of:
        public static UInt32 iGetHash(String m_String)
        in the C# DatHash.cs code.

    The C# code uses a 32-bit signed int for dwHash, checks sign bits, etc.
    We'll reproduce that behavior as closely as possible.

    The hashing is done over the *ASCII bytes* of input_string.
    """
    # In C#, dwHash starts as signed Int32=1. We'll store in Python as int,
    # but we must interpret the sign bit the same way the C# code does.
    dwHash = 1
    j = 0
    bCounter = 1
    # number of bits to process = 8 * length (i.e. each char => 8 bits)
    dwBlocks = 8 * len(input_string)

    # We'll treat each character as a single byte, so let's get the ASCII bytes
    # C# does: Boolean X = Convert.ToBoolean(m_String[j] & bCounter).
    # That suggests each char is 1 byte.
    encoded = input_string.encode('ascii', errors='ignore')  # or 'replace'

    for i in range(dwBlocks):
        # In C#: D = (dwHash < 0). We'll replicate by checking the sign bit
        # for a 32-bit integer. If the top bit (0x80000000) is set, it's negative.
        D = (dwHash & 0x80000000) != 0

        # A = (dwHash & 0x200000) != 0
        A = (dwHash & 0x200000) != 0
        # B = (dwHash & 2) != 0
        B = (dwHash & 0x2) != 0
        # C = (dwHash & 1) != 0
        C = (dwHash & 0x1) != 0

        # shift dwHash left by 1 (keeping track in 32-bit space)
        dwHash = (dwHash << 1) & 0xFFFFFFFF

        # X => test a single bit in the next character
        # encoded[j] & bCounter. bCounter = 1,2,4,8,16,32,64,128, then reset
        # once we've done 8 bits of that particular character
        current_char = 0
        if j < len(encoded):
            current_char = encoded[j]
        X = (current_char & bCounter) != 0

        # if (D ^ (A ^ B ^ C ^ X)) then dwHash |= 1
        if D ^ (A ^ B ^ C ^ X):
            dwHash |= 1

        bCounter = bCounter << 1
        if bCounter == 0 or bCounter > 0x80:
            # we've processed 8 bits from encoded[j]; move to next char
            j += 1
            bCounter = 1

    # Return this as an unsigned 32-bit integer
    return dwHash & 0xFFFFFFFF

###############################################################################
#  Loading a "filenames list" (like FileNames.list in the C# code)
###############################################################################
def load_hash_list(project_file_path: str):
    """
    This mirrors the logic in DatHashList.cs, building a dictionary of:
        { hash_value : "filename" }

    The original code also adds uppercase/lowercase collisions, etc. We'll do the
    same here for completeness. If you want to skip that or handle collisions
    differently, you can.
    """
    hash_dict = {}
    count = 0

    if not os.path.isfile(project_file_path):
        print(f"[ERROR]: Project file not found: {project_file_path}")
        return hash_dict

    with open(project_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            lower_hash = ce_hash(line.lower())
            upper_hash = ce_hash(line.upper())

            if lower_hash in hash_dict:
                print(f"[COLLISION]: line {count} => {hash_dict[lower_hash]} <-> {line}")
            hash_dict[lower_hash] = line

            if upper_hash in hash_dict:
                print(f"[COLLISION]: line {count} => {hash_dict[upper_hash]} <-> {line}")
            hash_dict[upper_hash] = line

            count += 1

    print(f"[INFO]: Project File Loaded: {count} entries")
    return hash_dict

###############################################################################
#  Unpacking DAT archives
###############################################################################
def unpack_dat(dat_path: str, out_folder: str, project_file: str):
    """
    Translates DatUnpack.iDoIt(...) from the C# code.
    1) Loads the hash dictionary from project_file
    2) Reads (hash, offset, size) in a loop until hash=0
    3) For each entry, tries to find a matching name from the dictionary
       or puts it in __Unknown\hash
    4) Reads the data chunk from offset, size
    5) Writes the extracted file
    """
    # Make sure out_folder ends with a slash
    if not out_folder.endswith(os.path.sep):
        out_folder += os.path.sep

    if not os.path.isfile(dat_path):
        print(f"[ERROR]: DAT file does not exist => {dat_path}")
        return

    # 1) load the project (hash->name)
    hash_dict = load_hash_list(project_file)
    if not hash_dict:
        print("[WARNING]: Hash dictionary empty or load failed. Unpacked files may go to __Unknown.")
    entries = []

    # 2) Read the table from the front of the .dat
    with open(dat_path, 'rb') as f:
        while True:
            chunk = f.read(12)  # 4 bytes hash + 4 bytes offset + 4 bytes size
            if len(chunk) < 12:
                # End of file (or something unexpected)
                break

            dwHash, dwOffset, dwSize = struct.unpack('<III', chunk)  # < => little-endian
            if dwHash == 0:
                # This matches the C# code's "if (dwHash == 0) break;"
                break

            entries.append((dwHash, dwOffset, dwSize))

    # 3) For each entry, get name from dictionary or unknown
    for (dwHash, dwOffset, dwSize) in entries:
        if dwHash in hash_dict:
            filename = hash_dict[dwHash]
        else:
            filename = f"__Unknown/{dwHash:08X}"

        # create full path
        fullpath = os.path.join(out_folder, filename)
        # ensure subfolders exist
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)

        print(f"[UNPACKING]: {filename}")
        # 4) read from offset, size
        with open(dat_path, 'rb') as f:
            f.seek(dwOffset)
            data = f.read(dwSize)

        # 5) write data out
        with open(fullpath, 'wb') as out_f:
            out_f.write(data)

###############################################################################
#  Repacking DAT archives
###############################################################################
def repack_dat(src_folder: str, dat_out: str, project_file: str):
    """
    A “reverse” operation that the original C# code did not show.
    We'll:
      1) Walk src_folder (including subdirectories).
      2) For each file, compute the hash based on either:
         - Its relative path (lower vs upper? up to you how to match).
           Typically you'd do the same logic that was used when making
           the original 'FileNames.list' so that the hash can match
           the original.
      3) Collect (hash, size, file_path). We'll fill in offset later.
      4) We first write out all the table entries to the .dat, but we
         can't finalize the offsets until we know how big the table is
         (because data follows).
      5) Actually, an easier approach is:
         - Collect all file data in memory or a staging, so we know all sizes.
         - Or do a “two-pass” approach: 
               pass1 => figure out how big the table is => compute data offsets
               pass2 => actually write the table, then write the data, then a (0,0,0).
    """
    # Make sure src_folder does not end with slash, so we can form relative paths
    src_folder = os.path.normpath(src_folder)

    # 1) load the project (hash->name). But for repacking, we might want
    #    to invert that dictionary => name->hash. We have to do the same
    #    hashing logic as the original code.
    #    (In the original C# code, iGetNameFromHashList goes from hash => name.
    #     For repacking, we want exactly the same hash that the game expects
    #     for each filename.)
    #    *If* we want to replicate EXACT naming => hash from “FileNames.list”,
    #    we could do a dictionary { some_lowercase_path : some_hash }. But actually
    #    we do the same function ce_hash(filename.lower()) to match the original.
    #    We can either do that or rely on the dictionary from load_hash_list. Then
    #    for each actual file, see if it’s in that dictionary by a reversed lookup.
    #
    #    For simplicity, let's just compute the hash from the file’s relative path
    #    the same way the original “FileNames.list” presumably would. If you do that
    #    consistently, it should match the original hash.
    #
    #    Example: If the original “FileNames.list” had lines like: 
    #         "SOME_DIR/texture.dds"
    #    Then you want to replicate the same relative path from your src_folder.
    #    That is, the part after src_folder is "SOME_DIR/texture.dds" => we do
    #    ce_hash(...).
    #
    #    That said, there's no single “correct” approach, but let's do:
    #        relative_path = <path under src_folder>.replace('\\','/').lower()
    #
    #    Then do:
    #        file_hash = ce_hash(relative_path)
    #
    #    That should produce the same hash if the original code used lower-case path
    #    for hashing. Or do ce_hash(relative_path.upper()) if you suspect it used upper.
    #
    #    If you have a “FileNames.list”, you can read it in, but that typically
    #    helps with *unpacking*. For repacking, you just want the same exact function
    #    used on the correct file path strings.
    #
    #    If your usage differs, tweak accordingly.

    entries = []
    # A small function to collect all files in subdirectories
    for root, dirs, files in os.walk(src_folder):
        for f in files:
            fullpath = os.path.join(root, f)
            # get relative path (from src_folder), forward slashes
            relpath = os.path.relpath(fullpath, start=src_folder)
            relpath = relpath.replace('\\','/')  # unify to forward slash
            # choose how to hash (lower or upper). Suppose the original used .lower()
            file_hash = ce_hash(relpath.lower())

            fsize = os.path.getsize(fullpath)
            entries.append( (file_hash, relpath, fsize, fullpath) )

    # We'll do a 2-pass approach:
    #
    # The table is a series of (hash [4 bytes], offset [4 bytes], size [4 bytes]),
    # plus a final record with hash=0. So we have len(entries)+1 table entries,
    # each 12 bytes. So total_table_size = (len(entries) + 1) * 12
    #
    # Data starts at offset = total_table_size
    n = len(entries)
    total_table_size = (n + 1) * 12
    current_offset = total_table_size  # first data offset

    # For convenience, let's build a small structure that also stores offset
    packed_entries = []
    for (hsh, rp, sz, fp) in entries:
        packed_entries.append( (hsh, current_offset, sz, rp, fp) )
        current_offset += sz

    # Now we can write out the new .dat
    with open(dat_out, 'wb') as out_f:
        # 5a) Write the table
        for (hsh, off, sz, rp, fp) in packed_entries:
            out_f.write(struct.pack('<III', hsh, off, sz))

        # final zero
        out_f.write(struct.pack('<III', 0, 0, 0))

        # 5b) Write each file’s data
        for (hsh, off, sz, rp, fp) in packed_entries:
            with open(fp, 'rb') as in_f:
                # we just copy
                data = in_f.read()
                out_f.write(data)

    print(f"[INFO] Repacked {n} files into: {dat_out}")

###############################################################################
#  Example CLI usage
###############################################################################
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage:")
        print("   python ce_dat_tool.py <command> <dat_or_folder> <output_folder_or_file> [project_file]")
        print("")
        print("Commands:")
        print("   unpack:  python ce_dat_tool.py unpack  input.dat  out_folder  FileNames.list")
        print("   repack:  python ce_dat_tool.py repack  in_folder  output.dat  FileNames.list")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "unpack":
        dat_in = sys.argv[2]
        out_folder = sys.argv[3]
        project_file = sys.argv[4] if len(sys.argv) > 4 else "data/FileNames.list"

        unpack_dat(dat_in, out_folder, project_file)

    elif command == "repack":
        folder_in = sys.argv[2]
        dat_out = sys.argv[3]
        project_file = sys.argv[4] if len(sys.argv) > 4 else "data/FileNames.list"

        repack_dat(folder_in, dat_out, project_file)

    else:
        print(f"Unknown command: {command}")
