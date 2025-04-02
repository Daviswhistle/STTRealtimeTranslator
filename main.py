# main.py
import threading
import queue
import tkinter as tk
import tkinter.messagebox
import traceback
import time
import os
from google.api_core.exceptions import OutOfRange
from config import ORIGINAL_FILE, TRANSLATED_FILE
from audio_recorder import AudioRecorder
from speech_recognizer import SpeechRecognizer
from translator_service import TranslatorService
from ui import RealtimeTranslatorUI

class RealtimeTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.stop_event = threading.Event()
        # <<< 초기 상태를 '중지' (set) 상태로 명확히 설정 >>>
        self.stop_event.set()

        # ... (폴더 생성, AudioRecorder 초기화 등은 동일) ...
        if not os.path.exists("results"):
            try: os.makedirs("results"); print("'results' 폴더 생성됨.")
            except OSError as e: print(f"'results' 폴더 생성 실패: {e}")
        self.audio_recorder = AudioRecorder()
        self.recognizer = None
        self.translator = None

        # ... (UI 초기화 try-except 블록은 동일) ...
        try:
            default_device_name = None
            try:
                default_device_info = self.audio_recorder.audio.get_default_input_device_info()
                default_device_name = default_device_info.get('name')
                print(f"기본 입력 장치 확인: {default_device_name}")
            except Exception as e: print(f"기본 오디오 입력 장치 가져오기 실패: {e}")

            self.ui = RealtimeTranslatorUI(
                root,
                start_callback=self.start_recording,
                stop_callback=self.stop_recording,
                get_input_devices=self.audio_recorder.get_input_devices,
                update_labels_callback=self.ui_update_labels,
                default_device_name=default_device_name
            )
        except Exception as e:
             error_msg = f"UI 초기화 중 오류: {e}\n\n{traceback.format_exc()}"
             print(error_msg)
             tk.messagebox.showerror("초기화 오류", f"프로그램 초기화 중 오류가 발생했습니다:\n{e}\n\n로그를 확인하세요.\n프로그램을 종료합니다.")
             if root and root.winfo_exists(): root.destroy()
             return

        # ... (큐, 스레드 변수 초기화, protocol 설정은 동일) ...
        self.text_queue = queue.Queue()
        self.record_thread = None
        self.process_thread = None
        self.update_thread = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    # ... (on_closing, ui_update_labels는 이전 수정과 동일하게 유지) ...
    def on_closing(self):
        print("애플리케이션 종료 중...")
        if not self.stop_event.is_set(): # 시작/진행 중 상태이면
            print("녹음/처리 중지 시도...")
            self.stop_recording()

        threads = [self.record_thread, self.process_thread, self.update_thread]
        active_threads = [t for t in threads if t and t.is_alive()]
        if active_threads:
             print(f"활성 스레드 {len(active_threads)}개 종료 대기...")
             for t in active_threads:
                 try:
                     self.stop_event.set() # 확실히 설정
                     print(f"  {t.name} 스레드 join 대기...")
                     t.join(timeout=2.0)
                     if t.is_alive(): print(f"  경고: {t.name} 스레드가 시간 내에 종료되지 않음.")
                 except Exception as e: print(f"  {t.name} 스레드 join 중 오류: {e}")
        else: print("활성 스레드 없음.")

        if hasattr(self, 'audio_recorder'):
             print("AudioRecorder 스트림 닫기 확인...")
             self.audio_recorder.close_stream()

        if hasattr(self, 'audio_recorder') and self.audio_recorder.audio:
            print("PyAudio 종료 시도...")
            try:
                self.audio_recorder.audio.terminate()
                print("PyAudio 종료됨.")
            except Exception as e: print(f"PyAudio 종료 중 오류 발생: {e}")

        if hasattr(self, 'ui') and self.ui and hasattr(self.ui, 'floating_window') and self.ui.floating_window:
            print("플로팅 윈도우 종료 시도...")
            try:
                if self.ui.floating_window.winfo_exists():
                    self.ui.floating_window.destroy()
                    print("플로팅 윈도우 종료됨.")
            except Exception as e: print(f"플로팅 윈도우 파괴 중 오류: {e}")

        print("리소스 정리 완료. 메인 윈도우 종료.")
        if self.root and self.root.winfo_exists(): self.root.destroy()

    def ui_update_labels(self, event=None):
        # 라벨 업데이트는 녹음 상태와 관계없이 가능하도록 변경 (또는 필요시 조건 재조정)
        if hasattr(self, 'ui') and self.ui:
            try:
                 # 녹음 중이 아닐 때만 레이블 업데이트가 필요하면 이전 조건 사용
                 # if self.stop_event.is_set(): # 중지 상태일 때만
                 self.ui.original_label.config(text=f"원본 ({self.ui.selected_source_language.get()})")
                 self.ui.translated_label.config(text=f"번역 ({self.ui.selected_target_language.get()})")
            except tk.TclError as e:
                 # 창 닫을 때 발생 가능
                 if "application has been destroyed" not in str(e):
                      print(f"ui_update_labels 오류: {e}")
            except Exception as e:
                 print(f"ui_update_labels 오류: {e}")


    # <<< start_recording 조건 수정 >>>
    def start_recording(self):
        """녹음 시작 콜백."""
        # <<< '중지' 상태일 때만 시작 가능하도록 조건 변경 >>>
        if not self.stop_event.is_set():
             # 이 경우는 이미 시작된 상태임
             print("이미 녹음/처리가 진행 중입니다. (stop_event unset)")
             return False

        # '중지' 상태일 때 아래 로직 실행
        # --- 유효성 검사 및 초기화 ---
        selected_device_name = self.ui.selected_device.get()
        source_lang = self.ui.selected_source_language.get()
        target_lang = self.ui.selected_target_language.get()
        if not selected_device_name or "오류" in selected_device_name or "없음" in selected_device_name:
            tk.messagebox.showerror("설정 오류", "유효한 오디오 입력 장치를 선택하세요.")
            return False
        if not source_lang or not target_lang:
            tk.messagebox.showerror("설정 오류", "입력 언어와 번역 언어를 모두 선택하세요.")
            return False
        try:
            devices = self.audio_recorder.get_input_devices()
            device_index = devices.get(selected_device_name)
            if device_index is None:
                 tk.messagebox.showerror("장치 오류", f"선택된 오디오 장치 '{selected_device_name}'를 찾을 수 없습니다.\n장치 목록을 새로고침합니다.")
                 try:
                      new_device_list = list(self.audio_recorder.get_input_devices().keys())
                      if not new_device_list: new_device_list = ["사용 가능한 장치 없음"]
                      self.ui.device_combobox['values'] = new_device_list
                      self.ui.selected_device.set(new_device_list[0])
                      self.ui.device_combobox.config(state="readonly" if "없음" not in new_device_list[0] else "disabled")
                 except Exception as refresh_e: tk.messagebox.showerror("오류", f"장치 목록 새로고침 실패: {refresh_e}")
                 return False
        except Exception as e:
             tk.messagebox.showerror("장치 오류", f"오디오 장치 목록 확인 중 오류: {e}")
             traceback.print_exc()
             return False
        try:
            print(f"Recognizer ({source_lang}) 및 Translator ({source_lang} -> {target_lang}) 초기화 시도...")
            self.recognizer = SpeechRecognizer(source_lang)
            self.translator = TranslatorService(source_lang, target_lang)
            print("초기화 완료.")
        except Exception as e:
            print(f"Recognizer/Translator 초기화 오류: {e}"); traceback.print_exc()
            tk.messagebox.showerror("초기화 오류", f"음성 인식기 또는 번역기 초기화 실패:\n{e}")
            return False
        # --- 초기화 끝 ---

        # <<< 시작 상태로 변경: stop_event 클리어 >>>
        self.stop_event.clear()

        print("녹음 시작...")
        try:
            # 큐 비우기
            while not self.audio_recorder.audio_queue.empty(): self.audio_recorder.audio_queue.get_nowait()
            while not self.text_queue.empty(): self.text_queue.get_nowait()
            print("이전 큐 내용 비움 완료.")

            self.audio_recorder.open_stream(device_index)
            print(f"오디오 스트림 열기 성공 (장치: {selected_device_name}, 인덱스: {device_index})")
        except queue.Empty: pass # 큐 비우기 중 예외는 무시
        except Exception as e:
            print(f"오디오 스트림 열기 실패: {e}"); traceback.print_exc()
            tk.messagebox.showerror("오디오 오류", f"오디오 스트림을 열 수 없습니다:\n{e}")
            self.stop_event.set() # 실패 시 다시 '중지' 상태로
            return False

        # 스레드 시작 (이전 스레드 join 확인)
        threads_to_join = [self.record_thread, self.process_thread, self.update_thread]
        for t in threads_to_join:
             if t and t.is_alive():
                  print(f"이전 {t.name} 스레드 join 시도...")
                  # join 하기 전에 해당 스레드가 stop_event를 인지하도록 set 해주는 것이 좋음
                  temp_stop = threading.Event() # 임시 이벤트로 이전 스레드 종료 시도
                  temp_stop.set()
                  # 이전 스레드가 이 임시 이벤트를 사용했다면 효과가 있겠지만,
                  # 현재 구조에서는 stop_event를 공유하므로 아래 clear 전에 set하면 안됨.
                  # 대신 join 타임아웃으로 처리.
                  t.join(timeout=1.0)

        # 이제 새 스레드를 시작할 것이므로 stop_event 클리어 (이미 위에서 했지만 확인차)
        self.stop_event.clear()

        self.record_thread = threading.Thread(target=self.record_audio, name="AudioRecordThread", daemon=True)
        self.process_thread = threading.Thread(target=self.process_stream, name="ProcessStreamThread", daemon=True)
        self.update_thread = threading.Thread(target=self.update_ui, name="UpdateUIThread", daemon=True)

        self.record_thread.start()
        self.process_thread.start()
        self.update_thread.start()
        print("모든 스레드 시작됨.")
        return True

    # <<< stop_recording 조건 수정 >>>
    def stop_recording(self):
        # <<< '시작/진행 중' 상태일 때만 중지 가능하도록 조건 변경 >>>
        if self.stop_event.is_set():
            # 이 경우는 이미 중지된 상태임
            print("이미 중지되었거나 시작되지 않았습니다. (stop_event set)")
            return

        # '시작/진행 중' 상태일 때 아래 로직 실행
        print("녹음/처리 중지 요청...")
        # <<< 중지 상태로 변경: stop_event 설정 >>>
        self.stop_event.set()

        # ... (AudioRecorder.stop(), 큐에 None 추가 등 동일) ...
        print("AudioRecorder.stop() 호출 (스트림 닫기)...")
        self.audio_recorder.stop()
        print("AudioRecorder.stop() 완료.")
        print("큐에 종료 신호(None) 추가 시도...")
        try:
            self.audio_recorder.audio_queue.put(None, block=False)
            self.text_queue.put((None, None, None), block=False)
        except queue.Full: print("경고: 큐가 가득 차 종료 신호를 넣지 못했습니다.")

        print("중지 신호 전송 및 리소스 정리 시도 완료.")


    # ... (record_audio, _audio_generator, process_stream, update_ui는 이전 수정과 동일하게 유지) ...
    # 해당 스레드들은 루프 조건에서 stop_event.is_set()을 올바르게 사용하고 있음
    def record_audio(self):
        """오디오 녹음 스레드"""
        print("record_audio 스레드 시작")
        # stop_event를 record 메서드에 전달
        try:
            # AudioRecorder.record가 stop_event를 인자로 받도록 수정됨을 가정
            self.audio_recorder.record(self.stop_event)
        except Exception as e:
            if not self.stop_event.is_set(): # 종료 중이 아닐 때만 오류 처리
                print(f"record_audio 스레드 오류: {e}")
                traceback.print_exc()
                self.root.after(0, lambda: self.ui.status_label.config(text="녹음 오류", fg="red"))
                self.stop_event.set() # 오류 시 종료 상태로
                # UI 버튼 상태도 변경 필요
                self.root.after(0, self.ui.toggle_recording) # 토글 호출하여 버튼 상태 맞추기
        finally:
             # stop_event 상태와 관계없이 루프 종료 시 로그 남김
            print(f"record_audio 스레드 종료 (stop_event: {self.stop_event.is_set()})")

    def _audio_generator(self):
        """오디오 큐에서 데이터를 읽어 스트리밍 API로 보낼 제너레이터"""
        print("_audio_generator 시작")
        while not self.stop_event.is_set():
            try:
                chunk = self.audio_recorder.audio_queue.get(block=True, timeout=0.1)
                if chunk is None:
                    print("_audio_generator: None 수신, 종료.")
                    break
                yield chunk
                self.audio_recorder.audio_queue.task_done()
            except queue.Empty:
                if self.stop_event.is_set():
                     print("_audio_generator: 중지 이벤트 확인 및 큐 비어있음, 종료.")
                     break
                continue
            except Exception as e:
                 print(f"_audio_generator 오류: {e}")
                 traceback.print_exc()
                 break
        print("_audio_generator 종료 - None 반환")
        yield None # 스트림 종료 알림

    def process_stream(self):
        """오디오 스트림 처리: 인식 -> 번역 -> 큐 저장"""
        print("process_stream 스레드 시작")
        if not self.recognizer or not self.translator:
             print("오류: Recognizer 또는 Translator가 초기화되지 않음.")
             if self.ui and self.root and self.root.winfo_exists():
                  self.root.after(0, lambda: self.ui.status_label.config(text="초기화 오류", fg="red"))
             return

        stream_active = True
        responses = None # 초기화
        try:
            audio_gen = self._audio_generator()
            print("StreamingRecognize 요청 시작...")
            responses = self.recognizer.start_streaming_recognize(audio_gen)

            if responses is None:
                 print("스트리밍 인식 시작 실패, process_stream 종료")
                 stream_active = False
                 if self.ui and self.root and self.root.winfo_exists():
                      self.root.after(0, lambda: self.ui.status_label.config(text="인식 오류", fg="red"))
                 return

            print("Streaming API 응답 처리 루프 시작...")
            for response in responses:
                if self.stop_event.is_set():
                    print("process_stream: 중지 이벤트 확인, 응답 처리 중단.")
                    stream_active = False
                    break

                if not response.results: continue
                result = response.results[0]
                if not result.alternatives: continue
                transcript = result.alternatives[0].transcript.strip()
                is_final = result.is_final

                if transcript:
                    try:
                        translated_text = self.translator.translate_text(transcript)
                        if translated_text is None: translated_text = "[번역 실패]"
                        if self.stop_event.is_set(): break
                        self.text_queue.put((transcript, translated_text, is_final))

                        if is_final:
                             if self.stop_event.is_set(): break
                             try:
                                with open(ORIGINAL_FILE, 'a', encoding='utf-8') as f_org, \
                                     open(TRANSLATED_FILE, 'a', encoding='utf-8') as f_tr:
                                    f_org.write(transcript + '\n')
                                    f_tr.write(translated_text + '\n')
                             except Exception as e: print(f"    [오류] 최종 결과 파일 쓰기 오류: {e}")
                    except Exception as e:
                         if not self.stop_event.is_set():
                              print(f"  [오류] 번역 중 오류 발생 (텍스트: '{transcript}'): {e}")
                              traceback.print_exc()
                              self.text_queue.put((transcript, "[번역 오류]", is_final))
                         else: break

            if not self.stop_event.is_set():
                print("Streaming API 응답 처리 루프 정상 종료.")

        except OutOfRange as e:
             print(f"process_stream: Google API 스트리밍 세션 종료됨 (OutOfRange): {e}")
             stream_active = False
             if not self.stop_event.is_set():
                 if self.ui and self.root and self.root.winfo_exists():
                     self.root.after(0, lambda: tk.messagebox.showwarning("연결 종료", "실시간 인식/번역 세션이 종료되었습니다.\n(Google API 타임아웃 등)\n\n다시 시작해주세요."))
                     self.stop_event.set()
                     self.root.after(0, self.ui.toggle_recording)
        except Exception as e:
            if not self.stop_event.is_set():
                print(f"process_stream 스레드에서 예외 발생: {e}")
                traceback.print_exc()
                stream_active = False
                if self.ui and self.root and self.root.winfo_exists():
                      self.root.after(0, lambda: self.ui.status_label.config(text="처리 오류", fg="red"))
                self.stop_event.set()
                self.root.after(0, self.ui.toggle_recording)
        finally:
            # API 스트림을 명시적으로 닫는 로직 추가 (필요한 경우)
            # Google Cloud Speech API의 경우 response iterator를 다 소모하거나
            # generator가 None을 yield하면 자동으로 닫히는 경향이 있음.
            # 명시적 close가 필요하다면 API 문서 확인 필요.
            # if responses and hasattr(responses, 'close'):
            #    try: responses.close(); print("API 응답 스트림 닫기 시도")
            #    except: pass
            print(f"process_stream 스레드 종료 (stream_active: {stream_active}, stop_event: {self.stop_event.is_set()})")


    def update_ui(self):
        """큐에서 결과를 가져와 UI 업데이트"""
        print("update_ui 스레드 시작")
        while True:
            try:
                original, translated, is_final = self.text_queue.get(block=True, timeout=0.1)

                if original is None:
                     print("update_ui: None 수신, 종료.")
                     break

                # <<< UI 업데이트 전에 stop_event 확인 >>>
                if self.stop_event.is_set():
                     print("update_ui: 중지 이벤트 확인, 업데이트 건너뛰고 종료 시도.")
                     # 남아있는 task done 처리
                     self.text_queue.task_done()
                     break

                if self.ui and self.root and self.root.winfo_exists():
                    self.root.after(0, self.ui.update_labels, original, translated, is_final)
                else:
                     print("UI 업데이트 스킵: UI 또는 root 윈도우 없음. 스레드 종료.")
                     break

                self.text_queue.task_done()

            except queue.Empty:
                if self.stop_event.is_set():
                    print("update_ui: 중지 이벤트 확인 및 큐 비어있음, 종료.")
                    break
                continue
            except Exception as e:
                print(f"update_ui 스레드 오류: {e}")
                traceback.print_exc()
                break
        print("update_ui 스레드 종료")


# ... (if __name__ == "__main__": 부분은 동일하게 유지) ...
if __name__ == "__main__":
    try:
        root = tk.Tk()
        try: # DPI Awareness
             from ctypes import windll
             windll.shcore.SetProcessDpiAwareness(1)
             print("DPI Awareness 설정됨 (Windows).")
        except: pass

        app = RealtimeTranslatorApp(root)

        if app and hasattr(app, 'ui') and app.ui and root.winfo_exists():
            print("애플리케이션 UI 시작...")
            root.mainloop()
            print("애플리케이션 UI 종료됨.")
        else:
             print("애플리케이션 초기화 실패. 프로그램을 종료합니다.")
             if 'root' in locals() and root and root.winfo_exists():
                 root.destroy()
    except Exception as e:
         print(f"애플리케이션 실행 중 최상위 오류: {e}")
         traceback.print_exc()
         try:
             if 'root' in locals() and root and root.winfo_exists():
                 root.destroy()
         except: pass
