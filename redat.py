import os
import struct
import importlib
import subprocess
import sys

def ensure_installed(package_name: str, install_name: str | None = None) -> None:
    if not install_name:
        install_name = package_name

    try:
        importlib.import_module(package_name)
    except ImportError:
        print(f"Installing '{package_name}' ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", install_name])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Could not install package '{install_name}'. "
                "Check permissions or internet connection."
            ) from e

required_libraries = [
    {
        "import_name": "colorama",
        "install_name": "colorama"
    }
]

for required_lib in required_libraries:
    ensure_installed(required_lib["import_name"], required_lib["install_name"])

from colorama import Fore, init
init()

###############################################################################
#  Hash function: same as your "undat.py" integer-based approach
###############################################################################
def ce_hash(input_string: str) -> int:
    dwHash = 1
    j = 0
    bCounter = 1
    dwBlocks = 8 * len(input_string)
    encoded = input_string.encode('ascii', errors='ignore')

    for i in range(dwBlocks):
        # Replicate "dwHash < 0" by testing top bit
        D = (dwHash & 0x80000000) != 0
        A = (dwHash & 0x200000) != 0
        B = (dwHash & 2) != 0
        C = (dwHash & 1) != 0

        # shift left
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

def load_filenames_list(list_path: str):
    """
    Mirroring the C# DatHashList logic:
       - For each line in FileNames.list, compute lower-hash and upper-hash,
         store both => that same filename
    """
    hash_dict = {}
    count = 0

    if not os.path.isfile(list_path):
        print(f"[ERROR]: Project file not found: {list_path}")
        return hash_dict

    with open(list_path, 'r', encoding='utf-8', errors='ignore') as f:
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


def gather_files(directory):
    """
    Recursively gather all files under 'directory',
    returning a list of (relative_path, fullpath).
    """
    all_files = []
    for root, dirs, files in os.walk(directory):
        for fname in files:
            fullpath = os.path.join(root, fname)
            # relative path from 'directory'
            relpath = os.path.relpath(fullpath, start=directory)
            all_files.append((relpath, fullpath))
    return all_files

def main():


    directory = "mission01"

    dat_filename = f"{directory}-modified.dat"
    filenames_list = load_filenames_list("data/FileNames.List")
    mapped_files = {v: k for k, v in filenames_list.items()}

    # print(filenames_list)
    print(f"{Fore.GREEN}Repacking folder: {directory} => {dat_filename}{Fore.RESET}")

    files = gather_files(directory)  # list of (relpath, fullpath)
    num_files = len(files)

    # We do a "two-pass" style approach:
    # 1) Table: (hash [4 bytes], offset [4 bytes], size [4 bytes]) for each file
    # 2) A final record of (0,0,0) to match Pivotal DAT style
    # 3) Then write the actual file data

    # We know how big the table is: (num_files + 1) * 12
    table_size = (num_files + 1) * 12
    current_offset = table_size

    # Build a list of entries: (dwHash, offset, size, fullpath)
    entries = []
    for relpath, fullpath in files:
        fsize = os.path.getsize(fullpath)
        # Typical logic: hash the relative path .lower()
        # so that it matches how "unpack" might have done it
        if relpath in mapped_files:
            dwHash = ce_hash(relpath.lower())
        else:
            dwHash = int(relpath.split(".")[0])
            # print(dwHash)
        # print(relpath)

        entries.append((dwHash, current_offset, fsize, fullpath))
        current_offset += fsize

    with open(dat_filename, "wb") as out_f:
        # Pass 1: write table
        for (dwHash, off, sz, fp) in entries:
            # each field is 4 bytes, little-endian
            # try:
            out_f.write(struct.pack('<III', dwHash, off, sz))
            # except:
                # print("ERRORED")
        # final zero record:
        out_f.write(struct.pack('<III', 0, 0, 0))

        # Pass 2: write file data
        for (dwHash, off, sz, fp) in entries:
            with open(fp, "rb") as in_f:
                out_f.write(in_f.read())

    print(f"{Fore.GREEN}Number of files packed: {num_files}{Fore.RESET}")
    print(f"{Fore.GREEN}Created DAT file: {dat_filename}{Fore.RESET}")

if __name__ == "__main__":
    main()
