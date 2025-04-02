# audio_recorder.py
import traceback
import pyaudio
import queue
from config import AUDIO_FORMAT, CHANNELS, RATE, CHUNK
import threading # threading 임포트 추가

class AudioRecorder:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_queue = queue.Queue()
        # self._is_recording_func = None # 제거 (record 메서드에서 직접 이벤트 사용)

    # ... (get_input_devices, open_stream, close_stream 메서드는 동일) ...
    def get_input_devices(self):
        """사용 가능한 오디오 입력 장치 목록 반환"""
        devices = {}
        try:
            info = self.audio.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount', 0) # 기본값 추가
            for i in range(num_devices):
                try:
                    device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
                    if device_info.get('maxInputChannels', 0) > 0: # 기본값 추가
                        devices[f"{device_info.get('name')}"] = i
                except Exception as e:
                    print(f"장치 정보 조회 오류 (인덱스 {i}): {e}") # 개별 장치 오류 로깅
        except Exception as e:
            print(f"오디오 호스트 API 정보 조회 오류: {e}") # API 자체 오류 로깅
        return devices

    def open_stream(self, device_index=None):
        """선택한 오디오 입력 장치를 사용하여 스트림 열기"""
        if self.stream:
            self.close_stream()

        try:
            self.stream = self.audio.open(
                format=AUDIO_FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK,
            )
            print("오디오 스트림 열림")
        except Exception as e:
             print(f"오디오 스트림 열기 중 오류: {e}")
             self.stream = None # 오류 시 스트림 None으로 설정
             raise # 오류를 다시 발생시켜 호출자에게 알림

    def close_stream(self):
        """스트림 닫기"""
        if self.stream:
            try:
                if self.stream.is_active(): # 활성화 상태일 때만 stop 호출
                     self.stream.stop_stream()
                self.stream.close()
                print("오디오 스트림 닫힘")
            except Exception as e:
                 # 이미 닫혔거나 다른 문제 발생 시 오류 로깅
                 print(f"오디오 스트림 닫기 중 오류: {e}")
            finally:
                 self.stream = None # 상태 확실히 업데이트

        # 큐 비우기 (선택적이지만 재시작 시 도움됨)
        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except queue.Empty: break
            except Exception: break # 예외 발생 시 중단

    # <<< record 메서드 수정: threading.Event 직접 사용 >>>
    def record(self, stop_event: threading.Event):
        """
        stop_event가 설정될 때까지 오디오 청크를 지속적으로 읽어 큐에 넣습니다.
        """
        if not self.stream or not self.stream.is_active():
             print("녹음 시작 불가: 스트림이 열려있지 않거나 활성 상태가 아님")
             return

        print("오디오 녹음 루프 시작 (stop_event 기반)")
        while not stop_event.is_set():
            try:
                # 스트림 존재 및 활성 상태 재확인 (중간에 닫힐 수 있음)
                if not self.stream or not self.stream.is_active():
                    if not stop_event.is_set(): # 의도치 않은 종료
                         print("녹음 중 스트림 비활성화 감지됨. 루프 종료.")
                    break

                # exception_on_overflow=False: 오버플로우 시 예외 대신 데이터 드롭
                data = self.stream.read(CHUNK, exception_on_overflow=False)

                # stop_event가 설정되지 않았을 때만 큐에 데이터 추가
                if data and not stop_event.is_set():
                    self.audio_queue.put(data)

            except IOError as e:
                # 스트림 관련 IO 오류 처리
                if stop_event.is_set():
                     # 종료 중 발생한 IO 오류는 예상 가능 (스트림 닫힘)
                     print(f"record: IO 오류 발생 (예상된 종료) - {e}")
                else:
                     # 예기치 않은 IO 오류
                     print(f"record: 오디오 읽기 중 IO 오류 발생 - {e}")
                break # IO 오류 시 루프 종료
            except Exception as e:
                # 기타 예외 처리
                if not stop_event.is_set():
                     print(f"record: 녹음 중 예기치 않은 오류 발생 - {e}")
                     traceback.print_exc()
                break # 예외 발생 시 루프 종료
        print("오디오 녹음 루프 종료")

    def stop(self):
        """스트림 중지 및 닫기 (PyAudio 종료는 포함 안 함)"""
        self.close_stream()

    # <<< __del__ 수정: PyAudio 종료 로직 제거 >>>
    def __del__(self):
        # 객체 소멸 시 스트림이 남아있다면 닫기 시도
        if self.stream:
            print("객체 소멸자: 남아있는 오디오 스트림 닫기 시도...")
            self.close_stream()
        # PyAudio 종료는 메인 앱에서 관리하므로 여기서 호출하지 않음
        # if self.audio:
        #     # self.audio.terminate() # 제거
        #     print("PyAudio 종료는 메인 앱에서 처리")
        pass # 특별히 할 일 없음