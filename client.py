import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket
import os
import threading
import sqlite3
from datetime import datetime

SERVER_HOST = 'localhost'
SERVER_PORT = 12345

class FileDownloaderClient:
    def __init__(self, root):
        self.root = root
        self.root.title("File Downloader Client")
        self.root.geometry("800x600")
        
        self.socket = None
        self.download_thread = None
        self.stop_download = False
        
        self.setup_ui()
        self.connect_to_server()
        
    def setup_ui(self):
        """Создание графического интерфейса"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)
        title_label = ttk.Label(main_frame, text="File Downloader Client", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        frame_files = ttk.LabelFrame(main_frame, text="Файлы на сервере:", padding="10")
        frame_files.pack(fill='both', expand=True, pady=5)

        columns = ('filename', 'size')
        self.tree_files = ttk.Treeview(frame_files, columns=columns, show='headings', height=6)
        self.tree_files.heading('filename', text='Имя файла')
        self.tree_files.heading('size', text='Размер (байт)')
        self.tree_files.column('filename', width=400)
        self.tree_files.column('size', width=150)

        scrollbar = ttk.Scrollbar(frame_files, orient="vertical", command=self.tree_files.yview)
        self.tree_files.configure(yscrollcommand=scrollbar.set)
        
        self.tree_files.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        frame_buttons = ttk.Frame(main_frame)
        frame_buttons.pack(fill='x', pady=10)
        
        self.btn_refresh = ttk.Button(frame_buttons, text="Обновить список", 
                                     command=self.refresh_file_list)
        self.btn_refresh.pack(side='left', padx=5)
        
        self.btn_download = ttk.Button(frame_buttons, text="Скачать выбранный", 
                                      command=self.start_download_thread)
        self.btn_download.pack(side='left', padx=5)
        
        self.btn_cancel = ttk.Button(frame_buttons, text="Отменить", 
                                    command=self.cancel_download, state='disabled')
        self.btn_cancel.pack(side='left', padx=5)
        
        self.btn_show_logs = ttk.Button(frame_buttons, text="Показать логи", 
                                       command=self.show_logs)
        self.btn_show_logs.pack(side='left', padx=5)

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=5)

        frame_info = ttk.LabelFrame(main_frame, text="Информация о скачивании:", padding="10")
        frame_info.pack(fill='x', pady=5)
        
        self.lbl_info = ttk.Label(frame_info, text="Выберите файл для скачивания", 
                                 wraplength=600)
        self.lbl_info.pack(pady=5)

        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief='sunken', anchor='w')
        status_bar.pack(fill='x', side='bottom', pady=(5, 0))
        
    def connect_to_server(self):
        """Подключение к серверу"""
        try:
            self.status_var.set("Подключаемся к серверу...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.socket.settimeout(None)
            self.status_var.set("Подключено к серверу")
            self.refresh_file_list()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться к серверу: {e}")
            self.status_var.set("Ошибка подключения")
            
    def refresh_file_list(self):
        """Запрос списка файлов у сервера"""
        try:
            self.status_var.set("Получаем список файлов...")
            self.btn_refresh.config(state='disabled')
            self.socket.send("LIST".encode('utf-8'))
            response = self.socket.recv(4096).decode('utf-8')

            for item in self.tree_files.get_children():
                self.tree_files.delete(item)
            if response:
                files = response.split(";")
                file_count = 0
                for file_info in files:
                    if "|" in file_info:
                        filename, size = file_info.split("|")
                        self.tree_files.insert('', 'end', values=(filename, size))
                        file_count += 1
                
                self.status_var.set(f"Найдено {file_count} файлов")
                if file_count == 0:
                    self.lbl_info.config(text="На сервере нет файлов для скачивания")
            else:
                self.status_var.set("На сервере нет файлов")
                self.lbl_info.config(text="На сервере нет файлов")
                        
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при получении списка файлов: {e}")
            self.status_var.set("Ошибка получения списка файлов")
        finally:
            self.btn_refresh.config(state='normal')
            
    def start_download_thread(self):
        """Запуск скачивания в отдельном потоке"""
        selected_item = self.tree_files.selection()
        if not selected_item:
            messagebox.showwarning("Предупреждение", "Выберите файл для скачивания")
            return

        self.btn_download.config(state='disabled')
        self.btn_refresh.config(state='disabled')
        self.btn_cancel.config(state='normal')
        self.progress.start()
        
        filename = self.tree_files.item(selected_item[0])['values'][0]
        self.stop_download = False
        self.download_thread = threading.Thread(target=self.download_file, args=(filename,))
        self.download_thread.daemon = True
        self.download_thread.start()
        self.monitor_download_thread()
        
    def monitor_download_thread(self):
        """Мониторинг состояния потока скачивания"""
        if self.download_thread and self.download_thread.is_alive():
            self.root.after(100, self.monitor_download_thread)
        else:
            self.progress.stop()
            self.btn_download.config(state='normal')
            self.btn_refresh.config(state='normal')
            self.btn_cancel.config(state='disabled')
            
    def cancel_download(self):
        """Отмена скачивания"""
        self.stop_download = True
        self.status_var.set("Отмена скачивания...")
        
    def safe_float_convert(self, value):
        """Безопасное преобразование в float"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
        
    def download_file(self, filename):
        """Скачивание файла (работает в отдельном потоке)"""
        try:
            download_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            download_socket.settimeout(30)
            download_socket.connect((SERVER_HOST, SERVER_PORT))
            
            self.status_var.set(f"Запрашиваем файл {filename}...")
            self.lbl_info.config(text=f"Подготовка к скачиванию: {filename}")
            
            download_socket.send(f"DOWNLOAD|{filename}".encode('utf-8'))
            response = download_socket.recv(1024).decode('utf-8')
            
            if self.stop_download:
                download_socket.close()
                self.status_var.set("Скачивание отменено")
                return
                
            if response.startswith("SUCCESS"):
                parts = response.split("|")
                if len(parts) >= 3:
                    original_size = parts[1]
                    compression_ratio = self.safe_float_convert(parts[2])
                else:
                    original_size = "0"
                    compression_ratio = 0.0
                
                save_path = filedialog.asksaveasfilename(
                    initialfile=f"{filename}.zip",
                    defaultextension=".zip",
                    filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
                )
                
                if save_path and not self.stop_download:
                    self.status_var.set("Скачиваем файл...")
                    self.lbl_info.config(text=f"Скачивание: {filename}\nПодготовка к передаче...")
                    
                    download_socket.send("READY".encode('utf-8'))
                    
                    file_size_data = download_socket.recv(1024).decode('utf-8')
                    if not file_size_data.isdigit():
                        raise Exception(f"Неверный размер файла: {file_size_data}")
                    
                    file_size = int(file_size_data)
                    self.lbl_info.config(text=f"Скачивание: {filename}\nРазмер: {file_size} байт")
                    
                    download_socket.send("SIZE_RECEIVED".encode('utf-8'))
                    
                    received_bytes = 0
                    with open(save_path, 'wb') as f:
                        while received_bytes < file_size:
                            if self.stop_download:
                                break
                                
                            remaining = file_size - received_bytes
                            chunk_size = min(8192, remaining)
                            
                            try:
                                data = download_socket.recv(chunk_size)
                                if not data:
                                    break
                                    
                                f.write(data)
                                received_bytes += len(data)
                                
                                if file_size > 0:
                                    progress = (received_bytes / file_size) * 100
                                    if received_bytes % max(1, file_size // 10) == 0 or received_bytes == file_size:
                                        self.lbl_info.config(
                                            text=f"Скачивание: {filename}\n"
                                                 f"Прогресс: {received_bytes}/{file_size} байт "
                                                 f"({progress:.1f}%)"
                                        )
                                
                            except socket.timeout:
                                continue
                            except Exception as e:
                                print(f"Ошибка при получении данных: {e}")
                                break
                    
                    try:
                        end_signal = download_socket.recv(1024)
                        if end_signal != b"FILE_END":
                            print(f"Предупреждение: не получен сигнал завершения")
                    except:
                        print(f"Предупреждение: таймаут при ожидании сигнала завершения")
                    
                    if self.stop_download:
                        try:
                            os.remove(save_path)
                        except:
                            pass
                        self.status_var.set("Скачивание отменено")
                        self.lbl_info.config(text="Скачивание отменено пользователем")
                        return
                    
                    actual_size = os.path.getsize(save_path)
                    if actual_size != file_size:
                        raise Exception(f"Несоответствие размера: ожидалось {file_size}, получено {actual_size}")
                    
                    compressed_size = actual_size
                    try:
                        ratio_text = f"{compression_ratio:.2f}%"
                    except:
                        ratio_text = f"{compression_ratio}%"
                    
                    info_text = (f"Файл успешно скачан!\n"
                                 f"• Исходный размер: {original_size} байт\n"
                                 f"• Размер архива: {compressed_size} байт\n"
                                 f"• Эффективность: {ratio_text}\n"
                                 f"• Сохранен как: {os.path.basename(save_path)}")

                    if compression_ratio > 0:
                        info_text += f"\n• Сжатие: УСПЕШНО (экономия {ratio_text})"
                    else:
                        info_text += f"\n• Сжатие: НЕЭФФЕКТИВНО (файл уже сжат)"
                    
                    self.lbl_info.config(text=info_text)
                    self.status_var.set(f"Файл скачан: {filename}")
                    message_text = (f"Файл успешно скачан!\n\n"
                                  f"Исходный размер: {original_size} байт\n"
                                  f"Сжатый размер: {compressed_size} байт\n"
                                  f"Эффективность: {ratio_text}\n\n"
                                  f"Сохранен как:\n{save_path}")
                    
                    self.root.after(0, lambda: messagebox.showinfo("Успех", message_text))
                    
                else:
                    self.status_var.set("Скачивание отменено")
                    
            else:
                error_msg = response.replace("ERROR|", "")
                self.root.after(0, lambda: messagebox.showerror("Ошибка", 
                    f"Ошибка при скачивании: {error_msg}"))
                self.status_var.set("Ошибка скачивания")
                
            download_socket.close()
            
        except socket.timeout:
            error_msg = "Таймаут соединения при скачивании"
            self.root.after(0, lambda: messagebox.showerror("Ошибка", error_msg))
            self.status_var.set("Таймаут скачивания")
        except Exception as e:
            error_msg = f"Ошибка при скачивании файла: {e}"
            self.root.after(0, lambda: messagebox.showerror("Ошибка", error_msg))
            self.status_var.set("Ошибка скачивания")
    
    def show_logs(self):
        """Показать окно с логами из базы данных"""
        try:
            log_window = tk.Toplevel(self.root)
            log_window.title("Логи скачиваний")
            log_window.geometry("900x500")

            columns = ('id', 'timestamp', 'client_ip', 'filename', 'original_size', 
                      'compressed_size', 'compression_ratio')
            tree_logs = ttk.Treeview(log_window, columns=columns, show='headings', height=20)
            tree_logs.heading('id', text='ID')
            tree_logs.heading('timestamp', text='Время')
            tree_logs.heading('client_ip', text='IP клиента')
            tree_logs.heading('filename', text='Имя файла')
            tree_logs.heading('original_size', text='Исходный размер')
            tree_logs.heading('compressed_size', text='Размер архива')
            tree_logs.heading('compression_ratio', text='Эффективность')
            tree_logs.column('id', width=50)
            tree_logs.column('timestamp', width=150)
            tree_logs.column('client_ip', width=120)
            tree_logs.column('filename', width=200)
            tree_logs.column('original_size', width=100)
            tree_logs.column('compressed_size', width=100)
            tree_logs.column('compression_ratio', width=100)
            scrollbar = ttk.Scrollbar(log_window, orient="vertical", command=tree_logs.yview)
            tree_logs.configure(yscrollcommand=scrollbar.set)
            frame_buttons = ttk.Frame(log_window)
            frame_buttons.pack(fill='x', pady=5)
            
            btn_refresh = ttk.Button(frame_buttons, text="Обновить", 
                                   command=lambda: self.load_logs_to_tree(tree_logs))
            btn_refresh.pack(side='left', padx=5)
            
            btn_clear = ttk.Button(frame_buttons, text="Очистить логи", 
                                 command=lambda: self.clear_logs(tree_logs))
            btn_clear.pack(side='left', padx=5)
            
            btn_export = ttk.Button(frame_buttons, text="Экспорт в CSV", 
                                  command=self.export_logs_to_csv)
            btn_export.pack(side='left', padx=5)
            tree_logs.pack(side='left', fill='both', expand=True, padx=5, pady=5)
            scrollbar.pack(side='right', fill='y', pady=5)

            self.load_logs_to_tree(tree_logs)
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить логи: {e}")
    
    def load_logs_to_tree(self, tree_widget):
        """Загрузка логов из БД в treeview"""
        try:
            for item in tree_widget.get_children():
                tree_widget.delete(item)

            conn = sqlite3.connect('download_log.db')
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, timestamp, client_ip, filename, original_size, 
                       compressed_size, compression_ratio 
                FROM download_log 
                ORDER BY timestamp DESC
            ''')
            
            rows = cursor.fetchall()
            for row in rows:
                ratio = row[6] if row[6] is not None else 0.0
                ratio_text = f"{ratio:.2f}%" if isinstance(ratio, (int, float)) else "0.00%"
                
                tree_widget.insert('', 'end', values=(
                    row[0],  # id
                    row[1],  # timestamp
                    row[2],  # client_ip
                    row[3],  # filename
                    row[4],  # original_size
                    row[5],  # compressed_size
                    ratio_text  # compression_ratio
                ))
            
            conn.close()

            if hasattr(tree_widget, 'master'):
                tree_widget.master.title(f"Логи скачиваний ({len(rows)} записей)")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке логов: {e}")
    
    def clear_logs(self, tree_widget):
        """Очистка всех логов"""
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить все логи?"):
            try:
                conn = sqlite3.connect('download_log.db')
                cursor = conn.cursor()
                cursor.execute('DELETE FROM download_log')
                conn.commit()
                conn.close()
                
                for item in tree_widget.get_children():
                    tree_widget.delete(item)
                    
                messagebox.showinfo("Успех", "Логи успешно очищены")
                tree_widget.master.title("Логи скачиваний (0 записей)")
                
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось очистить логи: {e}")
    
    def export_logs_to_csv(self):
        """Экспорт логов в CSV файл"""
        try:

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="download_logs.csv"
            )
            
            if file_path:
                conn = sqlite3.connect('download_log.db')
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, client_ip, filename, original_size, 
                           compressed_size, compression_ratio 
                    FROM download_log 
                    ORDER BY timestamp DESC
                ''')
                
                rows = cursor.fetchall()
                conn.close()

                with open(file_path, 'w', encoding='utf-8') as f:

                    f.write("Время;IP клиента;Имя файла;Исходный размер;Размер архива;Эффективность\n")

                    for row in rows:
                        ratio = row[5] if row[5] is not None else 0.0
                        ratio_text = f"{ratio:.2f}%" if isinstance(ratio, (int, float)) else "0.00%"
                        
                        f.write(f"{row[0]};{row[1]};{row[2]};{row[3]};{row[4]};{ratio_text}\n")
                
                messagebox.showinfo("Успех", f"Логи экспортированы в:\n{file_path}")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при экспорте логов: {e}")
            
    def __del__(self):
        """Закрытие соединения при завершении"""
        try:
            if self.socket:
                self.socket.send("EXIT".encode('utf-8'))
                self.socket.close()
        except:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = FileDownloaderClient(root)
    
    def on_closing():
        app.stop_download = True
        try:
            if app.socket:
                app.socket.send("EXIT".encode('utf-8'))
                app.socket.close()
        except:
            pass
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()