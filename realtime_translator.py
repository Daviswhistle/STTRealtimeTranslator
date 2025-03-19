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
        self.chunk = 1024
        self.record_seconds = 5  # 5초 단위로 처리
        
        # 오디오 스트림 및 처리 관련 변수
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()
        
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
        
        # 오디오 스트림 열기
        self.stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
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
                
                # WAV 파일로 임시 저장
                temp_filename = f"temp_{int(time.time())}.wav"
                wf = wave.open(temp_filename, 'wb')
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))
                wf.close()
                
                # 음성 인식 요청 설정
                with open(temp_filename, 'rb') as audio_file:
                    content = audio_file.read()
                
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
                
                # 임시 파일 삭제
                try:
                    os.remove(temp_filename)
                except:
                    pass
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")
    
    def update_ui(self):
        while self.is_recording or not self.text_queue.empty():
            try:
                original, translated = self.text_queue.get(timeout=1)
                
                # UI 업데이트는 메인 스레드에서 수행
                self.root.after(0, self.update_text_widgets, original, translated)
                
            except queue.Empty:
                time.sleep(0.1)
                continue
            except Exception as e:
                print(f"Error updating UI: {e}")
    
    def update_text_widgets(self, original, translated):
        # 원본 텍스트 업데이트
        self.original_text.insert(tk.END, original + '\n')
        self.original_text.see(tk.END)
        
        # 번역 텍스트 업데이트
        self.translated_text.insert(tk.END, translated + '\n')
        self.translated_text.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = RealtimeTranslator(root)
    root.mainloop()