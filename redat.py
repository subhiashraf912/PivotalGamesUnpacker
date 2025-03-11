import os
import struct
import importlib
import subprocess
import sys







directory = "mission01"








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

def load_filenames_list(list_path: str):

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

    all_files = []
    for root, dirs, files in os.walk(directory):
        for fname in files:
            fullpath = os.path.join(root, fname)
            relpath = os.path.relpath(fullpath, start=directory)
            all_files.append((relpath, fullpath))
    return all_files

def main():



    dat_filename = f"modified/{directory}.dat"
    filenames_list = load_filenames_list("data/FileNames.List")
    mapped_files = {v: k for k, v in filenames_list.items()}

    print(f"{Fore.GREEN}Repacking folder: {directory} => {dat_filename}{Fore.RESET}")

    files = gather_files(directory)
    num_files = len(files)

    table_size = (num_files + 1) * 12
    current_offset = table_size

    entries = []
    for relpath, fullpath in files:
        fsize = os.path.getsize(fullpath)
        if relpath in mapped_files:
            dwHash = ce_hash(relpath.lower())
        else:
            dwHash = int(relpath.split(".")[0])
            # print(dwHash)
        # print(relpath)

        entries.append((dwHash, current_offset, fsize, fullpath))
        current_offset += fsize

    with open(dat_filename, "wb") as out_f:
        for (dwHash, off, sz, fp) in entries:
            # try:
            out_f.write(struct.pack('<III', dwHash, off, sz))
            # except:
                # print("ERRORED")
        # final zero record:
        out_f.write(struct.pack('<III', 0, 0, 0))

        for (dwHash, off, sz, fp) in entries:
            with open(fp, "rb") as in_f:
                out_f.write(in_f.read())

    print(f"{Fore.GREEN}Number of files packed: {num_files}{Fore.RESET}")
    print(f"{Fore.GREEN}Created DAT file: {dat_filename}{Fore.RESET}")

if __name__ == "__main__":
    main()
