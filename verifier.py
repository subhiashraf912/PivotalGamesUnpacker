from undat import ce_hash

test_line = "WHATEVER_IS_THE_NEW_FILE.EVO"
lower_val = ce_hash(test_line.lower())
print(f"lower_val: {lower_val}")
hex_str = f"{lower_val:08X}"
print(hex_str)

print("input_string".encode('ascii', errors='ignore'))