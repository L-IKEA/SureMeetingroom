# suremeetingroom-bot (v0.1-local-mvp)

그룹웨어 회의실 자동 예약, 현황 조회, 가용시간 계산, 계정 연동 및 텔레그램 봇 연동을 지원하는 회의실 관리 봇 프로젝트입니다.

---

## 🌟 주요 기능 (v0.1-local-mvp)

1. **🔗 계정 연동 (Account Link)**: 텔레그램 계정과 그룹웨어 인증 정보를 안전하게 바인딩하는 로컬 인증 웹서버 제공
2. **🤖 텔레그램 봇 대화형 UI**: 인라인 버튼 기반 회의실 현황 조회, 빈 시간 검색, 즐겨찾기 등록/조회 및 계정 연동 지원
3. **🕒 가용시간(빈 시간대) 계산**: 지정 구간 내 예약 가능한 연속 빈 시간 슬롯 자동 계산 (`AvailabilityService`)
4. **⭐ 회의실 & 자산 즐겨찾기**: 자주 사용하는 회의실/자산을 유저별로 관리 (`FavoriteService`)
5. **🏢 정밀 회의실 현황 계산**: 실시간 당일 예약 필터링, 잔여 시간 계산 및 사용 상태 표시 (`RoomStatusService`)

---

## 📂 프로젝트 구조

```
suremeetingroom-bot/
├── src/
│   └── meeting_room_bot/
│       ├── __init__.py
│       ├── account_link/              # 계정 연동 로컬 웹서버 모듈
│       ├── auth/                      # 인증 및 세션 관리 프로바이더
│       ├── favorites/                 # 즐겨찾기 서비스 및 저장소
│       ├── groupware/                 # 그룹웨어 API 클라이언트
│       ├── models/                    # Asset, Room, Reservation 모델
│       ├── providers/                 # 데이터 및 인증 프로바이더
│       ├── services/                  # Availability, MeetingRoom, RoomStatus 서비스
│       └── telegram/                  # 텔레그램 봇 UI, 핸들러, 키보드, mock 서비스
├── scripts/
│   ├── run_local_app.py               # 로컬 통합 앱 실행기 (웹서버 + 봇)
│   ├── run_account_link_server.py     # 계정 연동 전용 웹서버 실행기
│   ├── run_telegram_bot.py            # 텔레그램 봇 단독 실행기
│   └── *_poc.py                       # PoC 검증 스크립트 모음
├── tests/                             # 154개 Pytest 단위 테스트 모음
├── docs/
│   ├── README.md                      # 문서 메인
│   └── CHANGELOG.md                   # 상세 변경 이력 (v0.1-local-mvp)
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
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_DATA_MODE=real
ACCOUNT_LINK_BASE_URL=http://localhost:8000
```

---

## 🏃 실행 가이드 및 Account Linking 테스트 절차

### 1. 로컬 통합 앱 실행 (계정 연동 서버 + 텔레그램 봇)
```bash
python scripts/run_local_app.py
```

### 2. 텔레그램 계정 연동 및 조회 수순
1. Telegram 앱에서 `/start` 입력 후 조회 기능(예: `[🟢 지금 빈 회의실]`) 선택.
2. 미인증 유저는 `🔐 그룹웨어 계정 연결이 필요합니다.` 및 DEV 토큰 생성 안내 수신.
3. 앱 실행 터미널 로그에 출력된 `http://localhost:8000/link/<token>` URL 확인.
4. 동일 PC 웹 브라우저에서 해당 URL 접속 후 그룹웨어 계정 로그인 진행.
5. Telegram 앱으로 돌아가 회의실 조회 및 즐겨찾기 기능 사용.

---

## 🧪 테스트 실행

```bash
pytest
```
*(현재 157개 단위 테스트 통과)*

---

## 📜 변경 이력
버전별 상세 업데이트 내역은 [docs/CHANGELOG.md](file:///c:/Users/suresoft/Desktop/priv/30.vibe/06.meetingroom/suremeetingroom-bot/docs/CHANGELOG.md)를 참고하세요.
