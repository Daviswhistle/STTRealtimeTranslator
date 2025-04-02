# ui.py
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, font as tkFont
from config import LANGUAGES
import traceback
import os
import platform

# <<< FloatingWindow 클래스 수정 >>>
class FloatingWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        try: self.wm_attributes("-alpha", 0.85)
        except tk.TclError: print("알파 투명도 설정 실패 (지원되지 않는 시스템일 수 있음)")

        self.configure(bg="#606060")

        # --- Initial Size & Font ---
        self.initial_width = 800
        self.initial_height = 100
        self.min_width = 250
        self.min_height = 60
        self.geometry(f"{self.initial_width}x{self.initial_height}")

        self.initial_font_size = 18
        self.min_font_size = 8
        self.base_font_ratio = self.initial_font_size / self.initial_height if self.initial_height > 0 else 0.18
        self.label_font = tkFont.Font(family="Arial", size=self.initial_font_size, weight="bold")

        # --- Widgets ---
        self.content_frame = tk.Frame(self, bg=self.cget('bg'))
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.translated_label_float = tk.Label(
            self.content_frame, text="", anchor='w', justify=tk.LEFT,
            bg=self.cget('bg'), fg="#FFFFFF", font=self.label_font,
        )
        self.translated_label_float.pack(pady=5, padx=15, fill=tk.BOTH, expand=True)

        self.close_button = tk.Button(
            self, text="✕", command=self.hide,
            bg="#888888", fg="#FFFFFF", font=("Arial", 10),
            relief=tk.FLAT, bd=0, width=3, highlightthickness=0
        )
        self.close_button.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

        # --- Resizing & Dragging State ---
        # <<< 탑 그립 크기 별도 정의 >>>
        self.grip_size = 8      # 일반 그립 크기 (약간 줄임)
        self.top_grip_size = 5  # 상단 그립 크기 (더 작게)
        # --- 나머지 상태 변수 동일 ---
        self.in_resize_grip = False
        self.resizing = False
        self.dragging = False
        self.resize_handle = None
        self._offset_x = 0; self._offset_y = 0
        self._resize_origin_x = 0; self._resize_origin_y = 0

        # --- Cursor Mapping (동일) ---
        self.cursor_default = "arrow"
        os_name = platform.system()
        self.cursor_resize_map = {
            'n': "sb_v_double_arrow", 's': "sb_v_double_arrow",
            'e': "sb_h_double_arrow", 'w': "sb_h_double_arrow",
            'nw': "size_nw_se" if os_name == "Windows" else "top_left_corner",
            'ne': "size_ne_sw" if os_name == "Windows" else "top_right_corner",
            'sw': "size_ne_sw" if os_name == "Windows" else "bottom_left_corner",
            'se': "size_nw_se" if os_name == "Windows" else "bottom_right_corner",
        }

        # --- Bindings (동일) ---
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_motion)
        self.bind("<B1-Motion>", self.on_drag_motion)
        self.content_frame.bind("<ButtonPress-1>", self.on_press)
        self.content_frame.bind("<ButtonRelease-1>", self.on_release)
        self.content_frame.bind("<B1-Motion>", self.on_drag_motion)
        self.translated_label_float.bind("<ButtonPress-1>", self.on_press)
        self.translated_label_float.bind("<ButtonRelease-1>", self.on_release)
        self.translated_label_float.bind("<B1-Motion>", self.on_drag_motion)

        self.withdraw()
        self.update_font_and_wraplength()

    # <<< get_handle 메서드 수정 >>>
    def get_handle(self, x, y):
        """ Check if coordinates (x, y) relative to the window are in a resize grip """
        w = self.winfo_width()
        h = self.winfo_height()
        handle = ''

        # <<< 상단 체크 시 top_grip_size 사용 >>>
        on_top = y < self.top_grip_size
        # <<< 나머지 체크 시 일반 grip_size 사용 >>>
        on_bottom = y > h - self.grip_size
        on_left = x < self.grip_size
        on_right = x > w - self.grip_size

        # 핸들 조합
        if on_top: handle += 'n'
        elif on_bottom: handle += 's' # elif 사용으로 상하 동시 감지 방지

        if on_left: handle += 'w'
        elif on_right: handle += 'e' # elif 사용으로 좌우 동시 감지 방지

        # 코너 우선 순위 처리 (예: 'nw'가 감지되면 'n'이나 'w'는 무시되어야 함)
        # 현재 로직은 자동으로 조합되므로 ('n' + 'w' = 'nw') 별도 처리는 불필요할 수 있음
        # 하지만 명확성을 위해 코너 핸들 직접 반환 고려 가능
        # 예: if on_top and on_left: return 'nw' ... 등

        # 생성된 핸들이 유효한지 확인 (n, s, e, w, ne, nw, se, sw 중 하나인지)
        if handle in ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']:
            return handle
        else:
            return None # 유효하지 않은 조합 또는 그립 영역 밖

    # ... (on_motion, on_press, on_drag_motion, on_release 메서드는 동일하게 유지) ...
    def on_motion(self, event):
        if not self.resizing and not self.dragging:
            handle = self.get_handle(event.x, event.y)
            cursor = self.cursor_resize_map.get(handle, self.cursor_default) if handle else self.cursor_default
            if self.cget('cursor') != cursor: self.config(cursor=cursor)
            self.in_resize_grip = bool(handle)

    def on_press(self, event):
        if event.widget == self.close_button: return
        handle = self.get_handle(event.x, event.y)
        if handle:
            self.resizing = True; self.dragging = False; self.resize_handle = handle
            self._resize_origin_x = event.x_root; self._resize_origin_y = event.y_root
            cursor = self.cursor_resize_map.get(handle, self.cursor_default)
            self.config(cursor=cursor)
        else:
            self.resizing = False; self.dragging = True
            self._offset_x = event.x; self._offset_y = event.y

    def on_drag_motion(self, event):
        if self.resizing and self.resize_handle:
            current_x_root = event.x_root; current_y_root = event.y_root
            delta_x = current_x_root - self._resize_origin_x; delta_y = current_y_root - self._resize_origin_y
            current_w = self.winfo_width(); current_h = self.winfo_height()
            current_x = self.winfo_x(); current_y = self.winfo_y()
            new_w, new_h = current_w, current_h; new_x, new_y = current_x, current_y

            if 'e' in self.resize_handle: new_w = max(self.min_width, current_w + delta_x)
            if 'w' in self.resize_handle:
                new_w = max(self.min_width, current_w - delta_x)
                if new_w > self.min_width: new_x = current_x + delta_x
            if 's' in self.resize_handle: new_h = max(self.min_height, current_h + delta_y)
            if 'n' in self.resize_handle:
                new_h = max(self.min_height, current_h - delta_y)
                if new_h > self.min_height: new_y = current_y + delta_y

            self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
            self.update_font_and_wraplength()
            self._resize_origin_x = current_x_root; self._resize_origin_y = current_y_root
        elif self.dragging:
            x = self.winfo_pointerx() - self._offset_x; y = self.winfo_pointery() - self._offset_y
            self.geometry(f'+{x}+{y}')

    def on_release(self, event):
        self.resizing = False; self.dragging = False; self.resize_handle = None
        if self.cget('cursor') != self.cursor_default:
             handle = self.get_handle(event.x, event.y)
             if not handle: self.config(cursor=self.cursor_default)

    # ... (update_font_and_wraplength, update_text, show, hide 메서드는 동일하게 유지) ...
    def update_font_and_wraplength(self):
        try: current_h = self.winfo_height(); current_w = self.winfo_width()
        except tk.TclError: return
        if current_h <= 0 or current_w <= 0: return

        new_font_size = max(self.min_font_size, int(self.base_font_ratio * current_h))
        self.label_font.config(size=new_font_size)

        # Frame padding (5*2) + Label padding (15*2) = 40 total horizontal padding
        new_wraplength = max(10, current_w - 40)
        self.translated_label_float.config(wraplength=new_wraplength)

        label_pady = max(5, int(current_h * 0.05))
        self.translated_label_float.pack_configure(pady=label_pady)

    def update_text(self, translated_text):
        if self.winfo_exists():
            self.translated_label_float.config(text=translated_text)
            self.translated_label_float.update_idletasks()
            try:
                req_h = self.translated_label_float.winfo_reqheight()
                frame_h = self.content_frame.winfo_height()
                label_pady = self.translated_label_float.pack_info().get('pady', 0) * 2
                if req_h > (frame_h - label_pady): self.translated_label_float.config(anchor='sw')
                else: self.translated_label_float.config(anchor='w')
            except tk.TclError: pass
            except Exception as e: print(f"Error checking label height: {e}")

    def show(self):
        if not self.winfo_exists(): return
        self.update_idletasks()
        try:
            geo = self.geometry()
            if geo.startswith("1x1"):
                self.geometry(f"{self.initial_width}x{self.initial_height}")
                self.update_idletasks()
        except tk.TclError: pass

        self.master.update_idletasks()
        master = self.master; master_w = master.winfo_width(); master_h = master.winfo_height()
        master_x = master.winfo_x(); master_y = master.winfo_y()
        win_w = self.winfo_width(); win_h = self.winfo_height()
        pos_x = master_x + (master_w // 2) - (win_w // 2)
        pos_y = master_y + master_h + 5
        screen_w = self.winfo_screenwidth(); screen_h = self.winfo_screenheight()
        if pos_x < 0: pos_x = 0;
        if pos_y < 0: pos_y = 0
        if pos_x + win_w > screen_w: pos_x = screen_w - win_w
        if pos_y + win_h > screen_h: pos_y = screen_h - win_h
        pos_x = max(0, pos_x); pos_y = max(0, pos_y)
        self.geometry(f'+{pos_x}+{pos_y}')
        self.update_font_and_wraplength()
        self.deiconify()
        self.lift()

    def hide(self):
        if self.winfo_exists(): self.withdraw()

# --- RealtimeTranslatorUI class remains unchanged ---
class RealtimeTranslatorUI:
    # ... (No changes needed in this class) ...
    def __init__(self, root, start_callback, stop_callback, get_input_devices, update_labels_callback, default_device_name=None):
        self.root = root
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.get_input_devices = get_input_devices
        self.update_labels_callback = update_labels_callback
        self.default_device_name = default_device_name
        self.selected_device = tk.StringVar()
        self.selected_source_language = tk.StringVar(value="영어 (미국)")
        self.selected_target_language = tk.StringVar(value="한국어")
        self.languages = LANGUAGES
        self.last_original_is_final = True
        self.last_translated_is_final = True
        try:
            self.floating_window = FloatingWindow(self.root)
        except Exception as e:
            print(f"FloatingWindow 생성 오류: {e}")
            traceback.print_exc()
            self.floating_window = None
        self.setup_ui()

    def setup_ui(self):
        self.root.title("실시간 번역 자막 프로그램")
        self.root.geometry("800x650")
        self.root.configure(bg="#f0f0f0")
        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # --- 오디오 장치 선택 ---
        device_frame = tk.Frame(main_frame, bg="#f0f0f0")
        device_frame.pack(fill=tk.X, pady=5)
        tk.Label(device_frame, text="오디오 입력 장치:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 5))
        device_list = []
        try:
            available_devices = self.get_input_devices()
            if available_devices: device_list = list(available_devices.keys())
            if not device_list: device_list = ["사용 가능한 장치 없음"]; self.selected_device.set(device_list[0])
        except Exception as e:
            print(f"오디오 장치 목록 로딩 오류: {e}"); traceback.print_exc(); device_list = ["오류: 장치 로딩 실패"]; self.selected_device.set(device_list[0])
        self.device_combobox = ttk.Combobox(
            device_frame, textvariable=self.selected_device, values=device_list,
            state="readonly" if device_list and "오류" not in device_list[0] and "없음" not in device_list[0] else "disabled", width=40, font=("Arial", 11))
        if device_list and "오류" not in device_list[0] and "없음" not in device_list[0]:
            if self.default_device_name and self.default_device_name in device_list: self.device_combobox.set(self.default_device_name); print(f"기본 장치 '{self.default_device_name}' 선택됨.")
            else: self.device_combobox.current(0); print(f"기본 장치 못 찾음. 첫 번째 장치 '{device_list[0]}' 선택됨.")
        self.device_combobox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # --- 컨트롤 영역 ---
        control_frame = tk.Frame(main_frame, bg="#f0f0f0")
        control_frame.pack(fill=tk.X, pady=5)
        lang_frame = tk.Frame(control_frame, bg="#f0f0f0"); lang_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(lang_frame, text="입력 언어:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0,5))
        self.source_lang_combobox = ttk.Combobox(lang_frame, textvariable=self.selected_source_language, values=list(self.languages.keys()), state="readonly", width=15, font=("Arial", 11))
        self.source_lang_combobox.pack(side=tk.LEFT, padx=5);
        if "영어 (미국)" in self.languages: self.source_lang_combobox.set("영어 (미국)")
        tk.Label(lang_frame, text="번역 언어:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=(10,5))
        self.target_lang_combobox = ttk.Combobox(lang_frame, textvariable=self.selected_target_language, values=list(self.languages.keys()), state="readonly", width=15, font=("Arial", 11))
        self.target_lang_combobox.pack(side=tk.LEFT, padx=5)
        if "한국어" in self.languages: self.target_lang_combobox.set("한국어")
        button_status_frame = tk.Frame(control_frame, bg="#f0f0f0"); button_status_frame.pack(side=tk.RIGHT, padx=5)
        self.toggle_float_button = tk.Button(button_status_frame, text="자막 창", command=self.toggle_floating_window, font=("Arial", 10), width=8)
        self.toggle_float_button.pack(side=tk.LEFT, padx=(0, 5))
        self.start_button = tk.Button(button_status_frame, text="번역 시작", command=self.toggle_recording, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=10)
        self.start_button.pack(side=tk.LEFT, padx=(10, 5))
        self.status_label = tk.Label(button_status_frame, text="대기 중", fg="gray", bg="#f0f0f0", font=("Arial", 12)); self.status_label.pack(side=tk.LEFT, padx=5)
        self.source_lang_combobox.bind('<<ComboboxSelected>>', self.update_labels_callback); self.target_lang_combobox.bind('<<ComboboxSelected>>', self.update_labels_callback)
        # --- 텍스트 영역 ---
        text_frame = tk.Frame(main_frame, bg="#f0f0f0"); text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.original_label = tk.Label(text_frame, text=f"원본 ({self.selected_source_language.get()})", bg="#f0f0f0", font=("Arial", 12, "bold"), anchor="w"); self.original_label.pack(fill=tk.X)
        self.original_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10, font=("Arial", 12), state='disabled', relief=tk.SOLID, borderwidth=1); self.original_text.pack(fill=tk.BOTH, expand=True, pady=(2, 10))
        self.translated_label = tk.Label(text_frame, text=f"번역 ({self.selected_target_language.get()})", bg="#f0f0f0", font=("Arial", 12, "bold"), anchor="w"); self.translated_label.pack(fill=tk.X)
        self.translated_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10, font=("Arial", 12), state='disabled', relief=tk.SOLID, borderwidth=1); self.translated_text.pack(fill=tk.BOTH, expand=True, pady=(2, 10))
        # --- 파일 저장 정보 ---
        info_frame = tk.Frame(main_frame, bg="#f0f0f0"); info_frame.pack(fill=tk.X, pady=(5, 0))
        results_dir = os.path.abspath("results"); info_text = f"로그 저장 경로: {results_dir}"
        tk.Label(info_frame, text=info_text, bg="#f0f0f0", font=("Arial", 9), fg="gray", justify=tk.LEFT, anchor="w").pack(side=tk.LEFT)

    def toggle_floating_window(self):
        if not self.floating_window: print("오류: 플로팅 윈도우 객체가 없습니다."); messagebox.showerror("오류", "자막 창 객체를 찾을 수 없습니다."); return
        try:
            if self.floating_window.winfo_viewable(): self.floating_window.hide()
            else: self.floating_window.show()
        except tk.TclError as e: print(f"플로팅 윈도우 토글 중 오류: {e}"); messagebox.showwarning("오류", "자막 창 상태를 변경하는 중 문제가 발생했습니다.")

    def toggle_recording(self):
        current_device = self.selected_device.get()
        if not current_device or "오류" in current_device or "없음" in current_device: messagebox.showerror("오류", "유효한 오디오 입력 장치를 선택해주세요."); return
        if self.start_button['text'] == "번역 시작":
            if self.floating_window and self.floating_window.winfo_exists(): self.floating_window.update_text("..."); self.floating_window.show()
            else: print("경고: 플로팅 윈도우를 표시할 수 없습니다.")
            self.last_original_is_final = True; self.last_translated_is_final = True
            self.original_text.config(state='normal'); self.translated_text.config(state='normal')
            self.original_text.delete('1.0', tk.END); self.translated_text.delete('1.0', tk.END)
            if self.start_callback():
                self.start_button.config(text="번역 중지", bg="#F44336"); self.status_label.config(text="번역 중...", fg="blue")
                self.device_combobox.config(state='disabled'); self.source_lang_combobox.config(state='disabled'); self.target_lang_combobox.config(state='disabled')
            else:
                self.original_text.config(state='disabled'); self.translated_text.config(state='disabled')
                if self.floating_window and self.floating_window.winfo_exists(): self.floating_window.hide()
        else:
            self.stop_callback()
            self.start_button.config(text="번역 시작", bg="#4CAF50"); self.status_label.config(text="대기 중", fg="gray")
            current_device = self.selected_device.get(); device_state = "readonly" if current_device and "오류" not in current_device and "없음" not in current_device else "disabled"
            self.device_combobox.config(state=device_state); self.source_lang_combobox.config(state='readonly'); self.target_lang_combobox.config(state='readonly')
            self.original_text.config(state='disabled'); self.translated_text.config(state='disabled')
            if self.floating_window and self.floating_window.winfo_exists(): self.floating_window.hide()

    def update_labels(self, original, translated, is_final):
        if not self.root or not self.root.winfo_exists(): return
        try:
            def _update_main_widget(widget, text, last_is_final_flag):
                widget.config(state='normal')
                try: last_line_num = int(widget.index('end-1c').split('.')[0])
                except: last_line_num = 1
                last_line_start_index = f"{last_line_num}.0"
                if last_is_final_flag: prefix = '\n' if widget.get('1.0', 'end-1c').strip() and text else ''; widget.insert(tk.END, prefix + text)
                else:
                    if widget.compare("1.0", "!=", tk.END):
                        try: last_line_end = f"{last_line_start_index} lineend"; widget.delete(last_line_start_index, last_line_end); widget.insert(last_line_start_index, text)
                        except tk.TclError as e: print(f"TclError: {e}"); prefix = '\n' if widget.get('1.0', 'end-1c').strip() else ''; widget.insert(tk.END, prefix + text)
                    else: widget.insert(tk.END, text)
                widget.see(tk.END)
                MAX_LINES=500; DELETE_BATCH_SIZE=50
                try:
                    count_str = widget.index('end-1c').split('.')[0]
                    if count_str: count=int(count_str);
                    if count > MAX_LINES: del_end=f"{count - MAX_LINES + DELETE_BATCH_SIZE}.0"; widget.delete("1.0", del_end)
                except: pass
                widget.config(state='disabled'); return is_final
            original_was_final=self.last_original_is_final; translated_was_final=self.last_translated_is_final
            self.last_original_is_final = _update_main_widget(self.original_text, original, original_was_final)
            self.last_translated_is_final = _update_main_widget(self.translated_text, translated, translated_was_final)
            if self.floating_window and self.floating_window.winfo_exists(): self.floating_window.update_text(translated)
            self.original_label.config(text=f"원본 ({self.selected_source_language.get()})"); self.translated_label.config(text=f"번역 ({self.selected_target_language.get()})")
        except tk.TclError as e:
            if "application has been destroyed" in str(e): pass
            else: print(f"UI TclError: {e}"); traceback.print_exc()
        except Exception as e:
            print(f"UI Exception: {e}"); traceback.print_exc()
            try:
                if self.original_text.winfo_exists(): self.original_text.config(state='disabled')
                if self.translated_text.winfo_exists(): self.translated_text.config(state='disabled')
            except: pass