# import serial
# s = serial.Serial('COM3', 9600, timeout=10)   # or '/dev/ttyUSB0' on Linux
# print(s.name)  
# data = s.read(128)
# print(data)          # raw bytes
# print(data.hex())    # hex string
# s.close()


# serial_card_reader.py
# pip install pyserial
import re
import sys
import time
from serial import Serial, SerialException
from serial.tools import list_ports

# ---------- Helpers ----------
TRACK1_RE = re.compile(r'%B([^?]+)\?')    # Track 1: %B<primary account data>?
TRACK2_RE = re.compile(r';([0-9=]+)\?')   # Track 2: ;<digits>=<expiry+svc>? or similar

def find_ports():
    ports = list_ports.comports()
    for p in ports:
        print(f"{p.device} - {p.description} - hwid={p.hwid}")
    return [p.device for p in ports]

def parse_possible_track_data(s):
    """Try to find Track 1 or Track 2 data inside ASCII string s."""
    t1 = TRACK1_RE.search(s)
    t2 = TRACK2_RE.search(s)
    out = {}
    if t1:
        out['track1_raw'] = t1.group(0)
        out['track1_data'] = t1.group(1)
        # Track1 format: %B<PAN>^<NAME>^<EXP+SERVICE+DISCRETIONARY>?
        parts = t1.group(1).split('^')
        out['pan'] = parts[0] if parts else None
        out['name'] = parts[1].strip() if len(parts) > 1 else None
        exp_field = parts[2] if len(parts) > 2 else None
        out['exp_and_extra'] = exp_field
    if t2:
        out['track2_raw'] = t2.group(0)
        out['track2_data'] = t2.group(1)
        # Track2 format: ;<PAN>=<YYMM><service><discretionary>?
        parts2 = t2.group(1).split('=')
        out['pan_t2'] = parts2[0] if parts2 else None
        out['expiry_t2'] = parts2[1][:4] if len(parts2) > 1 and len(parts2[1]) >= 4 else None
    return out

def hexdump(b):
    return ' '.join(f"{x:02X}" for x in b)

# ---------- Main ----------
def main():
    print("Available serial ports:")
    ports = find_ports()
    if not ports:
        print("No serial/COM ports found.")
        return

    # Pick the first port by default
    port = ports[0]
    print(f"\nAttempting to open {port} ...")

    # Common default settings; adjust to your device manual
    baudrate = 9600
    bytesize = 8
    parity = 'N'
    stopbits = 1
    timeout = 1  # seconds read timeout

    try:
        ser = Serial(port=port, baudrate=baudrate, bytesize=bytesize,
                     parity=parity, stopbits=stopbits, timeout=timeout)
    except SerialException as e:
        print("Failed to open serial port:", e)
        return

    print(f"Opened {ser.port} @ {ser.baudrate},{ser.bytesize}{ser.parity}{ser.stopbits}")
    print("Reading... Swipe card (or press Ctrl-C to exit).")
    try:
        buffer = b''
        while True:
            b = ser.read(64)  # read up to 64 bytes
            if not b:
                # no data this loop
                continue

            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{ts}] RAW BYTES ({len(b)}): {hexdump(b)}")

            # try interpret as ascii
            try:
                s = b.decode('utf-8', errors='ignore')
            except Exception:
                s = ''

            if s:
                print("ASCII:", repr(s))
                parsed = parse_possible_track_data(s)
                if parsed:
                    print("== Parsed track data ==")
                    for k,v in parsed.items():
                        print(f"  {k}: {v}")
                else:
                    print("No Track1/2 pattern detected in ASCII.")
            else:
                print("No printable ASCII detected; raw frame likely binary/proprietary.")

            # keep a small rolling buffer if the reader splits frames
            buffer += b
            if len(buffer) > 4096:
                buffer = buffer[-4096:]

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        ser.close()





def other_func():
    # uid_extractor.py
    # pip install pyserial   (only needed if you plan to read directly from the COM port)
    import binascii

    # Example observed payload (the ASCII chunk between ; and \r\n)
    observed = "372EC011" # observed = "37002EC011"

    # Phone UID (as hex, no colons) - change to your phone's reported UID
    phone_uid_hex = "2E50CCC7"

    def hexpairs_to_bytes(s):
        # remove any non-hex chars, ensure even length
        import re
        s2 = re.sub(r'[^0-9A-Fa-f]', '', s)
        if len(s2) % 2 == 1:
            s2 = "0" + s2
        return bytes.fromhex(s2)

    def show(b):
        return ' '.join(f"{x:02X}" for x in b)

    obs_bytes = hexpairs_to_bytes(observed)
    phone_bytes = hexpairs_to_bytes(phone_uid_hex)

    print("Observed bytes:", show(obs_bytes))
    print("Phone UID bytes:", show(phone_bytes))
    print()

    # Candidate transforms to test
    def transforms(b):
        # yield (name, bytes)
        yield ("raw", b)
        yield ("reversed", b[::-1])
        # nibble swap (swap high/low nibble inside each byte)
        yield ("nibble_swap", bytes(((x>>4) | ((x&0x0F)<<4)) & 0xFF for x in b))
        # bitwise NOT
        yield ("bitwise_not", bytes((~x) & 0xFF for x in b))
        # xor with common constants (0xFF, 0xAA, 0x55)
        for k in (0xFF, 0xAA, 0x55):
            yield (f"xor_{k:02X}", bytes((x ^ k) & 0xFF for x in b))
        # try swapping 16-bit words (if length multiple of 2)
        if len(b) % 2 == 0:
            wswap = bytearray()
            for i in range(0, len(b), 2):
                wswap.extend(b[i:i+2][::-1])
            yield ("word_swap16", bytes(wswap))
        # try splitting into 2 halves and reversing halves
        if len(b) >= 4:
            n = len(b)//2
            yield ("half_swap", b[n:] + b[:n])

    # Try matching phone bytes somewhere in candidate transforms or subsequences
    matches = []
    for name, tb in transforms(obs_bytes):
        if tb == phone_bytes:
            matches.append((name, tb, "exact"))
        # also check if phone appears as suffix or prefix inside tb or its reverse
        if phone_bytes in tb:
            matches.append((name, tb, "contains"))
        if phone_bytes in tb[::-1]:
            matches.append((name, tb, "contains_in_reverse"))

    # Print results
    if matches:
        print("MATCHES FOUND:")
        for name, tb, how in matches:
            print(f"  {name:15} {how:12} -> {show(tb)}")
    else:
        print("No direct match found with the tested transforms.")
        print("Showing all tried transforms for inspection:")
        for name, tb in transforms(obs_bytes):
            print(f"  {name:15} -> {show(tb)}")

    # If no match, try chopping off final/leading bytes (common: header + uid + checksum)
    print("\nNow try heuristics: cut off 1..3 leading and trailing bytes and test.")
    for lead_cut in range(0,4):
        for trail_cut in range(0,4):
            if lead_cut + trail_cut >= len(obs_bytes):
                continue
            sub = obs_bytes[lead_cut:len(obs_bytes)-trail_cut]
            if sub == phone_bytes:
                print(f"Exact match when cutting lead={lead_cut} trail={trail_cut}: -> {show(sub)}")
            # test reversed as well
            if sub[::-1] == phone_bytes:
                print(f"Reversed match when cutting lead={lead_cut} trail={trail_cut}: -> {show(sub)}")




def third_func():
    # discover_mapping.py
    # Usage: edit `samples` below with pairs (observed_hex, phone_uid_hex), then run:
    # python discover_mapping.py

    from itertools import permutations

    # Replace these example pairs with your actual observed hex strings and phone UIDs.
    # Observed: the ASCII hex payload you get from the reader (the part between ';' and '\r\n')
    # Phone UID: the UID your phone reports (no colons, uppercase or lowercase both ok)
    samples = [
        # Example: (observed_from_reader, phone_uid_from_phone)
        ("37002EC011", "2E50CCC7"),   # <-- replace or keep as first pair
        # Add the other pairs you collected, for example:
        ("4200955972", "9A13CF9F"),  # <-- put the phone UID for that card here
        ("47005E8C5E", "E334B244"),  # <-- and the phone UID for third card
        ("4200955973", "3ABDDF9F"),
        ("4B00B9CED5", "E6185F9C"),
    ]

    samples_valek_reader = [
        ("00473088", "2E50CCC7"), # 00000000\n
        ("00A713A7", "E334B244"), # 00A713A700000000\n
        ("00D937BA", "E6185F9C"), # 00D937BA00000000\n
        ("009AA9E4", "9A13CF9F"), # 009AA9E400000000\n
    ]

    def hex_to_bytes(s):
        import re
        s2 = re.sub(r'[^0-9A-Fa-f]', '', s)
        if len(s2) % 2 == 1:
            s2 = "0" + s2
        return bytes.fromhex(s2)

    obs_bytes_list = [hex_to_bytes(o) for o,_ in samples]
    phone_bytes_list = [hex_to_bytes(p) for _,p in samples]

    # Quick checks
    if any(len(p) != 4 for p in phone_bytes_list):
        print("Error: each phone UID must be 4 bytes (8 hex digits). Fix `samples` and re-run.")
        raise SystemExit

    if any(len(o) < 4 for o in obs_bytes_list):
        print("Error: each observed payload must be at least 4 bytes. Fix `samples` and re-run.")
        raise SystemExit

    # We'll try to map 4 phone bytes to any 4 of the observed bytes (observed may have length 5)
    obs_len = len(obs_bytes_list[0])
    phone_len = 4

    def try_find_mapping(obs_list, phone_list):
        obs_indices = list(range(obs_len))
        # choose permutations of 4 indices out of obs_len, keeping order (permute indices)
        for chosen_indices in permutations(obs_indices, phone_len):
            # derive XOR mask from first sample
            first_obs = obs_list[0]
            first_phone = phone_list[0]
            # compute mask bytes: mask[i] = phone[i] ^ obs[first_choice[i]]
            masks = [first_phone[i] ^ first_obs[chosen_indices[i]] for i in range(phone_len)]
            # Validate masks across all samples
            ok = True
            for obs, phone in zip(obs_list, phone_list):
                for i in range(phone_len):
                    obs_byte = obs[chosen_indices[i]]
                    expected = obs_byte ^ masks[i]
                    if expected != phone[i]:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                return chosen_indices, masks
        return None, None

    chosen, masks = try_find_mapping(obs_bytes_list, phone_bytes_list)
    if chosen is None:
        print("No mapping found matching all samples with a simple permutation + XOR mask.")
        print("If you have more samples, add them to `samples` and try again.")
    else:
        print("Mapping found!")
        print("Observed index -> UID byte index mapping (obs_index -> uid_index):")
        for uid_i, obs_i in enumerate(chosen):
            print(f"  UID[{uid_i}] <= OBS[{obs_i}]  (mask = 0x{masks[uid_i]:02X})")
        print("\nExample parser function (Python):\n")
        print("def parse_observed_to_uid(observed_bytes):")
        print("    # observed_bytes: bytes from your reader (e.g. bytes.fromhex('37002EC011'))")
        print("    obs = observed_bytes")
        mapping = ','.join(str(x) for x in chosen)
        mask_list = ','.join(hex(x) for x in masks)
        print(f"    mapping = [{mapping}]  # obs indices used for UID bytes")
        print(f"    masks = [{mask_list}]")
        print("    uid = bytes((obs[mapping[i]] ^ masks[i]) for i in range(4))")
        print("    return uid.hex().upper()  # returned UID hex without colons")

        # Show example result on provided samples
        print("\nVerification on provided samples:")
        for obs, phone in zip(obs_bytes_list, phone_bytes_list):
            uid = bytes((obs[chosen[i]] ^ masks[i]) for i in range(4))
            print(f"  OBS {obs.hex().upper()} -> PARSED UID {uid.hex().upper()} (phone reported {phone.hex().upper()})")


if __name__ == '__main__':
    main()
    # other_func()
    # third_func()
