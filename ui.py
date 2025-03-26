# ui.py
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from config import LANGUAGES
import traceback

class RealtimeTranslatorUI:
    # ... ( __init__, setup_ui, toggle_recording 은 이전과 동일하게 유지 ) ...
    def __init__(self, root, start_callback, stop_callback, get_input_devices, update_labels_callback):
        """
        start_callback, stop_callback: 녹음 시작/중지 시 호출할 함수
        get_input_devices: 오디오 입력 장치 목록을 가져오는 콜백 함수
        update_labels_callback: 언어 변경 시 레이블 업데이트 콜백 함수
        """
        self.root = root
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.get_input_devices = get_input_devices
        self.update_labels_callback = update_labels_callback

        self.selected_device = tk.StringVar()
        self.selected_source_language = tk.StringVar(value="영어 (미국)") # 기본값
        self.selected_target_language = tk.StringVar(value="한국어") # 기본값
        self.languages = LANGUAGES

        # 마지막 업데이트가 최종(final)이었는지 추적하는 상태 변수
        self.last_original_is_final = True
        self.last_translated_is_final = True

        self.setup_ui()

    # setup_ui 메서드는 변경 없음
    def setup_ui(self):
        # ... (이전 코드와 동일) ...
        self.root.title("실시간 번역 자막 프로그램")
        self.root.geometry("800x650")
        self.root.configure(bg="#f0f0f0")

        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- 오디오 장치 선택 ---
        device_frame = tk.Frame(main_frame, bg="#f0f0f0")
        device_frame.pack(fill=tk.X, pady=5)
        tk.Label(device_frame, text="오디오 입력 장치:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 5))

        try:
            device_list = list(self.get_input_devices().keys())
            if not device_list:
                 device_list = ["사용 가능한 장치 없음"]
                 self.selected_device.set(device_list[0])
        except Exception as e:
            print(f"오디오 장치 목록 로딩 오류: {e}")
            traceback.print_exc()
            device_list = ["오류: 장치 로딩 실패"]
            self.selected_device.set(device_list[0])

        self.device_combobox = ttk.Combobox(
            device_frame,
            textvariable=self.selected_device,
            values=device_list,
            state="readonly" if device_list and "오류" not in device_list[0] and "없음" not in device_list[0] else "disabled",
            width=40,
            font=("Arial", 11)
        )
        if device_list and "오류" not in device_list[0] and "없음" not in device_list[0]:
            self.device_combobox.current(0)

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
        self.original_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10, font=("Arial", 12), state='disabled', relief=tk.SOLID, borderwidth=1)
        self.original_text.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        self.translated_label = tk.Label(text_frame, text=f"번역 ({self.selected_target_language.get()})",
                                         bg="#f0f0f0", font=("Arial", 12, "bold"), anchor="w")
        self.translated_label.pack(fill=tk.X)
        self.translated_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10, font=("Arial", 12), state='disabled', relief=tk.SOLID, borderwidth=1)
        self.translated_text.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        # --- 파일 저장 정보 ---
        info_frame = tk.Frame(main_frame, bg="#f0f0f0")
        info_frame.pack(fill=tk.X, pady=(5, 0))
        info_text = f"로그 저장 경로: (프로그램 실행 폴더)" # 경로 표시 단순화
        tk.Label(info_frame, text=info_text, bg="#f0f0f0", font=("Arial", 9), fg="gray", justify=tk.LEFT, anchor="w").pack(side=tk.LEFT)


    # toggle_recording 메서드는 변경 없음
    def toggle_recording(self):
        # ... (이전 코드와 동일) ...
        current_device = self.selected_device.get()
        if not current_device or "오류" in current_device or "없음" in current_device:
            messagebox.showerror("오류", "유효한 오디오 입력 장치를 선택해주세요.")
            return

        if self.start_button['text'] == "번역 시작":
            self.last_original_is_final = True
            self.last_translated_is_final = True
            self.original_text.config(state='normal')
            self.translated_text.config(state='normal')
            self.original_text.delete('1.0', tk.END)
            self.translated_text.delete('1.0', tk.END)

            if self.start_callback():
                self.start_button.config(text="번역 중지", bg="#F44336")
                self.status_label.config(text="번역 중...", fg="blue")
                self.device_combobox.config(state='disabled')
                self.source_lang_combobox.config(state='disabled')
                self.target_lang_combobox.config(state='disabled')
            else:
                self.original_text.config(state='disabled')
                self.translated_text.config(state='disabled')

        else:
            self.stop_callback()
            self.start_button.config(text="번역 시작", bg="#4CAF50")
            self.status_label.config(text="대기 중", fg="gray")
            current_device = self.selected_device.get()
            device_state = "readonly" if current_device and "오류" not in current_device and "없음" not in current_device else "disabled"
            self.device_combobox.config(state=device_state)
            self.source_lang_combobox.config(state='readonly')
            self.target_lang_combobox.config(state='readonly')
            self.original_text.config(state='disabled')
            self.translated_text.config(state='disabled')


    # --- update_labels 메서드 수정 (정교한 인덱스 기반 + 히스토리 제한) ---
    def update_labels(self, original, translated, is_final):
        """
        텍스트 영역 업데이트. 정교한 인덱스로 마지막 줄만 업데이트 + 히스토리 제한.
        """
        if not self.root or not self.root.winfo_exists():
            return

        # 디버깅 로그는 필요 시 주석 해제
        # print(f"\n--- update_labels START ---")
        # print(f"Input: original='{original}', translated='{translated}', is_final={is_final}")
        # print(f"State before update: last_original_final={self.last_original_is_final}, last_translated_final={self.last_translated_is_final}")

        try:
            # === 공통 업데이트 함수 ===
            def _update_widget(widget, text, last_is_final_flag):
                widget.config(state='normal')

                # 마지막 줄 번호 (1부터 시작) 및 시작 인덱스 계산
                # 'end-1c'는 마지막 문자 위치, '.0'은 줄 번호
                try:
                    last_line_num = int(widget.index('end-1c').split('.')[0])
                except tk.TclError: # 위젯이 완전히 비어있을 때 'end-1c'가 오류 발생 가능
                    last_line_num = 1
                except ValueError: # 예상치 못한 인덱스 형식
                    last_line_num = 1

                last_line_start_index = f"{last_line_num}.0"
                # print(f"  Indices: last_line_num={last_line_num}, start_index={last_line_start_index}") # 디버깅

                if last_is_final_flag:
                    # 새 문장 시작: 기존 내용 끝에 새 줄 넣고 추가
                    current_content = widget.get('1.0', 'end-1c').strip()
                    prefix = '\n' if current_content and text else ''
                    # print(f"  Action: INSERT new line (prefix='{prefix}') with text: '{text}'") # 디버깅
                    widget.insert(tk.END, prefix + text)
                else:
                    # 현재 문장 업데이트: 마지막 줄 내용만 교체
                    # print(f"  Action: REPLACE last line content") # 디버깅
                    # 위젯이 비어있지 않은지 확인 (1.0 이후 내용이 있는지)
                    if widget.compare("1.0", "!=", tk.END):
                        # 마지막 줄의 내용 끝 인덱스 (개행 문자 제외)
                        last_line_content_end_index = f"{last_line_start_index} lineend"
                        # print(f"    Deleting from {last_line_start_index} to {last_line_content_end_index}") # 디버깅
                        # 마지막 줄의 내용만 삭제
                        widget.delete(last_line_start_index, last_line_content_end_index)
                        # 삭제된 위치(마지막 줄 시작)에 새 텍스트 삽입
                        widget.insert(last_line_start_index, text)
                        # print(f"    Inserted at {last_line_start_index}: '{text}'") # 디버깅
                    else: # 위젯이 비어있었다면 그냥 끝에 추가
                         widget.insert(tk.END, text)
                         # print(f"  Widget was empty, inserted at END: '{text}'") # 디버깅

                widget.see(tk.END)

                # === 히스토리 제한 ===
                MAX_LINES = 500
                DELETE_BATCH_SIZE = 50
                current_line_count = int(widget.index('end-1c').split('.')[0])
                if current_line_count > MAX_LINES:
                    lines_to_delete = current_line_count - MAX_LINES + DELETE_BATCH_SIZE
                    delete_end_index = f"{lines_to_delete}.0"
                    # print(f"  History Limit: {current_line_count} > {MAX_LINES}. Deleting 1.0 to {delete_end_index}") # 디버깅
                    widget.delete("1.0", delete_end_index)

                widget.config(state='disabled')
                return is_final # 업데이트된 is_final 상태 반환

            # === 위젯 업데이트 실행 ===
            self.last_original_is_final = _update_widget(self.original_text, original, self.last_original_is_final)
            self.last_translated_is_final = _update_widget(self.translated_text, translated, self.last_translated_is_final)

            # print(f"State after update: last_original_final={self.last_original_is_final}, last_translated_final={self.last_translated_is_final}") # 디버깅
            # print(f"--- update_labels END ---") # 디버깅

            # 레이블 업데이트
            self.original_label.config(text=f"원본 ({self.selected_source_language.get()})")
            self.translated_label.config(text=f"번역 ({self.selected_target_language.get()})")

        except tk.TclError as e:
            # ... (이하 동일) ...
            if "application has been destroyed" in str(e): print(f"UI 업데이트 중 TclError (무시 가능 - 앱 종료 중): {e}")
            else: print(f"UI 업데이트 중 TclError 발생: {e}"); traceback.print_exc()
        except Exception as e:
            print(f"UI 업데이트 중 예외 발생: {e}"); traceback.print_exc()
            try: # 안전하게 비활성화 시도
                if self.original_text and self.original_text.winfo_exists(): self.original_text.config(state='disabled')
                if self.translated_text and self.translated_text.winfo_exists(): self.translated_text.config(state='disabled')
            except: pass