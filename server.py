import socket
import threading
import os
import zipfile
import sqlite3
from datetime import datetime

HOST = 'localhost'
PORT = 12345
FILES_DIR = 'server_files' 

os.makedirs(FILES_DIR, exist_ok=True)

def log_to_db(client_ip, filename, original_size, compressed_size, compression_ratio):
    """Функция для записи лога в SQLite базу данных"""
    try:
        conn = sqlite3.connect('download_log.db')
        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS download_log
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         client_ip TEXT,
                         filename TEXT,
                         original_size INTEGER,
                         compressed_size INTEGER,
                         compression_ratio REAL,
                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute('''INSERT INTO download_log 
                        (client_ip, filename, original_size, compressed_size, compression_ratio)
                        VALUES (?, ?, ?, ?, ?)''',
                        (client_ip, filename, original_size, compressed_size, compression_ratio))
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[LOG] Запись в БД успешна для файла {filename}")
    except Exception as err:
        print(f"[DB ERROR] Ошибка базы данных: {err}")

def get_file_list():
    """Функция для получения списка файлов на сервере"""
    files = []
    try:
        for filename in os.listdir(FILES_DIR):
            filepath = os.path.join(FILES_DIR, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                files.append(f"{filename}|{size}")
        return ";".join(files)
    except Exception as e:
        print(f"[ERROR] Ошибка при получении списка файлов: {e}")
        return ""

def compress_file(filename):
    """Функция для сжатия файла в ZIP-архив"""
    try:
        filepath = os.path.join(FILES_DIR, filename)
        if not os.path.exists(filepath):
            return None, None, None

        original_size = os.path.getsize(filepath)
        zip_filename = f"{filename}.zip"
        zip_path = os.path.join(FILES_DIR, zip_filename)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(filepath, filename)
        compressed_size = os.path.getsize(zip_path)
        if original_size > 0:
            compression_ratio = (1 - compressed_size / original_size) * 100
        else:
            compression_ratio = 0.0

        return zip_path, original_size, compression_ratio
    except Exception as e:
        print(f"[ERROR] Ошибка при сжатии файла {filename}: {e}")
        return None, None, None

def handle_client(conn, addr):
    """Обработка подключения клиента"""
    print(f"[NEW CONNECTION] Подключился {addr}")
    
    try:
        while True:
            command = conn.recv(1024).decode('utf-8')
            if not command:
                break

            print(f"[COMMAND FROM {addr}] {command}")

            if command == "LIST":
                file_list = get_file_list()
                conn.send(file_list.encode('utf-8'))
                print(f"[SENT] Список файлов отправлен клиенту {addr}")

            elif command.startswith("DOWNLOAD"):
                try:
                    _, filename = command.split("|")
                    zip_path, original_size, compression_ratio = compress_file(filename)
                    
                    if zip_path and original_size is not None:
                        file_info = f"SUCCESS|{original_size}|{compression_ratio:.2f}"
                        conn.send(file_info.encode('utf-8'))
                        print(f"[INFO] Отправлена информация о файле: {file_info}")
                        response = conn.recv(1024).decode('utf-8')
                        if response == "READY":
                            with open(zip_path, 'rb') as f:
                                file_data = f.read()
                            file_size = len(file_data)
                            conn.send(str(file_size).encode('utf-8'))
                            ack = conn.recv(1024).decode('utf-8')
                            if ack == "SIZE_RECEIVED":
                                total_sent = 0
                                chunk_size = 8192
                                for i in range(0, file_size, chunk_size):
                                    chunk = file_data[i:i + chunk_size]
                                    conn.send(chunk)
                                    total_sent += len(chunk)
                                    print(f"[PROGRESS] Отправлено {total_sent}/{file_size} байт")
                                conn.send(b"FILE_END")
                                print(f"[SENT] Файл {zip_path} полностью отправлен клиенту {addr}")
                                compressed_size = os.path.getsize(zip_path)
                                log_to_db(addr[0], filename, original_size, compressed_size, compression_ratio)
                                try:
                                    os.remove(zip_path)
                                    print(f"[CLEANUP] Временный файл {zip_path} удален")
                                except Exception as e:
                                    print(f"[WARNING] Не удалось удалить временный файл: {e}")
                            else:
                                print(f"[ERROR] Клиент не подтвердил получение размера файла")
                    else:
                        error_msg = "ERROR|Файл не найден или ошибка сжатия"
                        conn.send(error_msg.encode('utf-8'))
                        print(f"[ERROR] {error_msg}")
                        
                except Exception as e:
                    error_msg = f"ERROR|Ошибка обработки запроса: {str(e)}"
                    conn.send(error_msg.encode('utf-8'))
                    print(f"[ERROR] {error_msg}")

            elif command == "EXIT":
                print(f"[CLIENT EXIT] Клиент {addr} отключился")
                break

    except Exception as e:
        print(f"[ERROR] Ошибка при работе с клиентом {addr}: {e}")
    finally:
        conn.close()
        print(f"[DISCONNECT] Клиент {addr} отключен")

def start_server():
    """Запуск сервера"""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((HOST, PORT))
        server.listen()
        print(f"[SERVER STARTED] Сервер слушает на {HOST}:{PORT}")
        print(f"[FILES DIR] Файлы берутся из папки: {os.path.abspath(FILES_DIR)}")

        files = os.listdir(FILES_DIR)
        if files:
            print(f"[FILES] Найдены файлы: {', '.join(files)}")
        else:
            print(f"[WARNING] В папке {FILES_DIR} нет файлов! Добавьте файлы для тестирования.")

        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

    except Exception as e:
        print(f"[FATAL ERROR] Не удалось запустить сервер: {e}")

if __name__ == "__main__":
    start_server()