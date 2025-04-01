# main.py (or your main script)
import threading
import queue
import tkinter as tk
import tkinter.messagebox # 메시지 박스 추가
import traceback
import time # time 모듈 추가
from google.api_core.exceptions import OutOfRange # API 타임아웃 관련 예외
from config import ORIGINAL_FILE, TRANSLATED_FILE
from audio_recorder import AudioRecorder
from speech_recognizer import SpeechRecognizer
from translator_service import TranslatorService
from ui import RealtimeTranslatorUI

class RealtimeTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.is_recording = False
        self.audio_recorder = AudioRecorder()
        self.recognizer = None
        self.translator = None

        try:
            self.ui = RealtimeTranslatorUI(
                root,
                start_callback=self.start_recording,
                stop_callback=self.stop_recording,
                get_input_devices=self.audio_recorder.get_input_devices,
                update_labels_callback=self.ui_update_labels
            )
        except Exception as e:
             print(f"UI 초기화 중 오류: {e}")
             traceback.print_exc()
             tk.messagebox.showerror("초기화 오류", f"프로그램 초기화 중 오류가 발생했습니다:\n{e}\n\n프로그램을 종료합니다.")
             root.destroy()
             return # 앱 초기화 중단

        # 텍스트 큐: (original, translated, is_final) 튜플 저장
        self.text_queue = queue.Queue()
        self.record_thread = None
        self.process_thread = None
        self.update_thread = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """앱 종료 시 호출될 함수"""
        print("애플리케이션 종료 중...")
        if self.is_recording:
            # tk.messagebox 대신 print 사용 (UI 스레드 아닐 수 있음)
            print("녹음 중지 시도...")
            self.stop_recording()

        # 스레드 종료 대기 (짧은 타임아웃)
        threads = [self.record_thread, self.process_thread, self.update_thread]
        for t in threads:
            if t and t.is_alive():
                try:
                    print(f"{t.name} 스레드 종료 대기...")
                    t.join(timeout=1.5)
                except Exception as e:
                    print(f"{t.name} 스레드 join 중 오류: {e}")

        # AudioRecorder 리소스 정리
        if hasattr(self, 'audio_recorder'):
             self.audio_recorder.stop()

        print("리소스 정리 완료. 애플리케이션 종료.")
        if self.root and self.root.winfo_exists():
             self.root.destroy()

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
        if source_lang == target_lang:
            tk.messagebox.showwarning("설정 경고", "입력 언어와 번역 언어가 동일합니다.")
            # 계속 진행할 수도 있음

        try:
            devices = self.audio_recorder.get_input_devices()
            device_index = devices.get(selected_device_name)
            if device_index is None:
                 tk.messagebox.showerror("장치 오류", f"선택된 오디오 장치 '{selected_device_name}'를 찾을 수 없습니다.")
                 return False
        except Exception as e:
             tk.messagebox.showerror("장치 오류", f"오디오 장치 목록 확인 중 오류: {e}")
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
            print("오디오 스트림 열기 성공.")
        except Exception as e:
            print(f"오디오 스트림 열기 실패: {e}")
            tk.messagebox.showerror("오디오 오류", f"오디오 스트림을 열 수 없습니다:\n{e}")
            self.is_recording = False
            return False # 시작 실패

        # 스레드 시작
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
        self.is_recording = False # 플래그 먼저 설정

        # 오디오 녹음 중단 및 스트림 닫기
        self.audio_recorder.stop()
        print("오디오 스트림 중지/닫힘.")

        # 큐에 종료 신호 추가 (선택적, _audio_generator가 is_recording으로 종료됨)
        # self.audio_recorder.audio_queue.put(None)

        # process_stream 스레드가 API 응답 대기를 마치고 종료하도록 함
        # update_ui 스레드가 큐를 비우고 종료하도록 함
        print("녹음 중지됨.")


    def record_audio(self):
        """오디오 녹음 스레드"""
        print("record_audio 스레드 시작")
        try:
            self.audio_recorder.record(lambda: self.is_recording)
        except Exception as e:
            print(f"record_audio 스레드 오류: {e}")
            traceback.print_exc()
        finally:
            # 스레드 종료 시 audio_queue에 None을 넣어 process_stream 종료 유도
            # self.audio_recorder.audio_queue.put(None) # _audio_generator에서 처리하므로 필요 없을 수 있음
            print("record_audio 스레드 종료")


    def _audio_generator(self):
        """오디오 큐에서 데이터를 읽어 스트리밍 API로 보낼 제너레이터"""
        while self.is_recording or not self.audio_recorder.audio_queue.empty():
            try:
                chunk = self.audio_recorder.audio_queue.get(block=True, timeout=0.1) # 블로킹 및 타임아웃
                if chunk is None: # 종료 신호 (현재 사용 안 함)
                    print("_audio_generator: None 수신, 종료.")
                    break
                yield chunk
                self.audio_recorder.audio_queue.task_done()
            except queue.Empty:
                if not self.is_recording:
                    print("_audio_generator: 녹음 중지 및 큐 비어있음, 종료.")
                    break # 녹음 중지되었고 큐 비었으면 종료
                else:
                    continue # 녹음 중이면 계속 대기
            except Exception as e:
                 print(f"_audio_generator 오류: {e}")
                 break
        print("_audio_generator 종료")


    def process_stream(self):
        """오디오 스트림 처리: 인식 -> 번역 -> 큐 저장"""
        print("process_stream 스레드 시작")
        if not self.recognizer or not self.translator:
             print("오류: Recognizer 또는 Translator가 초기화되지 않음.")
             return

        try:
            audio_gen = self._audio_generator()
            responses = self.recognizer.start_streaming_recognize(audio_gen)

            if responses is None:
                 print("스트리밍 인식 시작 실패, process_stream 종료")
                 # UI에 오류 상태 표시 고려
                 if self.ui and self.root and self.root.winfo_exists():
                      self.root.after(0, lambda: self.ui.status_label.config(text="인식 오류", fg="red"))
                 return

            print("Streaming API 응답 처리 시작...")
            for response in responses:
                 # 녹음 중지 시 빠르게 루프 탈출 시도
                if not self.is_recording and self.audio_recorder.audio_queue.empty():
                     print("process_stream: 녹음 중지됨, 응답 처리 중단.")
                     break

                if not response.results:
                    continue

                result = response.results[0]
                if not result.alternatives:
                    continue

                transcript = result.alternatives[0].transcript.strip()
                is_final = result.is_final

                # 중간 결과 또는 최종 결과 모두 처리
                if transcript: # 빈 텍스트는 무시
                    # print(f"인식 {'(최종)' if is_final else '(중간)'}: {transcript}") # 로그 상세하게
                    try:
                        translated_text = self.translator.translate_text(transcript)
                        # UI 업데이트 큐에 (original, translated, is_final) 추가
                        self.text_queue.put((transcript, translated_text, is_final))
                        # print(f"번역 결과: {translated_text}")

                        # 최종 결과만 파일에 저장 (선택적)
                        if is_final:
                             try:
                                with open(ORIGINAL_FILE, 'a', encoding='utf-8') as f_org, \
                                     open(TRANSLATED_FILE, 'a', encoding='utf-8') as f_tr:
                                    f_org.write(transcript + '\n')
                                    f_tr.write(translated_text + '\n')
                             except Exception as e:
                                 print(f"최종 결과 파일 쓰기 오류: {e}")

                    except Exception as e:
                         print(f"번역 중 오류 발생 (텍스트: '{transcript}'): {e}")
                         # 번역 실패 시 오류 메시지 큐에 넣기 (선택적)
                         # self.text_queue.put((transcript, "[번역 오류]", is_final))

        except OutOfRange as e:
             # Google API 스트리밍 타임아웃 (보통 305초)
             print(f"process_stream: Google API 스트리밍 타임아웃 또는 종료됨: {e}")
             # 사용자에게 알림
             if self.ui and self.root and self.root.winfo_exists():
                 self.root.after(0, lambda: tk.messagebox.showwarning("연결 종료", "실시간 인식/번역 세션이 종료되었습니다. 다시 시작해주세요."))
                 # 자동으로 중지 상태로 변경
                 self.root.after(0, self.ui.toggle_recording) # 토글 함수 호출하여 상태 변경
        except Exception as e:
            print(f"process_stream 스레드에서 예외 발생: {e}")
            traceback.print_exc()
            # UI에 오류 상태 표시 고려
            if self.ui and self.root and self.root.winfo_exists():
                  self.root.after(0, lambda: self.ui.status_label.config(text="처리 오류", fg="red"))
        finally:
            print("process_stream 스레드 종료")
            # 스레드 종료 시 is_recording 상태에 따라 UI 상태 업데이트 필요할 수 있음
            # 예를 들어, 오류로 종료 시 stop_recording 호출 등


    def update_ui(self):
        """큐에서 결과를 가져와 UI 업데이트"""
        print("update_ui 스레드 시작")
        while True: # is_recording 조건 제거, 큐에 항목이 있으면 계속 처리
            try:
                # 큐에서 결과 가져오기 (타임아웃)
                # 녹음 중지 후 남은 항목 처리를 위해 block=True 유지, 타임아웃 짧게
                original, translated, is_final = self.text_queue.get(block=True, timeout=0.2)

                if self.ui and self.root and self.root.winfo_exists():
                    # 메인 스레드에서 UI 업데이트 예약
                    self.root.after(0, self.ui.update_labels, original, translated, is_final)
                else:
                     print("UI 업데이트 스킵: UI 또는 root 윈도우 없음. 스레드 종료.")
                     break # UI 없으면 종료

                self.text_queue.task_done()

            except queue.Empty:
                # 큐가 비어있고 녹음이 중지되었으면 스레드 종료
                if not self.is_recording:
                    print("update_ui: 큐 비어있고 녹음 중지됨, 종료.")
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
        except ImportError:
             pass # Windows 아니거나 ctypes 없으면 무시
        except AttributeError:
             print("이 Windows 버전에서는 SetProcessDpiAwareness 지원 안 함.")
        except Exception as e:
             print(f"DPI 설정 중 오류: {e}")

        app = RealtimeTranslatorApp(root)
        if app and hasattr(app, 'ui'): # app 객체 생성 확인
            print("애플리케이션 UI 시작...")
            root.mainloop()
        else:
             print("애플리케이션 초기화 실패.")
             if root and root.winfo_exists():
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