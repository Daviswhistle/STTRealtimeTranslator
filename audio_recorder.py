# audio_recorder.py
import pyaudio
import queue
from config import AUDIO_FORMAT, CHANNELS, RATE, CHUNK

class AudioRecorder:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        # 오디오 청크를 직접 저장할 큐
        self.audio_queue = queue.Queue()
        self._is_recording_func = None # 녹음 상태 확인 함수

    def get_input_devices(self):
        """사용 가능한 오디오 입력 장치 목록 반환"""
        devices = {}
        info = self.audio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        for i in range(num_devices):
            device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
            if device_info.get('maxInputChannels') > 0:
                devices[f"{device_info.get('name')}"] = i
        return devices

    def open_stream(self, device_index=None):
        """선택한 오디오 입력 장치를 사용하여 스트림 열기"""
        if self.stream:
            self.close_stream() # 기존 스트림이 있다면 닫기

        self.stream = self.audio.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK,
            # 스트림 콜백 대신 직접 read 사용
        )
        print("오디오 스트림 열림")

    def close_stream(self):
        """스트림 닫기"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            print("오디오 스트림 닫힘")
        # 큐 비우기 (선택적)
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def record(self, is_recording_func):
        """
        is_recording_func 콜백을 통해 녹음 상태를 판단하며,
        오디오 청크를 지속적으로 읽어 큐에 넣습니다.
        """
        self._is_recording_func = is_recording_func
        while self._is_recording_func():
            try:
                # 스트림이 열려 있는지 확인
                if not self.stream or not self._is_recording_func():
                    break
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                if data and self._is_recording_func():
                    self.audio_queue.put(data) # 바이트 데이터를 직접 큐에 넣음
            except IOError as e:
                # 스트림이 닫혔거나 다른 IO 오류 발생 시 루프 종료
                print(f"오디오 읽기 오류: {e}")
                break
            except Exception as e:
                print(f"녹음 중 예기치 않은 오류: {e}")
                break
        print("오디오 녹음 루프 종료")

    def stop(self):
        """녹음 중지 및 리소스 정리"""
        # self._is_recording_func = lambda: False # 더 이상 녹음하지 않도록 설정 (앱 레벨에서 관리)
        self.close_stream()
        # PyAudio 종료는 앱 종료 시 한 번만 수행하는 것이 좋음
        # self.audio.terminate()

    def __del__(self):
        # 객체 소멸 시 PyAudio 종료
        if self.audio:
            self.audio.terminate()
            print("PyAudio 종료됨")