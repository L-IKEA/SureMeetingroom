# Change Log (변경 이력)

## [Unreleased / Latest Update] - 2026-08-11

### 🤖 텔레그램 봇 (Telegram Bot) 대화형 인터페이스 추가
- `python-telegram-bot` (v22+) 대화형(Interactive) 키보드 및 ConversationHandler 상태 기반 대화 흐름 구축
- **주요 봇 모듈 (`src/meeting_room_bot/telegram/`)**:
  - `bot.py`: 텔레그램 봇 응용 프로그램 생성 및 핸들러 등록 entrypoint
  - `handlers.py`: 메인 메뉴, 회의실 현황 조회, 빈 시간대(가용시간) 조회, 즐겨찾기 목록 및 관리 대화 처리기
  - `keyboards.py`: 인라인 버튼 및 키보드 레이아웃 생성기 (층별 선택, 시간대 선택, 메뉴 버튼 등)
  - `states.py`: 대화 상태 정의 Enum (`CHOOSING_MENU`, `SELECTING_FLOOR`, `SELECTING_TIME_SLOT` 등)
  - `mock_service.py`: 봇 대화 기능 테스트 및 그룹웨어 오프라인 상태 개발을 위한 Mock 서비스 제공

### ⭐ 회의실 즐겨찾기 (Favorites) 시스템
- 자주 사용하는 회의실을 관리할 수 있는 즐겨찾기 서비스 구현 (`src/meeting_room_bot/favorites/`)
  - `models.py`: 즐겨찾기 항목 Data Model (`FavoriteItem`)
  - `repository.py` / `json_repository.py`: JSON 파일 기반 즐겨찾기 지속성 저장소 구현 (`JsonFavoriteRepository`)
  - `service.py`: 즐겨찾기 추가/삭제/목록 조회/순서 변경 비즈니스 로직 (`FavoriteService`)

### 🕒 회의실 가용 시간대 계산 서비스 (`AvailabilityService`)
- `src/meeting_room_bot/services/availability_service.py`
  - 지정한 회의실 및 날짜/시간 구간 내에서 즉시 또는 연속으로 사용 가능한 빈 시간 슬롯(Free Slots) 자동 도출
  - 기존 예약 현황(`Reservation`)과의 중복 시간대 정밀 필터링 지원

### 🏢 회의실 및 자산 관리 서비스 (`MeetingRoomService`, `Asset`)
- `src/meeting_room_bot/models/asset.py`: 층별 회의실 및 비품/자산 정보를 표현하는 모델
- `src/meeting_room_bot/services/meeting_room_service.py`: 그룹웨어 API 데이터 기반 층별 회의실 매핑 및 자산 목록 조회 통합 서비스

### 🧪 스크립트 및 검증 PoC 확장 (`scripts/`)
- `scripts/run_telegram_bot.py`: `.env` 환경 변수 기반 텔레그램 봇 실행기
- `scripts/availability_poc.py`: 빈 회의실 시간대 조회 서비스 PoC
- `scripts/favorites_poc.py`: 즐겨찾기 저장 및 관리 PoC
- `scripts/list_assets_poc.py`: 회의실/자산 목록 조회 PoC
- `scripts/query_menu_poc.py`: 그룹웨어 자산 쿼리 및 메뉴 탐색 PoC

### ✅ 테스트 자동화 (Test Suite) 확장
- 전체 단위 테스트 suite 68개 통과 (`pytest` 실행 결과 68 passed)
  - `tests/test_telegram_bot.py`: 텔레그램 봇 핸들러 및 대화 흐름 테스트
  - `tests/test_favorites.py`: 즐겨찾기 CRUD 테스트
  - `tests/test_availability_service.py`: 가용 시간 계산 정확도 검증 테스트
  - `tests/test_meeting_room_service.py`: 회의실 서비스 통합 테스트

### ⚙️ 의존성 및 프로젝트 환경
- `requirements.txt`: `python-telegram-bot>=22.0`, `python-dotenv>=1.0.0` 추가
- `pytest.ini`: pytest 탐색 설정 및 경로 명시
- `.gitignore`: 로컬 데이터(`data/*.json`) 및 민감 환경변수(`.env`) 커밋 방지 처리
