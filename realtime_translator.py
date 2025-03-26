import os
import time
import threading
import queue
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import pyaudio
import wave
import datetime
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate

# 환경 변수 설정 - Google Cloud 인증 파일 경로
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

class RealtimeTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("실시간 번역 자막 프로그램")
        self.root.geometry("800x600")
        self.root.configure(bg="#f0f0f0")
        
        # 클라이언트 초기화
        self.speech_client = speech.SpeechClient()
        self.translate_client = translate.Client()
        
        # 오디오 설정
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 2048  # 버퍼 크기 증가
        self.record_seconds = 3  # 처리 주기 단축
        
        # 오디오 스트림 및 처리 관련 변수
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()
        
        # 오디오 입력 장치 목록 가져오기
        self.input_devices = self.get_input_devices()
        self.selected_device = tk.StringVar()
        if self.input_devices:
            self.selected_device.set(list(self.input_devices.keys())[0])  # 첫 번째 장치 선택
        
        # 저장할 파일 이름 설정
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.original_file = f"original_text_{self.timestamp}.txt"
        self.translated_file = f"translated_text_{self.timestamp}.txt"
        
        # 언어 설정
        self.languages = {
            "영어 (미국)": "en-US",
            "영어 (영국)": "en-GB",
            "한국어": "ko-KR",
            "일본어": "ja-JP",
            "중국어 (간체)": "zh",
            "중국어 (번체)": "zh-TW",
            "스페인어": "es-ES",
            "프랑스어": "fr-FR",
            "독일어": "de-DE",
            "러시아어": "ru-RU",
            "베트남어": "vi-VN",
            "태국어": "th-TH",
            "인도네시아어": "id-ID",
            "힌디어": "hi-IN"
        }
        
        # 언어 코드 매핑 (번역용)
        self.translate_codes = {
            "영어 (미국)": "en",
            "영어 (영국)": "en",
            "한국어": "ko",
            "일본어": "ja",
            "중국어 (간체)": "zh",
            "중국어 (번체)": "zh-TW",
            "스페인어": "es",
            "프랑스어": "fr",
            "독일어": "de",
            "러시아어": "ru",
            "베트남어": "vi",
            "태국어": "th",
            "인도네시아어": "id",
            "힌디어": "hi"
        }
        
        self.selected_source_language = tk.StringVar(value="영어 (미국)")
        self.selected_target_language = tk.StringVar(value="한국어")
        
        # UI 구성
        self.setup_ui()

    def update_labels(self, event=None):
        # 레이블 텍스트 업데이트
        self.original_label.config(text=f"원본 텍스트 ({self.selected_source_language.get()})")
        self.translated_label.config(text=f"번역 텍스트 ({self.selected_target_language.get()})")
    
    def setup_ui(self):
        # 프레임 설정
        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 오디오 장치 선택 프레임
        device_frame = tk.Frame(main_frame, bg="#f0f0f0")
        device_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(device_frame, text="오디오 입력 장치:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT)
        self.device_combobox = ttk.Combobox(
            device_frame, 
            textvariable=self.selected_device,
            values=list(self.input_devices.keys()),
            state="readonly",
            width=30,
            font=("Arial", 11)
        )
        self.device_combobox.pack(side=tk.LEFT, padx=5)
        
        # 상단 컨트롤 프레임
        control_frame = tk.Frame(main_frame, bg="#f0f0f0")
        control_frame.pack(fill=tk.X, pady=5)
        
        # 언어 선택 프레임
        lang_frame = tk.Frame(control_frame, bg="#f0f0f0")
        lang_frame.pack(side=tk.LEFT, padx=5)
        
        # 소스 언어 선택
        tk.Label(lang_frame, text="입력 언어:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT)
        self.source_lang_combobox = ttk.Combobox(
            lang_frame, 
            textvariable=self.selected_source_language,
            values=list(self.languages.keys()),
            state="readonly",
            width=15,
            font=("Arial", 11)
        )
        self.source_lang_combobox.pack(side=tk.LEFT, padx=5)
        
        # 목표 언어 선택
        tk.Label(lang_frame, text="번역 언어:", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT)
        self.target_lang_combobox = ttk.Combobox(
            lang_frame, 
            textvariable=self.selected_target_language,
            values=list(self.languages.keys()),
            state="readonly",
            width=15,
            font=("Arial", 11)
        )
        self.target_lang_combobox.pack(side=tk.LEFT, padx=5)
        
        # 콤보박스 이벤트 바인딩
        self.source_lang_combobox.bind('<<ComboboxSelected>>', self.update_labels)
        self.target_lang_combobox.bind('<<ComboboxSelected>>', self.update_labels)
        self.source_lang_combobox.bind('<KeyRelease>', lambda e: self.search_language(e, self.source_lang_combobox))
        self.target_lang_combobox.bind('<KeyRelease>', lambda e: self.search_language(e, self.target_lang_combobox))
        
        # 시작/중지 버튼
        self.start_button = tk.Button(control_frame, text="번역 시작", command=self.toggle_recording,
                                     bg="#4CAF50", fg="white", font=("Arial", 12), width=10)
        self.start_button.pack(side=tk.LEFT, padx=20)
        
        # 상태 표시 레이블
        self.status_label = tk.Label(control_frame, text="대기 중", bg="#f0f0f0", font=("Arial", 12))
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # 텍스트 영역 프레임
        text_frame = tk.Frame(main_frame, bg="#f0f0f0")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 원본 텍스트
        self.original_label = tk.Label(text_frame, text=f"원본 텍스트 ({self.selected_source_language.get()})", 
                                     bg="#f0f0f0", font=("Arial", 12, "bold"))
        self.original_label.pack(anchor="w")
        
        self.original_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=8, 
                                                     font=("Arial", 12))
        self.original_text.pack(fill=tk.X, expand=False, pady=5)
        
        # 번역 텍스트
        self.translated_label = tk.Label(text_frame, text=f"번역 텍스트 ({self.selected_target_language.get()})", 
                                      bg="#f0f0f0", font=("Arial", 12, "bold"))
        self.translated_label.pack(anchor="w")
        
        self.translated_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=8, 
                                                      font=("Arial", 12))
        self.translated_text.pack(fill=tk.X, expand=False, pady=5)
        
        # 파일 저장 정보
        save_info = tk.Label(main_frame, 
                           text=f"원본 텍스트 저장: {self.original_file}\n번역 텍스트 저장: {self.translated_file}", 
                           bg="#f0f0f0", font=("Arial", 10))
        save_info.pack(anchor="w", pady=5)
    
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
            self.start_button.config(text="번역 중지", bg="#F44336")
            self.status_label.config(text="번역 중...")
        else:
            self.stop_recording()
            self.start_button.config(text="번역 시작", bg="#4CAF50")
            self.status_label.config(text="대기 중")
    
    def start_recording(self):
        self.is_recording = True
        
        # 선택된 오디오 장치 인덱스 가져오기
        device_index = self.input_devices.get(self.selected_device.get(), None)
        
        # 오디오 스트림 열기
        self.stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=device_index,  # 선택된 장치 사용
            frames_per_buffer=self.chunk
        )
        
        # 스레드 시작
        self.record_thread = threading.Thread(target=self.record_audio)
        self.process_thread = threading.Thread(target=self.process_audio)
        self.update_thread = threading.Thread(target=self.update_ui)
        
        self.record_thread.daemon = True
        self.process_thread.daemon = True
        self.update_thread.daemon = True
        
        self.record_thread.start()
        self.process_thread.start()
        self.update_thread.start()
    
    def stop_recording(self):
        self.is_recording = False
        if hasattr(self, 'stream') and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
    
    def record_audio(self):
        while self.is_recording:
            # 5초 동안 오디오 수집
            frames = []
            for i in range(0, int(self.rate / self.chunk * self.record_seconds)):
                if not self.is_recording:
                    break
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)
            
            if frames and self.is_recording:  # 녹음이 중지되지 않았다면 큐에 추가
                self.audio_queue.put(frames)
    
    def search_language(self, event, combobox):
        # 현재 입력된 텍스트
        search_text = combobox.get().lower()
        
        # 검색 결과 필터링
        filtered_languages = [
            lang for lang in self.languages.keys()
            if search_text in lang.lower()
        ]
        
        # 콤보박스 업데이트
        combobox['values'] = filtered_languages
        
        # 드롭다운 표시
        combobox.event_generate('<Down>')

    def process_audio(self):
        while self.is_recording or not self.audio_queue.empty():
            try:
                frames = self.audio_queue.get(timeout=1)
                
                # 바이트 데이터로 직접 변환
                audio_data = b''.join(frames)
                
                # 음성 인식 요청 설정
                content = audio_data
                
                audio = speech.RecognitionAudio(content=content)
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=self.rate,
                    language_code=self.languages[self.selected_source_language.get()],
                    enable_automatic_punctuation=True
                )
                
                # 음성 인식 수행
                response = self.speech_client.recognize(config=config, audio=audio)
                
                # 결과 처리
                for result in response.results:
                    original_text = result.alternatives[0].transcript
                    if original_text.strip():  # 빈 텍스트가 아닌 경우에만 처리
                        # 번역 수행
                        source_lang = self.translate_codes[self.selected_source_language.get()]
                        target_lang = self.translate_codes[self.selected_target_language.get()]
                        
                        translation = self.translate_client.translate(
                            original_text, 
                            target_language=target_lang,
                            source_language=source_lang
                        )
                        
                        translated_text = translation['translatedText']
                        
                        # 결과를 큐에 추가
                        self.text_queue.put((original_text, translated_text))
                        
                        # 파일에 저장
                        with open(self.original_file, 'a', encoding='utf-8') as f:
                            f.write(original_text + '\n')
                        
                        with open(self.translated_file, 'a', encoding='utf-8') as f:
                            f.write(translated_text + '\n')
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")
    
    def update_ui(self):
        while self.is_recording or not self.text_queue.empty():
            try:
                original, translated = self.text_queue.get(timeout=0.1)
                if original and translated:  # 유효한 텍스트인 경우에만 처리
                    # UI 업데이트는 메인 스레드에서 수행
                    self.root.after(10, self.update_text_widgets, original, translated)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error updating UI: {e}")
                import traceback
                traceback.print_exc()
    
    def update_text_widgets(self, original, translated):
        try:
            # 원본 텍스트 업데이트
            self.original_text.insert(tk.END, original + '\n')
            self.original_text.see(tk.END)
            
            # 번역 텍스트 업데이트
            self.translated_text.insert(tk.END, translated + '\n')
            self.translated_text.see(tk.END)
            
            # 텍스트 위젯 내용 제한
            if float(self.original_text.index('end-1c').split('.')[0]) > 1000:
                self.original_text.delete('1.0', '100.0')
            if float(self.translated_text.index('end-1c').split('.')[0]) > 1000:
                self.translated_text.delete('1.0', '100.0')
            
            # 화면 갱신 강제
            self.root.update_idletasks()
        except Exception as e:
            print(f"Error in update_text_widgets: {e}")
            import traceback
            traceback.print_exc()

    def get_input_devices(self):
        """사용 가능한 오디오 입력 장치 목록을 반환합니다."""
        devices = {}
        info = self.audio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        
        for i in range(num_devices):
            device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
            if device_info.get('maxInputChannels') > 0:  # 입력 장치만 필터링
                devices[f"{device_info.get('name')}"] = i
        
        return devices

if __name__ == "__main__":
    root = tk.Tk()
    app = RealtimeTranslator(root)
    root.mainloop()