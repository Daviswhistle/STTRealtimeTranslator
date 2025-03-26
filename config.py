# config.py
import os
import datetime
import pyaudio # pyaudio 추가

# Google Cloud 인증 파일 경로 설정
# key.json 파일이 코드 실행 위치에 있다고 가정합니다.
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

# 오디오 설정
AUDIO_FORMAT = pyaudio.paInt16 # 실제 pyaudio 포맷 사용
CHANNELS = 1
RATE = 16000
# CHUNK: 마이크에서 읽는 단위. 스트리밍 API로 보낼 때도 이 크기를 사용할 수 있음
CHUNK = int(RATE / 10) # 100ms 단위 청크 (조정 가능)
# RECORD_SECONDS는 스트리밍 방식에서는 직접 사용되지 않음

# 언어 설정
LANGUAGES = {
    "영어 (미국)": "en-US",
    "영어 (영국)": "en-GB",
    "한국어": "ko-KR",
    "일본어": "ja-JP",
    "중국어 (간체)": "zh", # 또는 "zh-CN"
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

TRANSLATE_CODES = {
    "영어 (미국)": "en",
    "영어 (영국)": "en",
    "한국어": "ko",
    "일본어": "ja",
    "중국어 (간체)": "zh", # 또는 "zh-CN"
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

def get_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# 로그 파일 이름 (원본 및 번역 텍스트)
TIMESTAMP = get_timestamp()
ORIGINAL_FILE = f"original_text_{TIMESTAMP}.txt"
TRANSLATED_FILE = f"translated_text_{TIMESTAMP}.txt"