import tkinter as tk
from tkinter import ttk, messagebox
import socket
import os
import threading
import sqlite3
from datetime import datetime

SERVER_HOST = 'localhost'
SERVER_PORT = 12345
OUTPUT_DIR = 'D:\\repos\\Save_files\\output'

os.makedirs(OUTPUT_DIR, exist_ok=True)

class FileDownloaderClient:
    def __init__(self, root):
        self.root = root
        self.root.title("File Downloader Client")
        self.root.geometry("800x600")
        
        self.socket = None
        self.thread = None
        self.stop = False
        
        self.create_gui()
        self.connect()
        
    def create_gui(self):
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill='both', expand=True)
        
        title = ttk.Label(main, text="File Downloader Client", font=('Arial', 14, 'bold'))
        title.pack(pady=(0, 10))
        
        files_frame = ttk.LabelFrame(main, text="Files on server:", padding="10")
        files_frame.pack(fill='both', expand=True, pady=5)

        self.tree = ttk.Treeview(files_frame, columns=('name', 'size'), show='headings', height=6)
        self.tree.heading('name', text='File name')
        self.tree.heading('size', text='Size (bytes)')
        self.tree.column('name', width=400)
        self.tree.column('size', width=150)

        scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        buttons = ttk.Frame(main)
        buttons.pack(fill='x', pady=10)
        
        self.btn_refresh = ttk.Button(buttons, text="Refresh list", command=self.get_files)
        self.btn_refresh.pack(side='left', padx=5)
        
        self.btn_download = ttk.Button(buttons, text="Download selected", command=self.start_download)
        self.btn_download.pack(side='left', padx=5)
        
        self.btn_cancel = ttk.Button(buttons, text="Cancel", command=self.cancel_download, state='disabled')
        self.btn_cancel.pack(side='left', padx=5)
        
        self.btn_logs = ttk.Button(buttons, text="Show logs", command=self.show_logs)
        self.btn_logs.pack(side='left', padx=5)
        
        self.btn_open = ttk.Button(buttons, text="Open output", command=self.open_output)
        self.btn_open.pack(side='left', padx=5)

        self.progress = ttk.Progressbar(main, mode='indeterminate')
        self.progress.pack(fill='x', pady=5)

        info_frame = ttk.LabelFrame(main, text="Compression info:", padding="10")
        info_frame.pack(fill='x', pady=5)
        
        grid = ttk.Frame(info_frame)
        grid.pack(fill='x')
        
        ttk.Label(grid, text="Original:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.lbl_orig = ttk.Label(grid, text="0 bytes")
        self.lbl_orig.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(grid, text="Archive:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.lbl_comp = ttk.Label(grid, text="0 bytes")
        self.lbl_comp.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(grid, text="Ratio:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.lbl_ratio = ttk.Label(grid, text="0%")
        self.lbl_ratio.grid(row=2, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(grid, text="Saved:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.lbl_save = ttk.Label(grid, text="0 bytes")
        self.lbl_save.grid(row=3, column=1, sticky='w', padx=5, pady=2)
        
        self.lbl_status = ttk.Label(info_frame, text="Select file", wraplength=600, font=('Arial', 10))
        self.lbl_status.pack(pady=5)

        self.status_text = tk.StringVar()
        self.status_text.set("Ready")
        status_bar = ttk.Label(main, textvariable=self.status_text, relief='sunken', anchor='w')
        status_bar.pack(fill='x', side='bottom', pady=(5, 0))
        
    def connect(self):
        try:
            self.status_text.set("Connecting...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.socket.settimeout(None)
            self.status_text.set("Connected")
            self.get_files()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot connect: {e}")
            self.status_text.set("Error")
            
    def get_files(self):
        try:
            self.status_text.set("Getting files...")
            self.btn_refresh.config(state='disabled')
            self.socket.send("LIST".encode('utf-8'))
            data = self.socket.recv(4096).decode('utf-8')

            for item in self.tree.get_children():
                self.tree.delete(item)
                
            if data:
                files = data.split(";")
                count = 0
                for file_info in files:
                    if "|" in file_info:
                        name, size = file_info.split("|")
                        self.tree.insert('', 'end', values=(name, size))
                        count += 1
                
                self.status_text.set(f"Found {count} files")
                self.lbl_status.config(text=f"Found {count} files")
            else:
                self.status_text.set("No files")
                self.lbl_status.config(text="No files")
                        
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.status_text.set("Error")
        finally:
            self.btn_refresh.config(state='normal')
            
    def start_download(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select file")
            return

        self.btn_download.config(state='disabled')
        self.btn_refresh.config(state='disabled')
        self.btn_cancel.config(state='normal')
        self.progress.start()
        
        filename = self.tree.item(selected[0])['values'][0]
        self.stop = False
        self.thread = threading.Thread(target=self.download, args=(filename,))
        self.thread.daemon = True
        self.thread.start()
        self.check_thread()
        
    def check_thread(self):
        if self.thread and self.thread.is_alive():
            self.root.after(100, self.check_thread)
        else:
            self.progress.stop()
            self.btn_download.config(state='normal')
            self.btn_refresh.config(state='normal')
            self.btn_cancel.config(state='disabled')
            
    def cancel_download(self):
        self.stop = True
        self.status_text.set("Cancelling...")
        
    def download(self, filename):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((SERVER_HOST, SERVER_PORT))
            
            self.status_text.set(f"Requesting {filename}...")
            self.lbl_status.config(text=f"Requesting: {filename}")
            
            sock.send(f"DOWNLOAD|{filename}".encode('utf-8'))
            response = sock.recv(1024).decode('utf-8')
            
            if self.stop:
                sock.close()
                self.status_text.set("Cancelled")
                return
                
            if response.startswith("SUCCESS"):
                parts = response.split("|")
                if len(parts) >= 4:
                    orig = int(parts[1])
                    comp = int(parts[2])
                    ratio = float(parts[3])
                    saved = orig - comp
                    
                    saved_text = f"{saved} bytes"
                    if saved > 1024:
                        saved_text = f"{saved/1024:.2f} KB"
                    if saved > 1024*1024:
                        saved_text = f"{saved/(1024*1024):.2f} MB"
                    
                    self.root.after(0, self.update_info, orig, comp, ratio, saved_text)
                    
                else:
                    orig = 0
                    comp = 0
                    ratio = 0.0
                    saved_text = "0 bytes"
                
                time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                save_name = f"{filename}_{time_str}.zip"
                save_path = os.path.join(OUTPUT_DIR, save_name)
                
                self.status_text.set("Downloading...")
                self.lbl_status.config(text=f"Downloading: {filename}\n"
                                          f"Original: {orig} bytes\n"
                                          f"Archive: {comp} bytes\n"
                                          f"Ratio: {ratio:.2f}%\n"
                                          f"Saved: {saved_text}")
                
                sock.send("READY".encode('utf-8'))
                
                size_data = sock.recv(1024).decode('utf-8')
                if not size_data.isdigit():
                    raise Exception(f"Invalid size: {size_data}")
                
                total_size = int(size_data)
                sock.send("SIZE_RECEIVED".encode('utf-8'))
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < total_size:
                        if self.stop:
                            break
                            
                        remaining = total_size - received
                        chunk = min(8192, remaining)
                        
                        try:
                            data = sock.recv(chunk)
                            if not data:
                                break
                                
                            f.write(data)
                            received += len(data)
                            
                            if total_size > 0:
                                percent = (received / total_size) * 100
                                self.root.after(0, self.update_progress, 
                                               filename, orig, comp, ratio, received, total_size, percent, saved_text, save_path)
                            
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"Error: {e}")
                            break
                
                try:
                    end = sock.recv(1024)
                    if end != b"FILE_END":
                        print("Warning: no end signal")
                except:
                    print("Warning: timeout")
                
                if self.stop:
                    try:
                        os.remove(save_path)
                    except:
                        pass
                    self.status_text.set("Cancelled")
                    self.root.after(0, self.lbl_status.config, {'text': "Cancelled"})
                    return
                
                actual = os.path.getsize(save_path)
                if actual != total_size:
                    raise Exception(f"Size error: expected {total_size}, got {actual}")
                
                info = (f"File downloaded!\n"
                        f"Original: {orig} bytes\n"
                        f"Archive: {comp} bytes\n"
                        f"Ratio: {ratio:.2f}%\n"
                        f"Saved: {saved_text}\n"
                        f"Path: {save_path}")
                
                self.root.after(0, self.lbl_status.config, {'text': info})
                self.status_text.set(f"Downloaded: {filename}")
                
                message = (f"File downloaded!\n\n"
                          f"Original: {orig} bytes\n"
                          f"Archive: {comp} bytes\n"
                          f"Ratio: {ratio:.2f}%\n"
                          f"Saved: {saved_text}\n\n"
                          f"Path:\n{save_path}")
                
                self.root.after(0, lambda: messagebox.showinfo("Success", message))
                
            else:
                error = response.replace("ERROR|", "")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error: {error}"))
                self.status_text.set("Error")
                
            sock.close()
            
        except socket.timeout:
            self.root.after(0, lambda: messagebox.showerror("Error", "Timeout"))
            self.status_text.set("Timeout")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error: {e}"))
            self.status_text.set("Error")
    
    def update_info(self, orig, comp, ratio, saved_text):
        def fmt(size):
            if size >= 1024*1024:
                return f"{size:,} bytes ({size/(1024*1024):.2f} MB)"
            elif size >= 1024:
                return f"{size:,} bytes ({size/1024:.2f} KB)"
            else:
                return f"{size:,} bytes"
        
        self.lbl_orig.config(text=fmt(orig))
        self.lbl_comp.config(text=fmt(comp))
        self.lbl_ratio.config(text=f"{ratio:.2f}%")
        self.lbl_save.config(text=saved_text)
    
    def update_progress(self, filename, orig, comp, ratio, received, total, percent, saved_text, save_path):
        self.lbl_status.config(
            text=f"Downloading: {filename}\n"
                 f"Progress: {received}/{total} bytes ({percent:.1f}%)\n"
                 f"Original: {orig} bytes\n"
                 f"Archive: {comp} bytes\n"
                 f"Ratio: {ratio:.2f}%\n"
                 f"Saved: {saved_text}\n"
                 f"Path: {save_path}"
        )
    
    def show_logs(self):
        try:
            window = tk.Toplevel(self.root)
            window.title("Download Logs")
            window.geometry("1000x500")

            tree = ttk.Treeview(window, columns=('id', 'time', 'ip', 'name', 'orig', 'comp', 'ratio', 'path'), show='headings', height=20)
            
            tree.heading('id', text='ID')
            tree.heading('time', text='Time')
            tree.heading('ip', text='IP')
            tree.heading('name', text='File name')
            tree.heading('orig', text='Original')
            tree.heading('comp', text='Archive')
            tree.heading('ratio', text='Ratio')
            tree.heading('path', text='Path')
            
            tree.column('id', width=50)
            tree.column('time', width=150)
            tree.column('ip', width=120)
            tree.column('name', width=150)
            tree.column('orig', width=100)
            tree.column('comp', width=100)
            tree.column('ratio', width=80)
            tree.column('path', width=250)
            
            scroll = ttk.Scrollbar(window, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            
            buttons = ttk.Frame(window)
            buttons.pack(fill='x', pady=5)
            
            btn_refresh = ttk.Button(buttons, text="Refresh", command=lambda: self.load_logs(tree))
            btn_refresh.pack(side='left', padx=5)
            
            btn_clear = ttk.Button(buttons, text="Clear logs", command=lambda: self.clear_logs(tree))
            btn_clear.pack(side='left', padx=5)
            
            tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
            scroll.pack(side='right', fill='y', pady=5)

            self.load_logs(tree)
            
        except Exception as e:
            messagebox.showerror("Error", f"Cannot load logs: {e}")
    
    def load_logs(self, tree):
        try:
            for item in tree.get_children():
                tree.delete(item)

            conn = sqlite3.connect('download_log.db')
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM download_log ORDER BY timestamp DESC')
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                tree.insert('', 'end', values=("", "", "", "No logs found", "", "", "", ""))
                tree.master.title("Logs (0)")
            else:
                for row in rows:
                    id_num, time, ip, name, orig, comp, ratio, path = row
                    
                    def fmt(size):
                        if not isinstance(size, (int, float)):
                            size = 0
                        if size >= 1024*1024:
                            return f"{size/1024/1024:.2f} MB"
                        elif size >= 1024:
                            return f"{size/1024:.2f} KB"
                        else:
                            return f"{size} bytes"
                    
                    ratio_text = f"{ratio:.2f}%" if ratio else "0.00%"
                    tree.insert('', 'end', values=(
                        id_num,
                        time,
                        ip,
                        name,
                        fmt(orig),
                        fmt(comp),
                        ratio_text,
                        path
                    ))
                
                tree.master.title(f"Logs ({len(rows)})")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
    
    def clear_logs(self, tree):
        if messagebox.askyesno("Confirm", "Clear all logs?"):
            try:
                conn = sqlite3.connect('download_log.db')
                cursor = conn.cursor()
                cursor.execute('DELETE FROM download_log')
                conn.commit()
                conn.close()
                
                for item in tree.get_children():
                    tree.delete(item)
                    
                tree.insert('', 'end', values=("", "", "", "Logs cleared", "", "", "", ""))
                messagebox.showinfo("Success", "Logs cleared")
                tree.master.title("Logs (0)")
                
            except Exception as e:
                messagebox.showerror("Error", f"Cannot clear: {e}")
    
    def open_output(self):
        try:
            os.startfile(OUTPUT_DIR)
        except:
            messagebox.showerror("Error", f"Cannot open: {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FileDownloaderClient(root)
        root.mainloop()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter...")