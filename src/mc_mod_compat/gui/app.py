import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import webbrowser
from typing import List

from ..common import CheckStatus, ModCheckResult, KNOWN_LOADERS, CONFIG_FILE_NAME, SupportLevel
from ..config import ConfigManager
from ..i18n import I18nManager
from ..api.modrinth import ModrinthClient
from ..api.curseforge import CurseForgeClient
from ..checker.pipeline import CheckerPipeline
from ..checker.local import LocalVerificationStrategy
from ..checker.online import OnlineVerificationStrategy
from .tooltip import ToolTip

class ModCompatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.config = ConfigManager(CONFIG_FILE_NAME)
        
        # Initialize I18n
        locales_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
        self.i18n = I18nManager(locales_dir, default_lang="en_US")
        
        # Load language from config or system default (not implemented yet, defaulting to config or en_US)
        current_lang = self.config.get("language", "en_US")
        self.i18n.set_language(current_lang)
        self.i18n.add_observer(self.update_ui_text)
        
        self.title(self.i18n.t("app.title"))
        self.geometry("1000x750") # Slightly larger for extra controls
        
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
        
        self.lang_var = tk.StringVar(value=current_lang)
        self.lang_var.trace_add("write", self.on_language_change)
        
        self.status_var = tk.StringVar(value=self.i18n.t("status.ready"))
        self.progress_var = tk.DoubleVar(value=0.0)
        self.results_map = {} # Map tree item ID to ModCheckResult
        
        self.create_widgets()
        self.update_ui_text() # Initial text update

    def on_language_change(self, *args):
        lang = self.lang_var.get()
        if lang != self.i18n.current_lang:
            self.i18n.set_language(lang)
            self.save_config()

    def update_ui_text(self):
        self.title(self.i18n.t("app.title"))
        
        # Controls Frame
        self.controls_frame.config(text=self.i18n.t("app.config_title"))
        self.lbl_dir.config(text=self.i18n.t("app.dir_label"))
        self.btn_browse.config(text=self.i18n.t("app.browse_btn"))
        self.lbl_mc_ver.config(text=self.i18n.t("app.mc_ver_label"))
        self.lbl_loader.config(text=self.i18n.t("app.loader_label"))
        self.lbl_strat.config(text=self.i18n.t("app.strategies_label"))
        self.chk_online.config(text=self.i18n.t("app.online_check"))
        self.chk_local.config(text=self.i18n.t("app.local_check"))
        self.chk_relaxed.config(text=self.i18n.t("app.relaxed_check"))
        self.lbl_api_key.config(text=self.i18n.t("app.api_key_label"))
        self.btn_test_conn.config(text=self.i18n.t("app.test_conn_btn"))
        self.btn_save.config(text=self.i18n.t("app.save_btn", default="Save Settings"))
        self.lbl_lang.config(text=self.i18n.t("app.language_label", default="Language:"))
        
        # Action Button
        self.btn_start.config(text=self.i18n.t("app.start_btn"))
        
        # Treeview Headings
        self.tree.heading("status", text=self.i18n.t("columns.status"))
        self.tree.heading("file", text=self.i18n.t("columns.file"))
        self.tree.heading("mod_name", text=self.i18n.t("columns.mod_name"))
        self.tree.heading("version", text=self.i18n.t("columns.version"))
        self.tree.heading("source", text=self.i18n.t("columns.source"))
        self.tree.heading("reason", text=self.i18n.t("columns.reason"))
        
        # Status (if ready)
        if self.status_var.get() == "Ready" or self.status_var.get() == self.i18n._get_value(self.i18n.default_lang, "status.ready"): 
             # Rough check, better to track state properly
             self.status_var.set(self.i18n.t("status.ready"))

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
        self.controls_frame = ttk.LabelFrame(main_container, text="Configuration", padding=15)
        self.controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Row 1: Directory
        f_dir = ttk.Frame(self.controls_frame)
        f_dir.pack(fill=tk.X, pady=5)
        self.lbl_dir = ttk.Label(f_dir, text="Mods Directory:")
        self.lbl_dir.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(f_dir, textvariable=self.dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.btn_browse = ttk.Button(f_dir, text="Browse...", command=self.browse_dir)
        self.btn_browse.pack(side=tk.LEFT)
        
        # Row 2: MC Version & Loader
        f_ver = ttk.Frame(self.controls_frame)
        f_ver.pack(fill=tk.X, pady=5)
        
        self.lbl_mc_ver = ttk.Label(f_ver, text="Target MC Version:")
        self.lbl_mc_ver.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(f_ver, textvariable=self.mc_ver_var, width=15).pack(side=tk.LEFT, padx=(0, 20))
        
        self.lbl_loader = ttk.Label(f_ver, text="Loader:")
        self.lbl_loader.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Combobox(f_ver, textvariable=self.loader_var, values=list(KNOWN_LOADERS), width=15, state="readonly").pack(side=tk.LEFT, padx=(0, 20))
        
        # Row 3: Strategies
        f_strat = ttk.Frame(self.controls_frame)
        f_strat.pack(fill=tk.X, pady=5)
        
        self.lbl_strat = ttk.Label(f_strat, text="Strategies:")
        self.lbl_strat.pack(side=tk.LEFT, padx=(0, 10))
        self.chk_online = ttk.Checkbutton(f_strat, text="Online Check (Modrinth/CurseForge)", variable=self.use_online_var)
        self.chk_online.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(self.chk_online, lambda: self.i18n.t("app.tooltips.online_check"))
        
        self.chk_local = ttk.Checkbutton(f_strat, text="Local Metadata Check", variable=self.use_local_var)
        self.chk_local.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(self.chk_local, lambda: self.i18n.t("app.tooltips.local_check"))
        
        self.chk_relaxed = ttk.Checkbutton(f_strat, text="Relaxed Version Matching", variable=self.relaxed_var)
        self.chk_relaxed.pack(side=tk.LEFT)
        ToolTip(self.chk_relaxed, lambda: self.i18n.t("app.tooltips.relaxed_check"))
        
        # Row 4: API Key
        f_api = ttk.Frame(self.controls_frame)
        f_api.pack(fill=tk.X, pady=5)
        self.lbl_api_key = ttk.Label(f_api, text="CurseForge API Key (Optional):")
        self.lbl_api_key.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(f_api, textvariable=self.cf_key_var, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.btn_test_conn = ttk.Button(f_api, text="Test Connections", command=self.test_connection)
        self.btn_test_conn.pack(side=tk.LEFT)

        # Row 5: Language Selection (New)
        f_lang = ttk.Frame(self.controls_frame)
        f_lang.pack(fill=tk.X, pady=5)
        self.lbl_lang = ttk.Label(f_lang, text="Language:")
        self.lbl_lang.pack(side=tk.LEFT, padx=(0, 10))
        
        # Map display names to codes? Or just use codes?
        # Let's use a mapping if possible, but for now simple codes or we can get names from metadata
        # We need a list of available languages. I18nManager should provide this?
        # I'll rely on the keys of loaded translations.
        available_langs = sorted(list(self.i18n.translations.keys()))
        lang_combo = ttk.Combobox(f_lang, textvariable=self.lang_var, values=available_langs, state="readonly", width=10)
        lang_combo.pack(side=tk.LEFT)

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
        
        self.tree.bind("<Double-1>", self.on_item_double_click)
        
        # Tags for colors
        self.tree.tag_configure("confirmed", background="#e8f5e9") # Green 50
        self.tree.tag_configure("likely", background="#f1f8e9") # Light Green
        self.tree.tag_configure("possible", background="#fff3e0") # Orange 50
        self.tree.tag_configure("unsupported", background="#ffebee") # Red 50
        self.tree.tag_configure("unknown", background="#f5f5f5") # Grey 100

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
        self.config.set("language", self.lang_var.get())
        self.config.save()

    def test_connection(self):
        def _run():
            self.status_var.set(self.i18n.t("status.testing_conn"))
            mr = ModrinthClient()
            mr_ok = mr.check_connection()
            
            cf_key = self.cf_key_var.get()
            cf_ok = False
            if cf_key:
                cf = CurseForgeClient(cf_key)
                cf_ok = cf.check_connection()
            
            msg = self.i18n.t("dialog.conn_result", 
                mr_status="OK" if mr_ok else "Failed", 
                cf_status="OK" if cf_ok else "Failed (or no key)"
            )
            # Ideally "OK" and "Failed" should also be translated, but for now this is fine.
            # Or better:
            # ok_str = self.i18n.t("check_status.ok") # Assuming "ok" works for connection too
            # fail_str = "Failed" 
            
            self.after(0, lambda: messagebox.showinfo(self.i18n.t("dialog.conn_test_title"), msg))
            self.status_var.set(self.i18n.t("status.ready"))
            
        threading.Thread(target=_run, daemon=True).start()

    def start_check(self):
        path = self.dir_var.get()
        if not os.path.isdir(path):
            messagebox.showerror(self.i18n.t("dialog.error_title"), self.i18n.t("dialog.invalid_dir"))
            return
            
        self.save_config()
        self.tree.delete(*self.tree.get_children())
        self.results_map.clear()
        self.btn_start.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set(self.i18n.t("status.scanning"))
        
        threading.Thread(target=self._run_check, args=(path,), daemon=True).start()

    def _run_check(self, path: str):
        try:
            files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".jar")]
            total = len(files)
            if total == 0:
                self.after(0, lambda: messagebox.showinfo(self.i18n.t("dialog.info_title"), self.i18n.t("dialog.no_jars")))
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
                self.after(0, lambda: messagebox.showwarning(self.i18n.t("dialog.warning_title"), self.i18n.t("dialog.no_strategies")))
                return
                
            pipeline = CheckerPipeline(strategies)
            
            self.status_var.set(self.i18n.t("status.checking"))
            
            # Run pipeline
            results = pipeline.check_files(
                files, 
                self.mc_ver_var.get(), 
                self.loader_var.get(), 
                self.relaxed_var.get()
            )
            
            for res in results:
                self.after(0, self._add_result, res)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror(self.i18n.t("dialog.error_title"), str(e)))
        finally:
            self.after(0, self._finish_check)

    def _add_result(self, res: ModCheckResult):
        # Map SupportLevel to tag
        tag = "unknown"
        if res.level == SupportLevel.CONFIRMED:
            tag = "confirmed"
        elif res.level == SupportLevel.LIKELY:
            tag = "likely"
        elif res.level == SupportLevel.POSSIBLE:
            tag = "possible"
        elif res.level == SupportLevel.UNSUPPORTED:
            tag = "unsupported"
            
        # Translate status
        status_text = self.i18n.t(f"support_level.{res.level.value}", default=res.level.value)
            
        item_id = self.tree.insert("", tk.END, values=(
            status_text,
            res.file_name,
            res.mod_name or "",
            res.mod_version or "",
            res.source,
            res.reason
        ), tags=(tag,))
        
        self.results_map[item_id] = res

    def on_item_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        res = self.results_map.get(item_id)
        if res:
            self.show_details_popup(res)

    def show_details_popup(self, res: ModCheckResult):
        popup = tk.Toplevel(self)
        popup.title(self.i18n.t("details.title", default="Details"))
        popup.geometry("600x400")
        
        txt = tk.Text(popup, wrap=tk.WORD, font=("Segoe UI", 10))
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        txt.insert(tk.END, f"File: {res.file_name}\n", "header")
        txt.insert(tk.END, f"Status: {res.level.value.upper()}\n\n", "header")
        
        # Evidence
        txt.insert(tk.END, "Evidence Collected:\n", "subheader")
        
        if res.evidence:
            for ev in res.evidence:
                txt.insert(tk.END, f"- Source: {ev.source} (Confidence: {ev.confidence})\n")
                txt.insert(tk.END, f"  Result: {ev.level.value}\n")
                txt.insert(tk.END, f"  Reason: {ev.reason}\n\n")
        else:
            txt.insert(tk.END, "No evidence collected.\n")
            
        txt.tag_configure("header", font=("Segoe UI", 12, "bold"))
        txt.tag_configure("subheader", font=("Segoe UI", 11, "bold"))
        txt.config(state=tk.DISABLED)

    def _finish_check(self):
        self.btn_start.config(state=tk.NORMAL)
        self.status_var.set(self.i18n.t("status.done"))
        self.progress_var.set(100)
