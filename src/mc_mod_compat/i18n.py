import json
import os
import locale
from typing import Dict, Any, Optional, List

class I18nManager:
    def __init__(self, locales_dir: str, default_lang: str = "en_US"):
        self.locales_dir = locales_dir
        self.default_lang = default_lang
        self.current_lang = default_lang
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.observers: List[Any] = [] # List of callables to notify on lang change
        
        self.load_all_locales()
        
    def load_all_locales(self):
        """Loads all .json files from the locales directory."""
        if not os.path.exists(self.locales_dir):
            os.makedirs(self.locales_dir, exist_ok=True)
            return

        for filename in os.listdir(self.locales_dir):
            if filename.endswith(".json"):
                lang_code = filename[:-5] # Remove .json
                try:
                    with open(os.path.join(self.locales_dir, filename), "r", encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                except Exception as e:
                    print(f"Error loading locale {filename}: {e}")

    def set_language(self, lang_code: str):
        """Sets the current language and notifies observers."""
        if lang_code in self.translations:
            self.current_lang = lang_code
        else:
            # Fallback to default if not found, or keep current?
            # Let's try to match prefix (e.g. zh_CN -> zh) if we supported that, 
            # but for now strict match or fallback to default.
            print(f"Language {lang_code} not found, falling back to {self.default_lang}")
            self.current_lang = self.default_lang
            
        self.notify_observers()

    def get_available_languages(self) -> Dict[str, str]:
        """Returns a dict of code -> name (from the translation file itself if available, or just code)."""
        langs = {}
        for code, data in self.translations.items():
            name = data.get("_meta", {}).get("name", code)
            langs[code] = name
        return langs

    def t(self, key: str, **kwargs) -> str:
        """
        Translate a key.
        Key format: "section.subsection.key"
        Supports string interpolation with {param}.
        """
        # 1. Try current language
        val = self._get_value(self.current_lang, key)
        
        # 2. Try default language
        if val is None and self.current_lang != self.default_lang:
            val = self._get_value(self.default_lang, key)
            
        # 3. Return key if not found
        if val is None:
            return key
        
        # 4. Interpolate
        if isinstance(val, str):
            try:
                return val.format(**kwargs)
            except KeyError:
                return val # Return raw string if interpolation fails
        return str(val)

    def _get_value(self, lang: str, key: str) -> Optional[Any]:
        data = self.translations.get(lang, {})
        keys = key.split(".")
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return None
            
            if data is None:
                return None
        return data

    def add_observer(self, callback):
        self.observers.append(callback)
        
    def notify_observers(self):
        for callback in self.observers:
            try:
                callback()
            except Exception as e:
                print(f"Error in observer: {e}")

# Global instance pattern or per-app? 
# Usually passed around, but for simplicity in this project, we can instantiate in main/app.
