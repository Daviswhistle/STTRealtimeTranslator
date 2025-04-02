# ui.py
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, font as tkFont # <<< Import font module >>>
from config import LANGUAGES
import traceback
import os
import platform # For platform-specific cursors

# <<< FloatingWindow 클래스 수정 >>>
class FloatingWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        try:
            self.wm_attributes("-alpha", 0.85)
        except tk.TclError:
            print("알파 투명도 설정 실패 (지원되지 않는 시스템일 수 있음)")

        self.configure(bg="#606060")

        # --- Initial Size & Font ---
        self.initial_width = 800
        self.initial_height = 100
        self.min_width = 250  # Minimum window size
        self.min_height = 60
        self.geometry(f"{self.initial_width}x{self.initial_height}")

        self.initial_font_size = 18
        self.min_font_size = 8 # Minimum font size
        # Calculate base ratio based on height (or avg of width/height)
        self.base_font_ratio = self.initial_font_size / self.initial_height if self.initial_height > 0 else 0.18

        # Store font object for easier modification
        self.label_font = tkFont.Font(family="Arial", size=self.initial_font_size, weight="bold")

        # --- Widgets ---
        # Use a Frame to contain the label and make padding easier
        self.content_frame = tk.Frame(self, bg=self.cget('bg'))
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5) # Add padding around the frame

        self.translated_label_float = tk.Label(
            self.content_frame, # Place label inside the frame
            text="", anchor='w', justify=tk.LEFT,
            bg=self.cget('bg'), fg="#FFFFFF",
            font=self.label_font,
            # Wraplength will be updated dynamically
        )
        # Pack label inside the frame, allow it to expand
        self.translated_label_float.pack(pady=5, padx=15, fill=tk.BOTH, expand=True) # Padding inside frame


        self.close_button = tk.Button(
            self, text="✕", command=self.hide, # Use a better 'X' symbol
            bg="#888888", fg="#FFFFFF", font=("Arial", 10),
            relief=tk.FLAT, bd=0, width=3, highlightthickness=0 # Ensure flatness
        )
        self.close_button.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

        # --- Resizing & Dragging State ---
        self.grip_size = 10 # Pixels for resize handles
        self.in_resize_grip = False
        self.resizing = False
        self.dragging = False
        self.resize_handle = None # e.g., 'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'
        self._offset_x = 0
        self._offset_y = 0
        self._resize_origin_x = 0
        self._resize_origin_y = 0

        # --- Cursor Mapping ---
        self.cursor_default = "arrow"
        # Platform specific cursors are ideal but require checks
        os_name = platform.system()
        self.cursor_resize_map = {
            'n': "sb_v_double_arrow",
            's': "sb_v_double_arrow",
            'e': "sb_h_double_arrow",
            'w': "sb_h_double_arrow",
            # Diagonal cursors might vary more by platform/tk version
            'nw': "size_nw_se" if os_name == "Windows" else "top_left_corner",
            'ne': "size_ne_sw" if os_name == "Windows" else "top_right_corner",
            'sw': "size_ne_sw" if os_name == "Windows" else "bottom_left_corner",
            'se': "size_nw_se" if os_name == "Windows" else "bottom_right_corner",
        }

        # --- Bindings ---
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_motion)          # Detect cursor position for grips
        self.bind("<B1-Motion>", self.on_drag_motion) # Handle both dragging and resizing
        # Bind content frame/label for dragging as well
        self.content_frame.bind("<ButtonPress-1>", self.on_press)
        self.content_frame.bind("<ButtonRelease-1>", self.on_release)
        self.content_frame.bind("<B1-Motion>", self.on_drag_motion)
        self.translated_label_float.bind("<ButtonPress-1>", self.on_press)
        self.translated_label_float.bind("<ButtonRelease-1>", self.on_release)
        self.translated_label_float.bind("<B1-Motion>", self.on_drag_motion)

        self.withdraw()
        self.update_font_and_wraplength() # Initial setup

    def get_handle(self, x, y):
        """ Check if coordinates (x, y) relative to the window are in a resize grip """
        w = self.winfo_width()
        h = self.winfo_height()
        handle = ''
        if y < self.grip_size: handle += 'n'
        elif y > h - self.grip_size: handle += 's'
        if x < self.grip_size: handle += 'w'
        elif x > w - self.grip_size: handle += 'e'

        # Prioritize corners
        if handle == 'nw' or handle == 'ne' or handle == 'sw' or handle == 'se':
            return handle
        elif handle == 'n' or handle == 's' or handle == 'w' or handle == 'e':
            return handle
        else:
            return None

    def on_motion(self, event):
        """ Update cursor when mouse moves over grips (if not currently interacting) """
        if not self.resizing and not self.dragging:
            handle = self.get_handle(event.x, event.y)
            cursor = self.cursor_resize_map.get(handle, self.cursor_default) if handle else self.cursor_default
            if self.cget('cursor') != cursor:
                self.config(cursor=cursor)
            self.in_resize_grip = bool(handle) # Track if mouse is over a grip

    def on_press(self, event):
        """ Start dragging or resizing """
        # Ignore clicks on the button itself
        if event.widget == self.close_button:
            return

        handle = self.get_handle(event.x, event.y)
        if handle:
            self.resizing = True
            self.dragging = False
            self.resize_handle = handle
            # Use root coordinates for resizing calculations
            self._resize_origin_x = event.x_root
            self._resize_origin_y = event.y_root
            # Set cursor explicitly during resize
            cursor = self.cursor_resize_map.get(handle, self.cursor_default)
            self.config(cursor=cursor)
        else: # Start dragging
            self.resizing = False
            self.dragging = True
            # Use relative coordinates for dragging window position
            self._offset_x = event.x
            self._offset_y = event.y

    def on_drag_motion(self, event):
        """ Handle window move or resize based on state """
        if self.resizing and self.resize_handle:
            current_x_root = event.x_root
            current_y_root = event.y_root
            delta_x = current_x_root - self._resize_origin_x
            delta_y = current_y_root - self._resize_origin_y

            current_w = self.winfo_width()
            current_h = self.winfo_height()
            current_x = self.winfo_x()
            current_y = self.winfo_y()

            new_w, new_h = current_w, current_h
            new_x, new_y = current_x, current_y

            # Adjust width/height/position based on handle
            if 'e' in self.resize_handle: new_w = max(self.min_width, current_w + delta_x)
            if 'w' in self.resize_handle:
                new_w = max(self.min_width, current_w - delta_x)
                if new_w > self.min_width: new_x = current_x + delta_x # Move window left
            if 's' in self.resize_handle: new_h = max(self.min_height, current_h + delta_y)
            if 'n' in self.resize_handle:
                new_h = max(self.min_height, current_h - delta_y)
                if new_h > self.min_height: new_y = current_y + delta_y # Move window up

            # Apply geometry changes
            self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
            self.update_font_and_wraplength()

            # Update origin for next motion event for smoother resizing
            self._resize_origin_x = current_x_root
            self._resize_origin_y = current_y_root

        elif self.dragging:
            # Calculate new window top-left position
            x = self.winfo_pointerx() - self._offset_x
            y = self.winfo_pointery() - self._offset_y
            self.geometry(f'+{x}+{y}')

    def on_release(self, event):
        """ Reset interaction state """
        self.resizing = False
        self.dragging = False
        self.resize_handle = None
        # Reset cursor if needed, on_motion will handle it usually
        if self.cget('cursor') != self.cursor_default:
             # Check if still over grip before resetting
             handle = self.get_handle(event.x, event.y)
             if not handle:
                  self.config(cursor=self.cursor_default)


    def update_font_and_wraplength(self):
        """ Adjust font size and label wraplength based on current window size """
        try:
            current_h = self.winfo_height()
            current_w = self.winfo_width()
        except tk.TclError: # Can happen if called while window is being destroyed
            return

        if current_h <= 0 or current_w <= 0: return # Avoid invalid sizes

        # Calculate new font size based on height ratio
        new_font_size = max(self.min_font_size, int(self.base_font_ratio * current_h))
        self.label_font.config(size=new_font_size) # Update font object size

        # Calculate new wraplength based on width, accounting for padding
        # Frame padding (5*2) + Label padding (15*2) = 40 total horizontal padding
        new_wraplength = max(10, current_w - 40)

        self.translated_label_float.config(
            wraplength=new_wraplength
        )
        # Update dynamic padding for label (optional)
        label_pady = max(5, int(current_h * 0.05))
        self.translated_label_float.pack_configure(pady=label_pady)


    def update_text(self, translated_text):
        """ Update label text and adjust anchor for auto-scrolling effect """
        if self.winfo_exists():
            self.translated_label_float.config(text=translated_text)
            # Force update to allow calculating required height
            self.translated_label_float.update_idletasks()

            try:
                # Check if the required height exceeds the available height in the frame
                req_h = self.translated_label_float.winfo_reqheight()
                frame_h = self.content_frame.winfo_height()
                # Consider label's internal padding (pady * 2)
                label_pady = self.translated_label_float.pack_info().get('pady', 0) * 2

                # If required height > available space, anchor to bottom
                if req_h > (frame_h - label_pady):
                    self.translated_label_float.config(anchor='sw') # South-West
                else:
                    # Otherwise, anchor normally (West or Center)
                    self.translated_label_float.config(anchor='w') # West
            except tk.TclError as e:
                # Can happen during shutdown or if widgets aren't fully ready
                # print(f"TclError while checking label height: {e}")
                pass
            except Exception as e:
                print(f"Error checking label height: {e}")


    def show(self):
        if not self.winfo_exists(): return
        # Ensure window size is known before calculating position
        self.update_idletasks()

        # Check if geometry is reasonable, reset if not (e.g., 1x1+0+0)
        try:
            geo = self.geometry()
            if geo.startswith("1x1"): # Default Tk geometry before placement
                self.geometry(f"{self.initial_width}x{self.initial_height}")
                self.update_idletasks()
        except tk.TclError:
            pass # Ignore if window is destroyed

        # --- Position Calculation ---
        self.master.update_idletasks()
        master = self.master
        master_w = master.winfo_width()
        master_h = master.winfo_height()
        master_x = master.winfo_x()
        master_y = master.winfo_y()

        win_w = self.winfo_width()
        win_h = self.winfo_height()

        pos_x = master_x + (master_w // 2) - (win_w // 2)
        pos_y = master_y + master_h + 5 # Below main window

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        if pos_x < 0: pos_x = 0
        if pos_y < 0: pos_y = 0
        if pos_x + win_w > screen_w: pos_x = screen_w - win_w
        if pos_y + win_h > screen_h: pos_y = screen_h - win_h

        pos_x = max(0, pos_x)
        pos_y = max(0, pos_y)

        self.geometry(f'+{pos_x}+{pos_y}')
        # Ensure font/wrap is correct for current size *before* showing
        self.update_font_and_wraplength()
        self.deiconify()
        self.lift()

    def hide(self):
        if self.winfo_exists():
            self.withdraw()

# --- RealtimeTranslatorUI class remains unchanged from the previous version ---
# It already handles calling floating_window.show/hide and update_text correctly.
# It also has the "자막 창" toggle button.
class RealtimeTranslatorUI:
    # ... (All methods from the previous version are suitable here) ...
    # __init__, setup_ui, toggle_floating_window, toggle_recording, update_labels
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
            if not device_list:
                device_list = ["사용 가능한 장치 없음"]
                self.selected_device.set(device_list[0])
        except Exception as e:
            print(f"오디오 장치 목록 로딩 오류: {e}")
            traceback.print_exc()
            device_list = ["오류: 장치 로딩 실패"]
            self.selected_device.set(device_list[0])

        self.device_combobox = ttk.Combobox(
            device_frame, textvariable=self.selected_device, values=device_list,
            state="readonly" if device_list and "오류" not in device_list[0] and "없음" not in device_list[0] else "disabled",
            width=40, font=("Arial", 11)
        )
        if device_list and "오류" not in device_list[0] and "없음" not in device_list[0]:
            if self.default_device_name and self.default_device_name in device_list:
                self.device_combobox.set(self.default_device_name)
                print(f"기본 장치 '{self.default_device_name}' 선택됨.")
            else:
                self.device_combobox.current(0)
                print(f"기본 장치 못 찾음. 첫 번째 장치 '{device_list[0]}' 선택됨.")
        self.device_combobox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # --- 컨트롤 영역 ---
        control_frame = tk.Frame(main_frame, bg="#f0f0f0")
        control_frame.pack(fill=tk.X, pady=5)

        lang_frame = tk.Frame(control_frame, bg="#f0f0f0")
        lang_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(lang_frame, text="입력 언어:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0,5))
        self.source_lang_combobox = ttk.Combobox(
            lang_frame, textvariable=self.selected_source_language,
            values=list(self.languages.keys()), state="readonly", width=15, font=("Arial", 11)
        )
        self.source_lang_combobox.pack(side=tk.LEFT, padx=5)
        if "영어 (미국)" in self.languages: self.source_lang_combobox.set("영어 (미국)")

        tk.Label(lang_frame, text="번역 언어:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=(10,5))
        self.target_lang_combobox = ttk.Combobox(
            lang_frame, textvariable=self.selected_target_language,
            values=list(self.languages.keys()), state="readonly", width=15, font=("Arial", 11)
        )
        self.target_lang_combobox.pack(side=tk.LEFT, padx=5)
        if "한국어" in self.languages: self.target_lang_combobox.set("한국어")

        button_status_frame = tk.Frame(control_frame, bg="#f0f0f0")
        button_status_frame.pack(side=tk.RIGHT, padx=5)

        self.toggle_float_button = tk.Button(
            button_status_frame, text="자막 창", command=self.toggle_floating_window,
            font=("Arial", 10), width=8
        )
        self.toggle_float_button.pack(side=tk.LEFT, padx=(0, 5))

        self.start_button = tk.Button(button_status_frame, text="번역 시작", command=self.toggle_recording,
                                      bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=10)
        self.start_button.pack(side=tk.LEFT, padx=(10, 5))

        self.status_label = tk.Label(button_status_frame, text="대기 중", fg="gray", bg="#f0f0f0", font=("Arial", 12))
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.source_lang_combobox.bind('<<ComboboxSelected>>', self.update_labels_callback)
        self.target_lang_combobox.bind('<<ComboboxSelected>>', self.update_labels_callback)

        # --- 텍스트 영역 ---
        text_frame = tk.Frame(main_frame, bg="#f0f0f0")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.original_label = tk.Label(text_frame, text=f"원본 ({self.selected_source_language.get()})",
                                       bg="#f0f0f0", font=("Arial", 12, "bold"), anchor="w")
        self.original_label.pack(fill=tk.X)
        self.original_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10, font=("Arial", 12),
                                                       state='disabled', relief=tk.SOLID, borderwidth=1)
        self.original_text.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        self.translated_label = tk.Label(text_frame, text=f"번역 ({self.selected_target_language.get()})",
                                         bg="#f0f0f0", font=("Arial", 12, "bold"), anchor="w")
        self.translated_label.pack(fill=tk.X)
        self.translated_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10, font=("Arial", 12),
                                                         state='disabled', relief=tk.SOLID, borderwidth=1)
        self.translated_text.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        # --- 파일 저장 정보 ---
        info_frame = tk.Frame(main_frame, bg="#f0f0f0")
        info_frame.pack(fill=tk.X, pady=(5, 0))
        results_dir = os.path.abspath("results")
        info_text = f"로그 저장 경로: {results_dir}"
        tk.Label(info_frame, text=info_text, bg="#f0f0f0", font=("Arial", 9), fg="gray", justify=tk.LEFT,
                 anchor="w").pack(side=tk.LEFT)

    def toggle_floating_window(self):
        if not self.floating_window:
             print("오류: 플로팅 윈도우 객체가 없습니다.")
             messagebox.showerror("오류", "자막 창 객체를 찾을 수 없습니다.")
             return
        try:
            if self.floating_window.winfo_viewable():
                self.floating_window.hide()
            else:
                self.floating_window.show()
        except tk.TclError as e:
             print(f"플로팅 윈도우 토글 중 오류: {e}")
             messagebox.showwarning("오류", "자막 창 상태를 변경하는 중 문제가 발생했습니다.")

    def toggle_recording(self):
        current_device = self.selected_device.get()
        if not current_device or "오류" in current_device or "없음" in current_device:
            messagebox.showerror("오류", "유효한 오디오 입력 장치를 선택해주세요.")
            return

        if self.start_button['text'] == "번역 시작":
            if self.floating_window and self.floating_window.winfo_exists():
                self.floating_window.update_text("...")
                self.floating_window.show()
            else: print("경고: 플로팅 윈도우를 표시할 수 없습니다.")

            self.last_original_is_final = True
            self.last_translated_is_final = True
            self.original_text.config(state='normal'); self.translated_text.config(state='normal')
            self.original_text.delete('1.0', tk.END); self.translated_text.delete('1.0', tk.END)

            if self.start_callback():
                self.start_button.config(text="번역 중지", bg="#F44336")
                self.status_label.config(text="번역 중...", fg="blue")
                self.device_combobox.config(state='disabled')
                self.source_lang_combobox.config(state='disabled')
                self.target_lang_combobox.config(state='disabled')
            else:
                self.original_text.config(state='disabled'); self.translated_text.config(state='disabled')
                if self.floating_window and self.floating_window.winfo_exists(): self.floating_window.hide()
        else:
            self.stop_callback()
            self.start_button.config(text="번역 시작", bg="#4CAF50")
            self.status_label.config(text="대기 중", fg="gray")
            current_device = self.selected_device.get()
            device_state = "readonly" if current_device and "오류" not in current_device and "없음" not in current_device else "disabled"
            self.device_combobox.config(state=device_state)
            self.source_lang_combobox.config(state='readonly')
            self.target_lang_combobox.config(state='readonly')
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
                if last_is_final_flag:
                    prefix = '\n' if widget.get('1.0', 'end-1c').strip() and text else ''
                    widget.insert(tk.END, prefix + text)
                else:
                    if widget.compare("1.0", "!=", tk.END):
                        try:
                            last_line_end = f"{last_line_start_index} lineend"
                            widget.delete(last_line_start_index, last_line_end)
                            widget.insert(last_line_start_index, text)
                        except tk.TclError as e:
                            print(f"TclError updating last line: {e}")
                            prefix = '\n' if widget.get('1.0', 'end-1c').strip() else ''
                            widget.insert(tk.END, prefix + text)
                    else: widget.insert(tk.END, text)
                widget.see(tk.END)
                # History limit
                MAX_LINES = 500; DELETE_BATCH_SIZE = 50
                try:
                    count_str = widget.index('end-1c').split('.')[0]
                    if count_str:
                        count = int(count_str)
                        if count > MAX_LINES:
                            del_end = f"{count - MAX_LINES + DELETE_BATCH_SIZE}.0"
                            widget.delete("1.0", del_end)
                except: pass # Ignore errors during cleanup
                widget.config(state='disabled')
                return is_final

            original_was_final = self.last_original_is_final
            translated_was_final = self.last_translated_is_final
            self.last_original_is_final = _update_main_widget(self.original_text, original, original_was_final)
            self.last_translated_is_final = _update_main_widget(self.translated_text, translated, translated_was_final)

            if self.floating_window and self.floating_window.winfo_exists():
                self.floating_window.update_text(translated)

            self.original_label.config(text=f"원본 ({self.selected_source_language.get()})")
            self.translated_label.config(text=f"번역 ({self.selected_target_language.get()})")

        except tk.TclError as e:
            if "application has been destroyed" in str(e): pass # Ignore during shutdown
            else: print(f"UI update TclError: {e}"); traceback.print_exc()
        except Exception as e:
            print(f"UI update Exception: {e}"); traceback.print_exc()
            try:
                if self.original_text.winfo_exists(): self.original_text.config(state='disabled')
                if self.translated_text.winfo_exists(): self.translated_text.config(state='disabled')
            except: pass