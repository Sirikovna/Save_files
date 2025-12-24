import socket
import threading
import os
import zipfile
import sqlite3
from datetime import datetime

HOST = 'localhost'
PORT = 12345
INPUT_DIR = 'D:\\repos\\Save_files\\input'
OUTPUT_DIR = 'D:\\repos\\Save_files\\output'

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_database():
    conn = sqlite3.connect('download_log.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            client_ip TEXT,
            filename TEXT,
            original_size INTEGER,
            compressed_size INTEGER,
            compression_ratio REAL,
            save_path TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[DB] Database table created")

def add_to_database(client_ip, filename, original_size, compressed_size, compression_ratio, save_path):
    try:
        conn = sqlite3.connect('download_log.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO download_log (client_ip, filename, original_size, compressed_size, compression_ratio, save_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (client_ip, filename, original_size, compressed_size, compression_ratio, save_path))
        conn.commit()
        conn.close()
        print(f"[DB] Added record for {filename}")
        return True
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False

def get_files():
    files = []
    try:
        for filename in os.listdir(INPUT_DIR):
            filepath = os.path.join(INPUT_DIR, filename)
            if os.path.isfile(filepath):
                if not filename.endswith('.zip'):
                    size = os.path.getsize(filepath)
                    files.append(f"{filename}|{size}")
        return ";".join(files)
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

def create_zip(filename):
    try:
        filepath = os.path.join(INPUT_DIR, filename)
        if not os.path.exists(filepath):
            return None, None, None, None

        original_size = os.path.getsize(filepath)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_name = f"{filename}_{timestamp}.zip"
        zip_path = os.path.join(OUTPUT_DIR, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(filepath, filename)
        
        compressed_size = os.path.getsize(zip_path)
        
        if original_size > 0:
            compression_ratio = (1 - compressed_size / original_size) * 100
        else:
            compression_ratio = 0.0
        
        return zip_path, original_size, compressed_size, compression_ratio
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return None, None, None, None

def handle_client(conn, addr):
    print(f"[CONNECT] {addr[0]}:{addr[1]}")
    
    try:
        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data:
                break

            if data == "LIST":
                files = get_files()
                conn.send(files.encode('utf-8'))

            elif data.startswith("DOWNLOAD"):
                _, filename = data.split("|")
                zip_path, original_size, compressed_size, compression_ratio = create_zip(filename)
                
                if zip_path:
                    info = f"SUCCESS|{original_size}|{compressed_size}|{compression_ratio:.2f}"
                    conn.send(info.encode('utf-8'))
                    
                    response = conn.recv(1024).decode('utf-8')
                    if response == "READY":
                        with open(zip_path, 'rb') as f:
                            file_data = f.read()
                        file_size = len(file_data)
                        
                        conn.send(str(file_size).encode('utf-8'))
                        ack = conn.recv(1024).decode('utf-8')
                        
                        if ack == "SIZE_RECEIVED":
                            sent = 0
                            chunk = 8192
                            for i in range(0, file_size, chunk):
                                part = file_data[i:i + chunk]
                                conn.send(part)
                                sent += len(part)
                            
                            conn.send(b"FILE_END")
                            add_to_database(addr[0], filename, original_size, compressed_size, compression_ratio, zip_path)
                else:
                    conn.send("ERROR|File error".encode('utf-8'))

            elif data == "EXIT":
                break

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        conn.close()
        print(f"[DISCONNECT] {addr[0]}")

def start_server():
    create_database()
    
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((HOST, PORT))
        server.listen(5)
        print(f"[SERVER] {HOST}:{PORT}")
        print(f"[INPUT] {INPUT_DIR}")
        print(f"[OUTPUT] {OUTPUT_DIR}")

        files = os.listdir(INPUT_DIR)
        if files:
            print("[FILES] Available:")
            for f in files:
                path = os.path.join(INPUT_DIR, f)
                if os.path.isfile(path) and not f.endswith('.zip'):
                    size = os.path.getsize(path)
                    print(f"  {f} ({size} bytes)")

        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    start_server()