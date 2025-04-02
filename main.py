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
        self.is_recording = False

        if not os.path.exists("results"):
            try:
                os.makedirs("results")
                print("'results' 폴더 생성됨.")
            except OSError as e:
                 print(f"'results' 폴더 생성 실패: {e}")

        # <<< AudioRecorder 초기화를 UI 생성 *전*으로 이동 >>>
        self.audio_recorder = AudioRecorder()
        self.recognizer = None
        self.translator = None

        try:
            # <<< 기본 장치 이름을 UI 생성 전에 가져오기 >>>
            default_device_name = None
            try:
                # audio_recorder 인스턴스를 사용하여 기본 장치 정보 가져오기
                default_device_info = self.audio_recorder.audio.get_default_input_device_info()
                default_device_name = default_device_info.get('name')
                print(f"기본 입력 장치 확인: {default_device_name}")
            except Exception as e:
                print(f"기본 오디오 입력 장치 가져오기 실패: {e}")
                # 오류 발생 시 default_device_name은 None 유지

            # <<< UI 생성자에 default_device_name 전달 >>>
            self.ui = RealtimeTranslatorUI(
                root,
                start_callback=self.start_recording,
                stop_callback=self.stop_recording,
                get_input_devices=self.audio_recorder.get_input_devices, # 이 콜백은 여전히 필요
                update_labels_callback=self.ui_update_labels,
                default_device_name=default_device_name # 기본 장치 이름 전달
            )
        except Exception as e:
             # 에러 메시지에 스택 트레이스 포함
             error_msg = f"UI 초기화 중 오류: {e}\n\n{traceback.format_exc()}"
             print(error_msg)
             tk.messagebox.showerror("초기화 오류", f"프로그램 초기화 중 오류가 발생했습니다:\n{e}\n\n로그를 확인하세요.\n프로그램을 종료합니다.")
             # 오류 발생 시 안전하게 root 파괴
             if root and root.winfo_exists():
                  root.destroy()
             return # 앱 초기화 중단

        # 텍스트 큐, 스레드 등 나머지 초기화는 동일
        self.text_queue = queue.Queue()
        self.record_thread = None
        self.process_thread = None
        self.update_thread = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # <<< on_closing 메서드 수정 >>>
    def on_closing(self):
        """앱 종료 시 호출될 함수"""
        print("애플리케이션 종료 중...")
        if self.is_recording:
            print("녹음 중지 시도...")
            self.stop_recording() # 녹음 중지

        # 스레드 종료 대기 (짧은 타임아웃)
        threads = [self.record_thread, self.process_thread, self.update_thread]
        active_threads = [t for t in threads if t and t.is_alive()]
        if active_threads:
             print(f"활성 스레드 {len(active_threads)}개 종료 대기...")
             for t in active_threads:
                 try:
                     print(f"  {t.name} 스레드 종료 대기...")
                     t.join(timeout=1.0) # 타임아웃 줄임
                     if t.is_alive():
                          print(f"  경고: {t.name} 스레드가 시간 내에 종료되지 않음.")
                 except Exception as e:
                     print(f"  {t.name} 스레드 join 중 오류: {e}")
        else:
             print("활성 스레드 없음.")


        # AudioRecorder 리소스 정리
        if hasattr(self, 'audio_recorder'):
             print("AudioRecorder 리소스 정리 시도...")
             self.audio_recorder.stop() # 스트림 닫기 및 PyAudio 종료 유도

        # <<< 플로팅 윈도우 종료 추가 >>>
        if hasattr(self, 'ui') and self.ui and hasattr(self.ui, 'floating_window') and self.ui.floating_window:
            print("플로팅 윈도우 종료 시도...")
            try:
                if self.ui.floating_window.winfo_exists():
                    self.ui.floating_window.destroy()
                    print("플로팅 윈도우 종료됨.")
            except Exception as e:
                print(f"플로팅 윈도우 파괴 중 오류: {e}")

        print("리소스 정리 완료. 메인 윈도우 종료.")
        if self.root and self.root.winfo_exists():
             self.root.destroy()

    # ... (ui_update_labels, start_recording, stop_recording, record_audio, _audio_generator, process_stream, update_ui 메서드는 이전과 동일) ...
    def ui_update_labels(self, event=None):
        """언어 선택 변경 시 레이블 업데이트"""
        if not self.is_recording and hasattr(self, 'ui') and self.ui:
             self.ui.original_label.config(text=f"원본 ({self.ui.selected_source_language.get()})")
             self.ui.translated_label.config(text=f"번역 ({self.ui.selected_target_language.get()})")

    def start_recording(self):
        """녹음 시작 콜백. 성공 시 True, 실패 시 False 반환"""
        if self.is_recording:
            print("이미 녹음이 진행 중입니다.")
            return False # 이미 시작됨

        # 장치/언어 선택 유효성 검사
        selected_device_name = self.ui.selected_device.get()
        source_lang = self.ui.selected_source_language.get()
        target_lang = self.ui.selected_target_language.get()

        if not selected_device_name or "오류" in selected_device_name or "없음" in selected_device_name:
            tk.messagebox.showerror("설정 오류", "유효한 오디오 입력 장치를 선택하세요.")
            return False
        if not source_lang or not target_lang:
            tk.messagebox.showerror("설정 오류", "입력 언어와 번역 언어를 모두 선택하세요.")
            return False
        # 입력/번역 언어 동일 경고 (원하면 주석 해제)
        # if source_lang == target_lang:
        #     tk.messagebox.showwarning("설정 경고", "입력 언어와 번역 언어가 동일합니다.")

        try:
            devices = self.audio_recorder.get_input_devices()
            device_index = devices.get(selected_device_name)
            if device_index is None:
                 # 선택된 장치를 찾을 수 없을 때 사용자에게 알리고 장치 목록 새로고침 시도
                 tk.messagebox.showerror("장치 오류", f"선택된 오디오 장치 '{selected_device_name}'를 찾을 수 없습니다.\n장치 목록을 새로고침합니다.")
                 # UI의 장치 콤보박스 업데이트
                 try:
                      new_device_list = list(self.audio_recorder.get_input_devices().keys())
                      if not new_device_list: new_device_list = ["사용 가능한 장치 없음"]
                      self.ui.device_combobox['values'] = new_device_list
                      self.ui.selected_device.set(new_device_list[0]) # 첫번째 장치로 리셋
                      self.ui.device_combobox.config(state="readonly" if "없음" not in new_device_list[0] else "disabled")
                 except Exception as refresh_e:
                      tk.messagebox.showerror("오류", f"장치 목록 새로고침 실패: {refresh_e}")
                 return False # 시작 실패
        except Exception as e:
             tk.messagebox.showerror("장치 오류", f"오디오 장치 목록 확인 중 오류: {e}")
             traceback.print_exc()
             return False

        # Recognizer 및 Translator 초기화
        try:
            print(f"Recognizer ({source_lang}) 및 Translator ({source_lang} -> {target_lang}) 초기화 시도...")
            self.recognizer = SpeechRecognizer(source_lang)
            self.translator = TranslatorService(source_lang, target_lang)
            print("초기화 완료.")
        except Exception as e:
            print(f"Recognizer/Translator 초기화 오류: {e}")
            traceback.print_exc()
            tk.messagebox.showerror("초기화 오류", f"음성 인식기 또는 번역기 초기화 실패:\n{e}")
            return False

        self.is_recording = True
        print("녹음 시작...")

        try:
            self.audio_recorder.open_stream(device_index)
            print(f"오디오 스트림 열기 성공 (장치: {selected_device_name}, 인덱스: {device_index})")
        except Exception as e:
            print(f"오디오 스트림 열기 실패: {e}")
            traceback.print_exc()
            tk.messagebox.showerror("오디오 오류", f"오디오 스트림을 열 수 없습니다:\n{e}")
            self.is_recording = False
            return False # 시작 실패

        # 스레드 시작
        # 기존 스레드가 살아있으면 join 시도 (이전 실행 정리)
        threads_to_join = [self.record_thread, self.process_thread, self.update_thread]
        for t in threads_to_join:
             if t and t.is_alive():
                  print(f"이전 {t.name} 스레드 join 시도...")
                  t.join(timeout=0.5)

        # 스레드 새로 생성 및 시작
        self.record_thread = threading.Thread(target=self.record_audio, name="AudioRecordThread", daemon=True)
        self.process_thread = threading.Thread(target=self.process_stream, name="ProcessStreamThread", daemon=True)
        self.update_thread = threading.Thread(target=self.update_ui, name="UpdateUIThread", daemon=True)

        self.record_thread.start()
        self.process_thread.start()
        self.update_thread.start()
        print("모든 스레드 시작됨.")
        return True # 시작 성공

    def stop_recording(self):
        if not self.is_recording:
            print("녹음이 시작되지 않았습니다.")
            return

        print("녹음 중지 요청...")
        self.is_recording = False # 플래그 먼저 설정 (스레드 루프 종료 유도)

        # 오디오 녹음 중단 및 스트림 닫기 (AudioRecorder 내부에서 처리)
        print("AudioRecorder.stop() 호출...")
        self.audio_recorder.stop()
        print("AudioRecorder.stop() 완료.")

        # 큐 비우기 (선택적, 스레드 종료를 위해)
        print("오디오 큐 비우기 시도...")
        while not self.audio_recorder.audio_queue.empty():
            try:
                self.audio_recorder.audio_queue.get_nowait()
            except queue.Empty:
                break
            except Exception as e:
                 print(f"큐 비우기 중 오류: {e}")
                 break
        print("오디오 큐 비우기 완료.")

        # process_stream 스레드가 API 응답 대기를 마치고 종료하도록 함
        # update_ui 스레드가 큐를 비우고 종료하도록 함 (is_recording 플래그와 큐 상태 확인)
        print("녹음 관련 작업 중지됨.")


    def record_audio(self):
        """오디오 녹음 스레드"""
        print("record_audio 스레드 시작")
        try:
            # is_recording 플래그를 콜백으로 전달하여 녹음 루프 제어
            self.audio_recorder.record(lambda: self.is_recording)
        except Exception as e:
            print(f"record_audio 스레드 오류: {e}")
            traceback.print_exc()
            # 오류 발생 시 녹음 중지 상태로 전환 시도
            if self.is_recording:
                 self.root.after(0, self.ui.toggle_recording) # UI 스레드에서 토글 호출
        finally:
            print("record_audio 스레드 종료")


    def _audio_generator(self):
        """오디오 큐에서 데이터를 읽어 스트리밍 API로 보낼 제너레이터"""
        print("_audio_generator 시작")
        while self.is_recording or not self.audio_recorder.audio_queue.empty():
            try:
                chunk = self.audio_recorder.audio_queue.get(block=True, timeout=0.1)
                if chunk is None: # 종료 신호 (현재 로직에선 사용 안 함)
                     # print("_audio_generator: None 수신, 종료.")
                     break
                # print(f"Yielding chunk: {len(chunk)} bytes") # 데이터 흐름 확인용 로그
                yield chunk
                self.audio_recorder.audio_queue.task_done()
            except queue.Empty:
                if not self.is_recording:
                    # print("_audio_generator: 녹음 중지 및 큐 비어있음, 종료.")
                    break # 녹음 중지되었고 큐 비었으면 종료
                else:
                    continue # 녹음 중이면 계속 대기
            except Exception as e:
                 print(f"_audio_generator 오류: {e}")
                 traceback.print_exc()
                 break
        print("_audio_generator 종료")


    def process_stream(self):
        """오디오 스트림 처리: 인식 -> 번역 -> 큐 저장"""
        print("process_stream 스레드 시작")
        if not self.recognizer or not self.translator:
             print("오류: Recognizer 또는 Translator가 초기화되지 않음.")
             self.root.after(0, lambda: self.ui.status_label.config(text="초기화 오류", fg="red"))
             return

        stream_active = True # 스트림 상태 플래그

        try:
            audio_gen = self._audio_generator()
            print("StreamingRecognize 요청 시작...")
            responses = self.recognizer.start_streaming_recognize(audio_gen)

            if responses is None:
                 print("스트리밍 인식 시작 실패, process_stream 종료")
                 if self.ui and self.root and self.root.winfo_exists():
                      self.root.after(0, lambda: self.ui.status_label.config(text="인식 오류", fg="red"))
                 return

            print("Streaming API 응답 처리 루프 시작...")
            last_response_time = time.time()
            MAX_IDLE_TIME = 10 # 10초간 응답 없으면 경고 (디버깅용)

            for response in responses:
                current_time = time.time()
                # 응답 간 시간 체크 (디버깅)
                # if current_time - last_response_time > 1.0:
                #      print(f"  ({current_time - last_response_time:.2f}초 만에 응답 수신)")
                last_response_time = current_time

                # 녹음 중지 시 빠르게 루프 탈출 시도
                if not self.is_recording:
                     print("process_stream: 녹음 중지 플래그 확인, 응답 처리 중단 시도.")
                     stream_active = False
                     break # 응답 처리 루프 탈출

                if not response.results:
                    # print("  응답에 결과 없음, 계속")
                    continue

                result = response.results[0]
                if not result.alternatives:
                    # print("  결과에 alternative 없음, 계속")
                    continue

                transcript = result.alternatives[0].transcript.strip()
                is_final = result.is_final

                # 중간 결과 또는 최종 결과 모두 처리
                if transcript: # 빈 텍스트는 무시
                    # print(f"  인식 {'(최종)' if is_final else '(중간)'}: '{transcript}'")
                    try:
                        translated_text = self.translator.translate_text(transcript)
                        if translated_text is None: # 번역 실패 시
                             translated_text = "[번역 실패]"
                        # print(f"  번역 결과: '{translated_text}'")
                        # UI 업데이트 큐에 (original, translated, is_final) 추가
                        self.text_queue.put((transcript, translated_text, is_final))

                        # 최종 결과만 파일에 저장
                        if is_final:
                             try:
                                with open(ORIGINAL_FILE, 'a', encoding='utf-8') as f_org, \
                                     open(TRANSLATED_FILE, 'a', encoding='utf-8') as f_tr:
                                    f_org.write(transcript + '\n')
                                    f_tr.write(translated_text + '\n')
                                # print(f"    -> 최종 결과 파일 저장 완료.")
                             except Exception as e:
                                 print(f"    [오류] 최종 결과 파일 쓰기 오류: {e}")

                    except Exception as e:
                         print(f"  [오류] 번역 중 오류 발생 (텍스트: '{transcript}'): {e}")
                         traceback.print_exc()
                         # 번역 실패 시 오류 메시지 큐에 넣기
                         self.text_queue.put((transcript, "[번역 오류]", is_final))
                # else:
                    # print("  빈 transcript 무시")


                # # 일정 시간 응답 없으면 로그 남기기 (디버깅용)
                # if time.time() - last_response_time > MAX_IDLE_TIME:
                #      print(f"경고: {MAX_IDLE_TIME}초 이상 API 응답 없음...")
                #      # 여기서 연결 재시도 로직을 넣을 수도 있음

            print("Streaming API 응답 처리 루프 정상 종료.")

        except OutOfRange as e:
             # Google API 스트리밍 타임아웃 (보통 305초) 또는 정상 종료 시 발생 가능
             print(f"process_stream: Google API 스트리밍 세션 종료됨 (OutOfRange): {e}")
             stream_active = False
             if self.is_recording: # 사용자가 중지하지 않았는데 종료된 경우
                 if self.ui and self.root and self.root.winfo_exists():
                     self.root.after(0, lambda: tk.messagebox.showwarning("연결 종료", "실시간 인식/번역 세션이 종료되었습니다.\n(Google API 타임아웃 또는 네트워크 문제)\n\n다시 시작해주세요."))
                     # 자동으로 중지 상태로 변경 (UI 스레드에서 호출)
                     self.root.after(0, self.ui.toggle_recording)
        except Exception as e:
            print(f"process_stream 스레드에서 예외 발생: {e}")
            traceback.print_exc()
            stream_active = False
            # UI에 오류 상태 표시 고려
            if self.ui and self.root and self.root.winfo_exists():
                  self.root.after(0, lambda: self.ui.status_label.config(text="처리 오류", fg="red"))
            # 오류 발생 시 자동 중지
            if self.is_recording:
                 self.root.after(0, self.ui.toggle_recording)
        finally:
            print(f"process_stream 스레드 종료 (stream_active: {stream_active})")


    def update_ui(self):
        """큐에서 결과를 가져와 UI 업데이트"""
        print("update_ui 스레드 시작")
        while True:
            try:
                # 큐에서 결과 가져오기 (타임아웃 짧게 설정)
                original, translated, is_final = self.text_queue.get(block=True, timeout=0.1)

                if self.ui and self.root and self.root.winfo_exists():
                    # 메인 스레드에서 UI 업데이트 예약
                    # print(f"UI 업데이트 요청: Orig='{original[:20]}...', Trans='{translated[:20]}...', Final={is_final}")
                    self.root.after(0, self.ui.update_labels, original, translated, is_final)
                else:
                     print("UI 업데이트 스킵: UI 또는 root 윈도우 없음. 스레드 종료.")
                     break # UI 없으면 종료

                self.text_queue.task_done()

            except queue.Empty:
                # 큐가 비어있고 녹음이 중지되었으면 스레드 종료
                if not self.is_recording:
                    # print("update_ui: 큐 비어있고 녹음 중지됨, 종료.")
                    break
                # 녹음 중이면 계속 대기
                continue
            except Exception as e:
                print(f"update_ui 스레드 오류: {e}")
                traceback.print_exc()
                break # 오류 시 스레드 종료
        print("update_ui 스레드 종료")


if __name__ == "__main__":
    try:
        root = tk.Tk()
        # DPI 인식 설정 (Windows에서 선명도 향상)
        try:
             from ctypes import windll
             windll.shcore.SetProcessDpiAwareness(1)
             print("DPI Awareness 설정됨 (Windows).")
        except ImportError: pass # Windows 아니거나 ctypes 없으면 무시
        except AttributeError: print("이 Windows 버전에서는 SetProcessDpiAwareness 지원 안 함.")
        except Exception as e: print(f"DPI 설정 중 오류: {e}")

        app = RealtimeTranslatorApp(root)

        # app 객체 및 ui 객체 생성 확인
        if app and hasattr(app, 'ui') and app.ui and root.winfo_exists(): # winfo_exists 추가
            print("애플리케이션 UI 시작...")
            root.mainloop()
            print("애플리케이션 UI 종료됨.")
        else:
             print("애플리케이션 초기화 실패. 프로그램을 종료합니다.")
             # 메인 루프 시작 전에 root가 파괴되었을 수 있으므로 다시 체크
             if 'root' in locals() and root and root.winfo_exists():
                 root.destroy()
    except Exception as e:
         print(f"애플리케이션 실행 중 최상위 오류: {e}")
         traceback.print_exc()
         # 최후의 수단으로 tk 객체 정리 시도
         try:
             if 'root' in locals() and root and root.winfo_exists():
                 root.destroy()
         except:
             pass
