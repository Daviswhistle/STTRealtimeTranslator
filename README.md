# 실시간 번역 자막 프로그램

이 프로그램은 외국어 음성을 실시간으로 번역하여 자막을 제공합니다.

## 기능

- 선택한 입력 장치(기기 내 재생 포함)를 통해 음성을 실시간으로 인식
- Google Cloud Speech-to-Text API를 사용하여 음성을 텍스트로 변환
- Google Cloud Translation API를 사용하여 텍스트를 한국어로 번역
- 원본 텍스트와 번역된 한국어 텍스트를 화면에 표시
- 모든 텍스트를 파일로 자동 저장

## 설치 방법

1. 필요한 패키지 설치:
   ```
   pip install -r requirements.txt
   ```

2. Google Cloud 서비스 계정 키 설정:
- Google Cloud Console에서 프로젝트 생성
- [Speech-to-Text API](https://console.cloud.google.com/apis/library/speech.googleapis.com) 활성화
- [Cloud Translation API](https://console.cloud.google.com/apis/library/translate.googleapis.com) 활성화
- 서비스 계정 생성 및 JSON 키 파일 다운로드
- 다운로드한 JSON 키 파일을 프로젝트 폴더에 저장
- JSON 파일 이름을 `key.json`으로 변경하거나 
  realtime_translator.py 파일에서 환경 변수 설정 부분을 수정

## 사용 방법

1. 프로그램 실행:
   ```
   python realtime_translator.py
   ```

2. "번역 시작" 버튼을 클릭하여 번역을 시작합니다.

3. 번역을 중지하려면 "번역 중지" 버튼을 클릭합니다.

4. 프로그램 실행 시 자동으로 다음 파일이 생성됩니다:
   - `original_text_[날짜_시간].txt`: 원본 텍스트
   - `translated_text_[날짜_시간].txt`: 번역된 텍스트

## 주의사항

- Google Cloud 서비스 사용을 위해 결제 계정 등록이 필요할 수 있습니다.
- 인터넷 연결이 필요합니다(Google Cloud API 사용).