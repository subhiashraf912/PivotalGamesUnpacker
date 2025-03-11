import os
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
            if "." not in relpath:
                all_files.append(relpath)
            # all_files.append((relpath, fullpath))
    return all_files


for file in gather_files("mission01"):
    print(file)
# print(gather_files("mission01"))