import os
import struct
import re
import importlib
import subprocess
import sys




dat_file = "mission01.dat"











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
#  DEC <-> HEX CONVERSION (if desired)
###############################################################################
def hash_dec_to_hex(dwHash: int) -> str:
    """Convert an integer hash to uppercase 8-hex-digit string, e.g. 0x1A2B3C4D => '1A2B3C4D'."""
    return f"{dwHash:08X}"

###############################################################################
#  Hash function (integer-based)
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
#  Load FileNames.list => { integer_hash : "Some/Name.ext" }
###############################################################################
def load_filenames_list(list_path: str):
    if not os.path.isfile(list_path):
        print(f"[ERROR]: Project file not found: {list_path}")
        return {}

    hash_dict = {}
    count = 0
    with open(list_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lower_hash = ce_hash(line.lower())
            upper_hash = ce_hash(line.upper())
            if lower_hash not in hash_dict:
                hash_dict[lower_hash] = line
            if upper_hash not in hash_dict:
                hash_dict[upper_hash] = line
            count += 1

    print(f"{Fore.GREEN}[INFO] Loaded {count} filenames from: {list_path}{Fore.RESET}")
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
        # might be ASCII -> guess txt
        try:
            data[:256].decode("ascii")
            return "txt"
        except UnicodeDecodeError:
            return "bin"

def extract_eobj_internal_name(data: bytes) -> str:

    offset = 8
    if len(data) <= offset:
        return ""
    out_bytes = []
    i = offset
    while i < len(data):
        b = data[i]
        if b == 0:
            break  # null terminator
        if b < 32 or b > 126:
            break
        out_bytes.append(b)
        i += 1

    return bytes(out_bytes).decode('ascii', errors='ignore').strip()

###############################################################################
def main():
    project_file = "data/FileNames.list"

    name_map = {}
    if os.path.isfile(project_file):
        name_map = load_filenames_list(project_file)
    else:
        print("[WARNING] No existing FileNames.list found, starting empty.")
    
    print(f"{Fore.CYAN}Processing DAT: {dat_file}{Fore.RESET}")
    parent_dir = os.path.splitext(dat_file)[0]
    os.makedirs(parent_dir, exist_ok=True)

    processed_files = {}
    with open(dat_file, "rb") as f:
        loop = 0
        while True:
            f.seek(loop)
            chunk = f.read(12)
            if len(chunk) < 12:
                break
            dwHash, dwOffset, dwSize = struct.unpack("<III", chunk)
            if dwHash == 0:
                break

            if dwHash in processed_files:
                loop += 12
                continue
            processed_files[dwHash] = True

            f.seek(dwOffset)
            data = f.read(dwSize)

            # Known name?
            if dwHash in name_map:
                mapped_name = name_map[dwHash]
                safe_name = re.sub(r'[<>:"/\\|?*]', "", mapped_name)
                save_path = os.path.join(parent_dir, safe_name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                print(f"{Fore.YELLOW}Extracting known: {mapped_name}{Fore.RESET}")
            else:
                # Unknown => guess extension
                ext_guess = guess_extension(data)
                if ext_guess == "eobj":
                    # try read internal name
                    possible_name = extract_eobj_internal_name(data)
                    if possible_name:
                        
                        name_map[dwHash] = possible_name
                        
                        with open(project_file, "a", encoding="utf-8") as list_fp:
                            list_fp.write(f"{possible_name}.EVO" + "\n")
                            list_fp.write(f"{possible_name}.DDS" + "\n")

                        safe_name = re.sub(r'[<>:"/\\|?*]', "", possible_name)
                        save_path = os.path.join(parent_dir, f"{safe_name}.EVO")
                        print(f"{Fore.YELLOW}Extracting EOBJ with internal name: {possible_name}{Fore.RESET}")
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    else:
                        # fallback
                        # hex_str = hash_dec_to_hex(dwHash)
                        safe_name = f"{dwHash}.eobj"
                        save_path = os.path.join(parent_dir, safe_name)
                        print(f"{Fore.YELLOW}Extracting unknown EOBJ => {safe_name}{Fore.RESET}")
                else:
                    # fallback for everything else
                    # hex_str = hash_dec_to_hex(dwHash)
                    safe_name = f"{dwHash}.{ext_guess}"
                    save_path = os.path.join(parent_dir, safe_name)
                    print(f"{Fore.YELLOW}Extracting unknown: {safe_name}{Fore.RESET}")

            with open(save_path, "wb") as out_f:
                out_f.write(data)

            loop += 12

    print(f"{Fore.GREEN}Finished processing: {dat_file}{Fore.RESET}")

if __name__ == "__main__":
    main()
