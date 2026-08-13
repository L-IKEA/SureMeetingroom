# Local MVP Architecture Documentation

본 문서는 **SureMeetingRoom Bot**의 Local MVP (1차 안정 버전) 시스템 아키텍처 및 데이터 흐름을 정리한 문서입니다.

---

## 1. System Architecture Diagram

```text
+-------------------------------------------------------------------------+
|                        Telegram Messenger Client                        |
+-------------------------------------------------------------------------+
                                    │
                                    │ Telegram Update / Callback Query
                                    ▼
+-------------------------------------------------------------------------+
|                       Telegram Bot (python-telegram-bot)                |
|  - handlers.py (Button callbacks & Navigation)                          |
|  - keyboards.py (Dynamic Inline Keyboards)                              |
|  - states.py (User UI State Manager)                                    |
+-------------------------------------------------------------------------+
                                    │
                         QueryResult (Provider Layer)
                                    ▼
+-------------------------------------------------------------------------+
|                      MeetingRoomQueryProvider                           |
|  ├─ RealMeetingRoomProvider (TELEGRAM_DATA_MODE=real)                   |
|  └─ MockMeetingRoomProvider (TELEGRAM_DATA_MODE=mock)                   |
+-------------------------------------------------------------------------+
          │                                           │
          │ (UserSessionManager)                      │ (FavoriteService)
          ▼                                           ▼
+-----------------------+                   +-----------------------------+
| GroupwareClient       |                   | FavoriteService             |
| - requests.Session    |                   | - Asset / Room Favorites    |
| - Cookie Session      |                   | - Per-user Isolation        |
+-----------------------+                   +-----------------------------+
          │                                           │
          └-------------------+-----------------------┘
                              │
                              ▼
+-------------------------------------------------------------------------+
|                       Groupware REST API Service                        |
|  - POST /api/login (Authentication)                                     |
|  - GET  /api/asset (Locations / Assets)                                 |
|  - GET  /api/asset/{asset_id}/item/ (Rooms / Items)                    |
|  - GET  /api/asset/{asset_id}/items/daily (Daily Reservations)         |
+-------------------------------------------------------------------------+
```

---

## 2. Component Layer Responsibilities

### 2.1 Telegram Interface Layer
- **`handlers.py`**: Telegram Update 및 Callback Query 핸들링, `safe_edit_message_text`를 이용한 UI 렌더링.
- **`keyboards.py`**: 메인 메뉴, 시간 선택, 층 선택, 회의실 목록, 즐겨찾기 변경 인라인 키보드 생성.
- **`states.py` (`UserStateManager`)**: 사용자별 UI 탐색 위치(`last_menu`), 시간(`time`), 기간(`duration`), 조회 범위(`scope`), 선택 층(`asset_id`) 메모리 관리.

### 2.2 Provider Layer (`providers/`)
- **`RealMeetingRoomProvider`**: 사용자 세션(`UserSessionManager.get_client(user_id)`) 및 `FavoriteService`를 조합하여 회의실 가용성, 층 목록, 상세 정보를 실시간 조회.
- **`MockMeetingRoomProvider`**: 외부 그룹웨어 통신 없이 독립된 층/회의실 Mock 데이터로 텔레그램 UI를 검증.

### 2.3 Core Service Layer (`services/`, `favorites/`, `auth/`)
- **`RoomStatusService`**: 기준 시각 `now` (Asia/Seoul) 및 오늘 자정 경계(`day_end`)에 맞춰 회의실 가용성(`AVAILABLE`/`OCCUPIED`), `current_reservation_end`, `next_reservation_start`, 연속 예약 `available_from`을 정밀 계산.
- **`MeetingRoomService`**: 그룹웨어 API 응답을 도메인 모델(`Asset`, `Room`, `Reservation`)로 변환하고 당일(`target_date`) 오버랩 예약 필터링 및 시간순 정렬.
- **`FavoriteService`**: `user_id`별 층/회의실 즐겨찾기 데이터 영속화 및 조회 범위 제한.
- **`UserSessionManager`**: Telegram `user_id` $\leftrightarrow$ 인증된 `GroupwareClient` 세션 매핑 관리.

### 2.4 Account Linking (Web Auth Layer)
- **`account_link/app.py` (FastAPI)**: Telegram 사용자가 계정 연결 버튼 클릭 시 일회성 Secure Token을 발급받아 HTTPS/HTTP 웹 브라우저에서 그룹웨어 계정으로 로그인 진행 (`POST /api/login`).
- **Local Sharing**: Local MVP 환경에서는 Telegram Bot 프로세스와 FastAPI 웹 서버가 동일한 `UserSessionManager` 싱글톤 인스턴스를 공유하여 로그인 성공 즉시 Telegram `user_id`에 Groupware 세션이 바인딩됨.

---

## 3. Data Isolation & Security Principles

1. **User Isolation**:
   - Groupware 세션 및 즐겨찾기 데이터는 Telegram `user_id` (`str(update.effective_user.id)`)를 키로 사용자별 분리 관리되며, 다중 사용자 격리 테스트(`tests/test_multi_user_isolation.py`)를 통해 이를 검증합니다.
   - 사용자 A의 세션 만료/로그아웃 및 즐겨찾기 변경은 사용자 B에게 일체 영향을 주지 않습니다.
2. **Secrets & Privacy Protection**:
   - `TELEGRAM_BOT_TOKEN`, 비밀번호, GOSSOcookie, Session Cookie는 코드에 노출되지 않으며 `.env`를 통해 관리됩니다.
   - 그룹웨어 API 응답에서 사용자 이름, 회의 제목 등 개인정보는 도메인 모델 변환 시 완전 배제됩니다.
