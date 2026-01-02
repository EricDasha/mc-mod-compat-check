import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import webbrowser
from typing import List

from ..common import CheckStatus, ModCheckResult, KNOWN_LOADERS, CONFIG_FILE_NAME
from ..config import ConfigManager
from ..api.modrinth import ModrinthClient
from ..api.curseforge import CurseForgeClient
from ..checker.pipeline import CheckerPipeline
from ..checker.local import LocalVerificationStrategy
from ..checker.online import OnlineVerificationStrategy

class ModCompatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Minecraft Mod Compatibility Checker")
        self.geometry("1000x700")
        
        self.config = ConfigManager(CONFIG_FILE_NAME)
        
        # Styles
        self.setup_styles()
        
        # Variables
        self.dir_var = tk.StringVar(value=self.config.get("last_dir", os.getcwd()))
        self.mc_ver_var = tk.StringVar(value=self.config.get("last_mc", "1.20.1"))
        self.loader_var = tk.StringVar(value=self.config.get("last_loader", "fabric"))
        self.cf_key_var = tk.StringVar(value=self.config.get("cf_api_key", ""))
        self.use_online_var = tk.BooleanVar(value=self.config.get("use_online", True))
        self.use_local_var = tk.BooleanVar(value=self.config.get("use_local", True))
        self.relaxed_var = tk.BooleanVar(value=self.config.get("relaxed", False))
        
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)
        
        self.create_widgets()
        
    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam') # Usually better than default
        
        # Colors
        bg_color = "#f0f0f0"
        fg_color = "#333333"
        accent_color = "#007acc"
        
        self.configure(bg=bg_color)
        
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        
        # Treeview
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=25)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def create_widgets(self):
        main_container = ttk.Frame(self, padding=20)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # --- Top Control Panel ---
        controls_frame = ttk.LabelFrame(main_container, text="Configuration", padding=15)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Row 1: Directory
        f_dir = ttk.Frame(controls_frame)
        f_dir.pack(fill=tk.X, pady=5)
        ttk.Label(f_dir, text="Mods Directory:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(f_dir, textvariable=self.dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(f_dir, text="Browse...", command=self.browse_dir).pack(side=tk.LEFT)
        
        # Row 2: MC Version & Loader
        f_ver = ttk.Frame(controls_frame)
        f_ver.pack(fill=tk.X, pady=5)
        
        ttk.Label(f_ver, text="Target MC Version:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(f_ver, textvariable=self.mc_ver_var, width=15).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(f_ver, text="Loader:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Combobox(f_ver, textvariable=self.loader_var, values=list(KNOWN_LOADERS), width=15, state="readonly").pack(side=tk.LEFT, padx=(0, 20))
        
        # Row 3: Strategies
        f_strat = ttk.Frame(controls_frame)
        f_strat.pack(fill=tk.X, pady=5)
        
        ttk.Label(f_strat, text="Strategies:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(f_strat, text="Online Check (Modrinth/CurseForge)", variable=self.use_online_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(f_strat, text="Local Metadata Check", variable=self.use_local_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(f_strat, text="Relaxed Version Matching", variable=self.relaxed_var).pack(side=tk.LEFT)
        
        # Row 4: API Key
        f_api = ttk.Frame(controls_frame)
        f_api.pack(fill=tk.X, pady=5)
        ttk.Label(f_api, text="CurseForge API Key (Optional):").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(f_api, textvariable=self.cf_key_var, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(f_api, text="Test Connections", command=self.test_connection).pack(side=tk.LEFT)

        # --- Action Bar ---
        action_frame = ttk.Frame(main_container)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_start = ttk.Button(action_frame, text="Start Compatibility Check", command=self.start_check, cursor="hand2")
        self.btn_start.pack(fill=tk.X, ipady=5)

        # --- Results Table ---
        columns = ("status", "file", "mod_name", "version", "source", "reason")
        self.tree = ttk.Treeview(main_container, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("status", text="Status")
        self.tree.heading("file", text="File Name")
        self.tree.heading("mod_name", text="Mod Name")
        self.tree.heading("version", text="Version")
        self.tree.heading("source", text="Source")
        self.tree.heading("reason", text="Reason")
        
        self.tree.column("status", width=100, anchor=tk.CENTER)
        self.tree.column("file", width=200)
        self.tree.column("mod_name", width=150)
        self.tree.column("version", width=100)
        self.tree.column("source", width=80, anchor=tk.CENTER)
        self.tree.column("reason", width=200)
        
        scrollbar = ttk.Scrollbar(main_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tags for colors
        self.tree.tag_configure("ok", background="#e0f7fa")
        self.tree.tag_configure("error", background="#ffebee")
        self.tree.tag_configure("warning", background="#fff3e0")

        # --- Status Bar ---
        status_frame = ttk.Frame(self, relief=tk.SUNKEN, padding=2)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)

    def browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)
            self.save_config()

    def save_config(self):
        self.config.set("last_dir", self.dir_var.get())
        self.config.set("last_mc", self.mc_ver_var.get())
        self.config.set("last_loader", self.loader_var.get())
        self.config.set("cf_api_key", self.cf_key_var.get())
        self.config.set("use_online", self.use_online_var.get())
        self.config.set("use_local", self.use_local_var.get())
        self.config.set("relaxed", self.relaxed_var.get())
        self.config.save()

    def test_connection(self):
        def _run():
            self.status_var.set("Testing connections...")
            mr = ModrinthClient()
            mr_ok = mr.check_connection()
            
            cf_key = self.cf_key_var.get()
            cf_ok = False
            if cf_key:
                cf = CurseForgeClient(cf_key)
                cf_ok = cf.check_connection()
            
            msg = f"Modrinth: {'OK' if mr_ok else 'Failed'}\nCurseForge: {'OK' if cf_ok else 'Failed (or no key)'}"
            self.after(0, lambda: messagebox.showinfo("Connection Test", msg))
            self.status_var.set("Ready")
            
        threading.Thread(target=_run, daemon=True).start()

    def start_check(self):
        path = self.dir_var.get()
        if not os.path.isdir(path):
            messagebox.showerror("Error", "Invalid directory")
            return
            
        self.save_config()
        self.tree.delete(*self.tree.get_children())
        self.btn_start.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Scanning...")
        
        threading.Thread(target=self._run_check, args=(path,), daemon=True).start()

    def _run_check(self, path: str):
        try:
            files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".jar")]
            total = len(files)
            if total == 0:
                self.after(0, lambda: messagebox.showinfo("Info", "No .jar files found"))
                return

            strategies = []
            
            # Online Strategy
            if self.use_online_var.get():
                mr_client = ModrinthClient()
                cf_client = CurseForgeClient(self.cf_key_var.get()) if self.cf_key_var.get() else None
                strategies.append(OnlineVerificationStrategy(mr_client, cf_client))
            
            # Local Strategy
            if self.use_local_var.get():
                strategies.append(LocalVerificationStrategy())
            
            if not strategies:
                self.after(0, lambda: messagebox.showwarning("Warning", "No strategies selected!"))
                return
                
            pipeline = CheckerPipeline(strategies)
            
            self.status_var.set("Checking mods...")
            
            # Run pipeline
            # Note: Pipeline is currently designed to run all at once for batching.
            # To show progress, we might need to batch manually here or update pipeline to callback.
            # For simplicity, let's run it and show indeterminate progress or just "Processing..."
            
            results = pipeline.check_files(
                files, 
                self.mc_ver_var.get(), 
                self.loader_var.get(), 
                self.relaxed_var.get()
            )
            
            for res in results:
                self.after(0, self._add_result, res)
                
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, self._finish_check)

    def _add_result(self, res: ModCheckResult):
        tag = "warning"
        if res.status == CheckStatus.OK:
            tag = "ok"
        elif res.status in (CheckStatus.WRONG_MC, CheckStatus.WRONG_LOADER):
            tag = "error"
            
        self.tree.insert("", tk.END, values=(
            res.status.value,
            res.file_name,
            res.mod_name or "",
            res.mod_version or "",
            res.source,
            res.reason
        ), tags=(tag,))

    def _finish_check(self):
        self.btn_start.config(state=tk.NORMAL)
        self.status_var.set("Done")
        self.progress_var.set(100)
