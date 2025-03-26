# speech_recognizer.py
from google.cloud import speech
from config import RATE, LANGUAGES

class SpeechRecognizer:
    def __init__(self, language):
        self.client = speech.SpeechClient()
        self.language_code = LANGUAGES.get(language, "en-US") # 기본값 설정
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=self.language_code,
            enable_automatic_punctuation=True,
            # 모델 선택 (선택적, 상황에 따라 다름. 'latest_long' 또는 'telephony' 등)
            # model='latest_long',
            # use_enhanced=True, # 향상된 모델 사용 (비용 증가)
        )
        # 스트리밍 설정을 streaming_config로 분리
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=self.config,
            interim_results=True # <<<=== 중요: 중간 결과 활성화
        )
        self.requests = None
        self.responses = None

    def start_streaming_recognize(self, audio_generator):
        """
        스트리밍 인식을 시작하고 응답 스트림을 반환합니다.
        audio_generator: 오디오 청크를 yield하는 제너레이터
        """
        print(f"스트리밍 인식 시작 (언어: {self.language_code})")
        # 스트리밍 요청 생성
        self.requests = (speech.StreamingRecognizeRequest(audio_content=content)
                       for content in audio_generator)

        # streaming_recognize 호출, responses는 반복 가능한 객체
        try:
            # DEADLINE_SECONDS 설정 추가 (예: 300초 = 5분) - 장시간 실행 시 필요할 수 있음
            self.responses = self.client.streaming_recognize(
                config=self.streaming_config,
                requests=self.requests,
                # timeout=300.0 # 요청 타임아웃 설정 (필요에 따라 조정)
            )
            return self.responses
        except Exception as e:
            print(f"Streaming recognize 시작 오류: {e}")
            self.responses = None # 오류 발생 시 None으로 설정
            return None

    # def recognize(self, audio_bytes):
    #     """음성 데이터를 받아 텍스트로 변환하여 리스트로 반환"""
    #     audio = speech.RecognitionAudio(content=audio_bytes)
    #     config = speech.RecognitionConfig(
    #         encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    #         sample_rate_hertz=RATE,
    #         language_code=LANGUAGES[self.language],
    #         enable_automatic_punctuation=True
    #     )
    #     response = self.client.recognize(config=config, audio=audio)
    #     transcripts = []
    #     for result in response.results:
    #         transcript = result.alternatives[0].transcript
    #         if transcript.strip():
    #             transcripts.append(transcript)
    #     return transcripts
