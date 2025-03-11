#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import struct
import re

###############################################################################
#  Hash Function (equivalent to DatHash.iGetHash in the C# code)
###############################################################################
def ce_hash(input_string: str) -> int:
    """
    Python translation of DatHash.iGetHash from the C# code.
    """
    dwHash = 1  # starts as 1 in the C# code
    j = 0
    bCounter = 1
    dwBlocks = 8 * len(input_string)

    encoded = input_string.encode('ascii', errors='ignore')

    for i in range(dwBlocks):
        D = (dwHash & 0x80000000) != 0   # sign bit
        A = (dwHash & 0x200000) != 0
        B = (dwHash & 2) != 0
        C = (dwHash & 1) != 0

        dwHash = (dwHash << 1) & 0xFFFFFFFF

        current_char = encoded[j] if j < len(encoded) else 0
        X = ((current_char & bCounter) != 0)

        if D ^ (A ^ B ^ C ^ X):
            dwHash |= 1

        bCounter <<= 1
        if bCounter == 0 or bCounter > 0x80:
            j += 1
            bCounter = 1

    return dwHash & 0xFFFFFFFF

###############################################################################
#  Load "FileNames.list"  =>  { hash_value : "Some/Path/File.ext" }
###############################################################################
def load_hash_list(project_file_path: str):
    """
    Mirroring the C# DatHashList logic:
       - For each line in FileNames.list, compute lower-hash and upper-hash,
         store both => that same filename
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

    print(f"[INFO]: Project File Loaded: {count} filenames")
    return hash_dict

###############################################################################
#  Guess extension from file contents (like your old undat script)
###############################################################################
def guess_extension(data: bytes):
    """
    Use the same logic from your old "undat" code to guess an extension.
    We'll check the first 4 bytes, or do a naive ASCII check.
    """
    if len(data) < 4:
        # too short, just call it '.bin'
        return 'bin'

    first4 = data[:4]

    # Mimic your old approach
    if first4 == b'DDS ':
        return 'dds'
    elif first4 == b'PSF ':
        return 'psf'
    elif first4 == b'SCH ':
        return 'sch'
    elif first4 == b'EOBJ':
        return 'eobj'
    elif first4[1:4] == b'PNG':
        return 'png'
    elif first4 == b'imgf':
        return 'imgf'
    elif first4 == b'SLOC':
        return 'sloc'
    elif first4[:2] == b'BM':  # maybe a .bmp
        return 'bmp'
    elif first4.hex() == '02000000':
        return 'bin'
    # check if it might be text
    # e.g. old code: (ext[0:1].hex() > "47" and ext[0:1].hex() < "58") or ext == b"Vers"...
    # We'll do a simpler approach:
    try:
        # if the data is mostly ASCII-likely, guess txt
        data[:256].decode('ascii')
        # if decode works with no UnicodeError, let's call it txt
        return 'txt'
    except UnicodeDecodeError:
        return 'bin'

###############################################################################
#  Unpacking DAT archives
###############################################################################
def unpack_dat(dat_path: str, out_folder: str, project_file: str):
    """
    1) Load the hash dictionary (hash->filename) from project_file
    2) Read (hash, offset, size) in a loop until we see hash=0 or end of file
    3) For each entry:
        - If hash is in dictionary => use that name
        - Else => use  __Unknown/XXXXXXX
        - Then read the data, guess extension if no known extension
        - Create subfolders as needed and write data
    """
    if not os.path.isfile(dat_path):
        print(f"[ERROR]: DAT file not found => {dat_path}")
        return

    # ensure out_folder ends with slash
    if not out_folder.endswith(os.path.sep):
        out_folder += os.path.sep

    os.makedirs(out_folder, exist_ok=True)

    # load the known hash->filename map
    hash_dict = load_hash_list(project_file) if project_file else {}
    if not hash_dict:
        print("[WARNING]: Hash dictionary is empty or not loaded; unknown files go to __Unknown/")

    # read all entries from the front
    entries = []
    with open(dat_path, 'rb') as f:
        while True:
            chunk = f.read(12)
            if len(chunk) < 12:
                break
            dwHash, dwOffset, dwSize = struct.unpack('<III', chunk)
            if dwHash == 0:
                break
            entries.append((dwHash, dwOffset, dwSize))

    # extract each entry
    for (dwHash, dwOffset, dwSize) in entries:
        # see if that hash is known
        if dwHash in hash_dict:
            # e.g. "someFolder/texture.dds"
            candidate_name = hash_dict[dwHash]
        else:
            # fallback => __Unknown/DEADBEEF
            # no extension in the dictionary, so we will guess from data
            candidate_name = f"__Unknown/{dwHash:08X}"

        # read the data
        with open(dat_path, 'rb') as f:
            f.seek(dwOffset)
            data = f.read(dwSize)

        # If the dictionary doesn't have an obvious extension, or the user wants
        # to confirm the extension, we can guess from the data. 
        # We'll do it if the mapped name does NOT contain a period. 
        # (If "someFolder/texture.dds" is in the dictionary, we trust that extension.)
        # If you prefer always to guess, you can tweak this logic.
        _, ext_in_name = os.path.splitext(candidate_name)
        if not ext_in_name:
            # guess extension
            guessed_ext = guess_extension(data)
            candidate_name += f".{guessed_ext}"

        # build full path
        fullpath = os.path.join(out_folder, candidate_name)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)

        print(f"[UNPACKING] 0x{dwHash:08X} => {candidate_name}")

        # write it
        with open(fullpath, 'wb') as out_f:
            out_f.write(data)

###############################################################################
#  Repacking DAT archives
###############################################################################
def repack_dat(src_folder: str, dat_out: str, project_file: str):
    """
    Reverse operation:
      1) We walk src_folder, collecting all files.
      2) For each file, we compute the same hash that the engine expects.
         Typically that means we take the RELATIVE PATH under src_folder,
         change to lower() or upper(), then pass to ce_hash.
      3) We store (hash, size, file_path). We'll fill offset in a second pass.
      4) We build a table of (hash, offset, size) + final (0,0,0)
      5) Then write the file data.
    """
    src_folder = os.path.normpath(src_folder)

    # If you want to do EXACT name->hash from your FileNames.list, then we could:
    #   (A) invert the dictionary from load_hash_list:  name.lower()->hash
    #   (B) for each file, find its relative path, see if it's in that dict
    #   (C) if not found, fallback to hashing the relative path with ce_hash.
    #
    # Here, we keep it simpler: we just do ce_hash(relative_path.lower()).

    # load dictionary for convenience, but we might not strictly need it
    # if your repacking strategy just uses the relative path => hash approach.
    if project_file and os.path.isfile(project_file):
        hash_dict = load_hash_list(project_file)
        # But remember, that is hash->name. For repacking we might want name->hash,
        # which means inverting it. We'll do that below if desired:
        #   name_to_hash = { v.lower(): k for (k,v) in hash_dict.items() }
        # Then you'd check if relative_path.lower() in name_to_hash ...
        # For now, let's do the simpler approach.

    entries = []

    # gather every file from src_folder
    for root, dirs, files in os.walk(src_folder):
        for fname in files:
            fullpath = os.path.join(root, fname)
            # REL path
            relpath = os.path.relpath(fullpath, start=src_folder).replace('\\','/')
            # compute hash by lowercasing the relpath
            file_hash = ce_hash(relpath.lower())
            fsize = os.path.getsize(fullpath)
            entries.append((file_hash, relpath, fsize, fullpath))

    # The table: (hash, offset, size) repeated, + final (0,0,0).
    # We'll do a 2-pass approach:
    n = len(entries)
    table_size = (n + 1) * 12  # each record is 12 bytes, plus the final zero
    current_offset = table_size

    packed_entries = []
    for (hsh, rp, sz, fp) in entries:
        packed_entries.append((hsh, current_offset, sz, rp, fp))
        current_offset += sz

    with open(dat_out, 'wb') as out_f:
        # pass 1: write the table
        for (hsh, off, sz, rp, fp) in packed_entries:
            out_f.write(struct.pack('<III', hsh, off, sz))

        # final zero entry
        out_f.write(struct.pack('<III', 0, 0, 0))

        # pass 2: write the file data
        for (hsh, off, sz, rp, fp) in packed_entries:
            with open(fp, 'rb') as in_f:
                out_f.write(in_f.read())

    print(f"[INFO] Wrote {n} files into new DAT => {dat_out}")

###############################################################################
#  Command-line entry point
###############################################################################
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage:")
        print("   python ce_dat_tool.py unpack  <input.dat>  <out_folder>  [FileNames.list]")
        print("   python ce_dat_tool.py repack  <in_folder>  <output.dat>  [FileNames.list]")
        sys.exit(0)

    mode = sys.argv[1].lower()
    if mode == "unpack":
        dat_in = sys.argv[2]
        out_folder = sys.argv[3]
        project_file = sys.argv[4] if len(sys.argv) > 4 else "data/FileNames.list"
        unpack_dat(dat_in, out_folder, project_file)

    elif mode == "repack":
        folder_in = sys.argv[2]
        dat_out = sys.argv[3]
        project_file = sys.argv[4] if len(sys.argv) > 4 else ""
        repack_dat(folder_in, dat_out, project_file)

    else:
        print(f"Unknown command: {mode}")
        sys.exit(1)
