# translator_service.py
from google.cloud import translate_v2 as translate
from config import TRANSLATE_CODES
import traceback # 추가 (오류 로깅 강화)
import html      # <<< 추가: 만약을 위한 HTML 언이스케이프

class TranslatorService:
    def __init__(self, source_language, target_language):
        """
        source_language, target_language: UI에서 선택한 언어 (예: "영어 (미국)", "한국어")
        """
        self.client = translate.Client()
        self.source_language = source_language
        self.target_language = target_language

    def translate_text(self, text):
        """텍스트를 번역하여 번역된 문자열 반환"""
        if not text or not text.strip(): # 빈 텍스트 또는 공백만 있는 텍스트는 번역 요청 안 함
            # print("번역 건너뜀: 빈 텍스트") # 디버깅용
            return ""
        try:
            source_lang_code = TRANSLATE_CODES.get(self.source_language)
            target_lang_code = TRANSLATE_CODES.get(self.target_language)

            if not source_lang_code or not target_lang_code:
                print(f"오류: 지원하지 않는 언어 코드 - 소스: {self.source_language}, 타겟: {self.target_language}")
                return f"[번역 오류: 언어 코드 확인 필요]"

            # print(f"번역 요청: '{text}' ({source_lang_code} -> {target_lang_code})") # 디버깅용
            translation = self.client.translate(
                text,
                target_language=target_lang_code,
                source_language=source_lang_code, # 명시적으로 지정
                format_='text'  # <<<--- 이 파라미터를 추가하여 결과 형식을 텍스트로 지정
            )
            translated = translation['translatedText']
            # print(f"번역 결과 (API): '{translated}'") # 디버깅용

            # 만약 format_='text'로도 해결되지 않는 특수한 HTML 엔티티가 있다면
            # html.unescape를 사용하여 추가로 디코딩할 수 있습니다.
            # 일반적으로 format_='text'만으로 충분합니다.
            # decoded_translated = html.unescape(translated)
            # if translated != decoded_translated:
            #    print(f"HTML 언이스케이프 적용: '{decoded_translated}'") # 디버깅용
            # return decoded_translated

            return translated # format_='text'를 사용하면 보통 추가 디코딩 불필요

        except Exception as e:
            print(f"번역 API 오류 (텍스트: '{text}'): {e}")
            traceback.print_exc() # 상세 오류 출력
            return "[번역 오류]"