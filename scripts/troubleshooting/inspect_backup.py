import sys
import os
import argparse
from common import Config

# Simple bencode decoder
def decode_bencode(data):
    def decode_func(data, index):
        if index >= len(data):
            return None, index
        char = chr(data[index])
        if char == 'i':
            index += 1
            end = data.index(b'e', index)
            val = int(data[index:end])
            return val, end + 1
        elif char == 'l':
            index += 1
            lst = []
            while index < len(data) and chr(data[index]) != 'e':
                val, index = decode_func(data, index)
                lst.append(val)
            return lst, index + 1
        elif char == 'd':
            index += 1
            dct = {}
            while index < len(data) and chr(data[index]) != 'e':
                key, index = decode_func(data, index)
                val, index = decode_func(data, index)
                if isinstance(key, bytes):
                    key = key.decode('utf-8', errors='ignore')
                dct[key] = val
            return dct, index + 1
        elif char.isdigit():
            end = data.index(b':', index)
            length = int(data[index:end])
            val = data[end + 1 : end + 1 + length]
            return val, end + 1 + length
        return None, index

    val, _ = decode_func(data, 0)
    return val

def inspect_backup(hash_val, config):
    backup_dir = config.bt_backup_path
    file_path = os.path.join(backup_dir, f"{hash_val}.torrent")
    
    if not os.path.exists(file_path):
        print(f"Backup file not found: {file_path}")
        return

    print(f"Reading: {file_path}")
    with open(file_path, 'rb') as f:
        data = f.read()
        
    try:
        torrent = decode_bencode(data)
        info = torrent.get('info', {})
        name = info.get('name', b'').decode('utf-8', errors='ignore')
        
        print(f"Name: {name}")
        print(f"Private: {info.get('private')}")
        print(f"Announce: {torrent.get('announce')}")
        
        announce_list = torrent.get('announce-list')
        if announce_list:
            print("Announce List:")
            for tier in announce_list:
                for url in tier:
                    print(f"  - {url.decode('utf-8', errors='ignore')}")
        else:
            print("Announce List: None")
            
    except Exception as e:
        print(f"Error decoding: {e}")

def main():
    parser = argparse.ArgumentParser(description="Inspect .torrent backup file")
    parser.add_argument("hash", help="Torrent Hash")
    args = parser.parse_args()
    
    config = Config()
    inspect_backup(args.hash, config)

if __name__ == "__main__":
    main()
