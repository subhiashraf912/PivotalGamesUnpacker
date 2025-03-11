import os
import struct
import re
import json
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
    {"import_name": "colorama", "install_name": "colorama"}
]
for required_lib in required_libraries:
    ensure_installed(required_lib["import_name"], required_lib["install_name"])

from colorama import Fore, init
init()

###############################################################################
#  Hash function: duplicates the C# "DatHash.iGetHash"
###############################################################################
def ce_hash(input_string: str) -> int:
    dwHash = 1
    j = 0
    bCounter = 1
    dwBlocks = 8 * len(input_string)
    encoded = input_string.encode('ascii', errors='ignore')
    for i in range(dwBlocks):
        D = (dwHash & 0x80000000) != 0
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
#  Load FileNames.list => { 123456789: "Some/Name.ext", ... } (integer keys)
###############################################################################
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


###############################################################################
def guess_extension(data: bytes) -> str:
    if len(data) < 4:
        return "bin"
    first4 = data[:4]
    if first4 == b"DDS ":
        return "dds"
    elif first4 == b"PSF ":
        return "psf"
    elif first4 == b"SCH ":
        return "sch"
    elif first4 == b"EOBJ":
        return "eobj"
    elif first4[1:4] == b"PNG":
        return "png"
    elif first4.hex() == "02000000":
        return "bin"
    elif first4 == b"imgf":
        return "imgf"
    elif first4 == b"SLOC":
        return "sloc"
    elif first4[:2] == b"BM":
        return "bmp"
    else:
        try:
            data[:256].decode("ascii")
            return "txt"
        except UnicodeDecodeError:
            return "bin"

###############################################################################
#  Main "undat" logic
###############################################################################
def main():

    dat_file = "mission01.dat"
    project_file = "data/FileNames.list"

    # Load dictionary (hash -> filename) with integer keys
    name_map = {}
    if project_file and os.path.isfile(project_file):
        name_map = load_filenames_list(project_file)

    # with open('f.json', 'w', encoding='utf-8') as file:
    #     file.write(json.dumps(name_map, indent=4))
    #     file.close()

    print(f"{Fore.GREEN}Processing DAT: {dat_file}{Fore.RESET}")

    parent_dir = os.path.splitext(dat_file)[0]
    os.makedirs(parent_dir, exist_ok=True)

    processed_files = {}
    with open(dat_file, "rb") as f:
        loop = 0
        while True:
            f.seek(loop)
            hash_data = f.read(4)
            if len(hash_data) < 4:
                # out of data
                break

            dwHash = struct.unpack("<I", hash_data)[0]
            if dwHash == 0:
                # "if (dwHash == 0) break;"
                break

            # skip duplicates
            if dwHash in processed_files:
                loop += 12
                continue
            processed_files[dwHash] = True

            offset = struct.unpack("<I", f.read(4))[0]
            size   = struct.unpack("<I", f.read(4))[0]

            f.seek(offset)
            data = f.read(size)

            # Check if dwHash is in name_map (integer keys)
            if dwHash in name_map:
                # known filename from FileNames.list
                mapped_name = name_map[dwHash]
                # remove weird characters
                filename = re.sub(r'[<>:"/\\|?*]', "", mapped_name)
                filename = f"{filename.split('.')[0]}.{dwHash}.{filename.split('.')[1]}"
                # save_path = os.path.join(parent_dir, filename)
                save_path = f"{parent_dir}\\{mapped_name}"
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                print(f"{Fore.YELLOW}Extracting known: {mapped_name}{Fore.RESET}")
            else:
                # unknown => guess extension
                ext_guess = guess_extension(data)
                # sub_dir = os.path.join(parent_dir, ext_guess)
                # os.makedirs(sub_dir, exist_ok=True)
                # fallback name => e.g. "A955C55F.dds" style
                # convert dwHash to hex
                # hash_str = f"{dwHash:08X}"
                filename = f"{dwHash}.{ext_guess}"
                # save_path = os.path.join(sub_dir, filename)
                save_path = f"{parent_dir}\\{filename}"
                print(f"{Fore.YELLOW}Extracting unknown: {filename}{Fore.RESET}")
            with open(save_path, "wb") as out_f:
                out_f.write(data)

            loop += 12

    print(f"{Fore.GREEN}Finished processing: {dat_file}{Fore.RESET}")

if __name__ == "__main__":
    main()
