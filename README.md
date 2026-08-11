# suremeetingroom-bot

그룹웨어 회의실 자동 예약, 현황 조회, 가용시간 계산 및 텔레그램 봇 연동을 지원하는 회의실 관리 봇 프로젝트입니다.

---

## 🌟 주요 기능

1. **🏢 그룹웨어 연동 및 회의실 현황 조회**: 층별 회의실 실시간 예약 현황 및 사용 여부 조회 (`RoomStatusService`)
2. **🕒 가용시간(빈 시간대) 계산**: 특정 날짜/시간 구간 내에서 예약 가능한 회의실 빈 시간 슬롯 자동 추천 (`AvailabilityService`)
3. **⭐ 회의실 즐겨찾기 (Favorites)**: 자주 사용하는 회의실을 등록/삭제하고 빠르게 조회하는 기능 (`FavoriteService`)
4. **🤖 텔레그램 봇 (Telegram Bot) 대화형 UI**: 인라인 버튼 기반 회의실 현황 조회, 빈 시간 검색, 즐겨찾기 관리 지원 (`src/meeting_room_bot/telegram/`)

---

## 📂 프로젝트 구조

```
suremeetingroom-bot/
├── src/
│   └── meeting_room_bot/
│       ├── __init__.py
│       ├── groupware/
│       │   ├── __init__.py
│       │   └── client.py              # 그룹웨어 API 클라이언트
│       ├── models/
│       │   ├── asset.py               # 회의실/자산 모델
│       │   ├── reservation.py         # 예약 모델
│       │   └── room.py                # 회의실 모델
│       ├── services/
│       │   ├── availability_service.py # 가용 시간대 계산 서비스
│       │   ├── meeting_room_service.py # 회의실 통합 서비스
│       │   └── room_status_service.py # 회의실 현황 서비스
│       ├── favorites/                 # 즐겨찾기 관리 모듈
│       │   ├── json_repository.py
│       │   ├── repository.py
│       │   └── service.py
│       └── telegram/                  # 텔레그램 봇 UI 및 핸들러
│           ├── bot.py
│           ├── handlers.py
│           ├── keyboards.py
│           ├── mock_service.py
│           └── states.py
├── scripts/
│   ├── run_telegram_bot.py            # 텔레그램 봇 실행 스크립트
│   ├── room_status_poc.py             # 회의실 현황 PoC
│   ├── availability_poc.py            # 가용 시간 조회 PoC
│   ├── favorites_poc.py               # 즐겨찾기 PoC
│   ├── list_assets_poc.py             # 자산 목록 PoC
│   └── query_menu_poc.py              # 메뉴 쿼리 PoC
├── tests/                             # Pytest 단위 테스트 모음
├── docs/
│   ├── README.md                      # 문서 메인
│   └── CHANGELOG.md                   # 상세 변경 이력
├── .env.example                       # 환경 변수 템플릿
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 🚀 시작하기

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정 (`.env`)
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 필요한 토큰 및 인증 정보를 입력합니다:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GROUPWARE_USER_ID=your_id
GROUPWARE_PASSWORD=your_password
```

---

## 🤖 텔레그램 봇 실행

```bash
python scripts/run_telegram_bot.py
```

---

## 🧪 테스트 실행

```bash
pytest
```
*(현재 68개 단위 테스트 통과)*

---

## 📜 변경 이력
상세한 업데이트 내역 및 기능 변경 이력은 [docs/CHANGELOG.md](file:///c:/Users/suresoft/Desktop/priv/30.vibe/06.meetingroom/suremeetingroom-bot/docs/CHANGELOG.md)를 참고하세요.
