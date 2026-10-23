# SureMeetingRoom Bot v0.2 Phase 2.3A Specification: Platform-Independent Meeting Room Web App v1

**Document Version**: 1.0.0  
**Status**: Completed & Validated (Review Ready)  
**Task Base Commit**: `aefce423a690e0d6140906177e0b2251bd0ed354`  
**Target Branch**: `feature/v0.2-platform-abstraction`  

---

## 1. Web App 목적 (Purpose)

기존 Telegram 챗봇 텍스트 및 인라인 키보드 UI는 단계별 선택(메뉴 → 위치 → 시간)을 거쳐야 하므로 "지금 어떤 회의실이 언제까지 비어있는지"를 한눈에 직관적으로 파악하기 어려웠습니다.

Phase 2.3A에서는 이를 해결하기 위해 **모바일 우선(Mobile-First) 반응형 회의실 시간표(Timeline) Web App v1**을 구현했습니다.
사용자는 복잡한 Groupware 화면을 검색하지 않고도 모바일 브라우저 화면 하나에서:
1. 오늘 날짜 및 현재 시각(Asia/Seoul)
2. 층/위치별 전체 회의실 목록 및 정원(수용 인원)
3. 08:00 ~ 20:00 업무 시간 기준 예약 현황 블록
4. "지금 빈 회의실(🟢)" 강조 표시
5. 즐겨찾기(⭐) 회의실 필터링
6. 예약 블록 터치 시 상세 정보(예약 시간, 예약자, 회의명) 확인

을 즉각적으로 파악할 수 있습니다.

---

## 2. Architecture & Design Principles

### 2.1 Platform-Independent Architecture

본 Web App은 Telegram, Kakao, 사내 일반 브라우저 모두에서 공통으로 재사용할 수 있도록 **완전한 플랫폼 독립(Platform-Independent)** 원칙에 따라 설계되었습니다.

```
                  [ Standalone Mobile / Desktop Browser ]
                  [ Telegram Mini App (Phase 2.3B)      ]
                  [ Kakao Webview (Future)              ]
                                    │
                                    ▼
                Meeting Room Timeline Web App (HTML/CSS/JS)
                                    │
                         GET /timeline (HTML)
                     GET /api/web/timeline (JSON)
                                    │
                                    ▼
                      FastAPI Web Application (app.py)
                                    │
                       Provider Interface Layer
                    (MeetingRoomQueryProvider)
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
           MockMeetingRoomProvider      RealMeetingRoomProvider
                     │                             │
                     ▼                             ▼
            MockMeetingRoomData           MeetingRoomService
                                                   │
                                                   ▼
                                            GroupwareClient
```

- **Telegram 전용 의존성 완전 배제 (0 Dependency)**:
  - Web App 템플릿(`timeline.html`), 라우터(`app.py`), 서비스(`MeetingRoomService`) 내부에 `Telegram.WebApp`, `if telegram_user:` 등의 플랫폼 종속 코드를 전혀 포함하지 않습니다.
  - 향후 Telegram Mini App 연동은 Phase 2.3B에서 Adapter Layer를 통해 별도로 구현됩니다.

---

## 3. Timeline Data Flow

### 3.1 Bootstrap Initial Load (`GET /timeline`)
1. 사용자가 브라우저로 `GET /timeline` 접근
2. FastAPI 미들웨어 및 라우터에서 `meetingroom_web_session` 쿠키 검증
3. `web_session_store` 및 `session_manager`에서 사용자 세션 이중 검증
4. `get_provider().get_timeline(user_id, asset_id=None)` 호출 (`asyncio.to_thread`를 통한 논블로킹 I/O 격리)
5. 서버사이드에서 렌더링된 초기 데이터셋을 `<script id="initial-timeline-data" type="application/json">`으로 주입
6. 클라이언트 JS가 추가 네트워크 라운드트립 없이 즉시 시간표 그리드를 렌더링하여 첫 화면 깜빡임 없는 고속 로딩 제공

### 3.2 Dynamic Floor Switching (`GET /api/web/timeline?asset_id=...`)
1. 사용자가 상단 층 드롭다운(`[ 판교 7층 ▼ ]`)을 변경
2. 클라이언트 JS가 `GET /api/web/timeline?asset_id=80` 비동기 fetch 호출
3. JSON 응답 수신 후 시간표 그리드, 회의실 목록, 예약 블록을 페이지 새로고침 없이 즉각 갱신

---

## 4. Authentication & Security Policy

### 4.1 Strict Dual Session Validation
모든 Timeline 접근 시 다음 두 계층을 검증합니다:
1. **WebSession 검증**: `meetingroom_web_session` HttpOnly 쿠키가 유효하며 만료되지 않았는지 확인.
2. **GroupwareClient 세션 검증**: `session_manager` 내에 해당 `UserKey`에 대한 활성 Groupware 인증 세션이 존재하는지 확인.

### 4.2 Error & Boundary Handling
- **미인증 접근**: HTTP 401 반환 및 친절한 안내 화면 ("인증되지 않은 접근입니다. 계정을 먼저 연결해주세요.")
- **세션 만료 (Groupware 401)**: HTTP 401 반환, 만료된 WebSession 쿠키 즉시 소각, 안내 화면 ("계정 연결이 만료되었습니다. 다시 연결해 주세요.")
- **네트워크 오류 (Groupware Connection Error)**: HTTP 502 / 안전한 오류 배너 ("회의실 정보를 불러오지 못했습니다. 네트워크 상태를 확인해주세요.") 제공 (내부 traceback 노출 엄격 차단)

### 4.3 Zero Credential Leakage
- `password`, `GOSSOcookie`, `account link token`, `LinkSession ID`, `WebSession ID`는 HTML 렌더링 결과 및 API 응답 JSON에 **절대 포함되지 않습니다**.
- 테스트 스위트(`TestCredentialHygiene`)를 통해 자동 검증됩니다.

### 4.4 Security Response Headers & Future Mini App Consideration
현재 적용 중인 보안 헤더:
```http
Referrer-Policy: no-referrer
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: frame-ancestors 'none'
```
> [!NOTE]
> Phase 2.3B Telegram Mini App 연동 시 Telegram 내 iframe/WebView 로딩을 허용하기 위해 `X-Frame-Options` 및 CSP `frame-ancestors https://web.telegram.org` 정책 조정이 필요합니다. Phase 2.3A에서는 보안 원칙을 유지하기 위해 완화하지 않았으며, Phase 2.3B 어댑터 작업 시 선별적으로 조정됩니다.

---

## 5. Mobile-First UX Design

1. **고정 회의실 컬럼 (Sticky Left Column)**:
   - 360px ~ 430px 모바일 화면에서 시간축이 가로로 스크롤되더라도 회의실 이름, 정원, 지금 사용 가능 상태를 식별할 수 있도록 좌측 컬럼(`position: sticky; left: 0; z-index: 20`)을 고정했습니다.
2. **Asia/Seoul 실시간 세로 인디케이터**:
   - 업무 시간(08:00 ~ 20:00) 기준 현재 시각을 나타내는 붉은색 세로 Indicator 라인 및 시각 배지(`11:05`)가 실시간 위치에 표시됩니다.
3. **접근성 중심 시각 표현 (Accessibility-Focused)**:
   - 색상(초록/빨강)뿐만 아니라 명확한 텍스트 배지(`🟢 지금 빈 회의실`, `🔴 사용 중 (14:00까지)`), 굵은 폰트, 외곽선(Border)을 병행하여 저시력자 및 색약자도 즉시 상태를 판별할 수 있습니다.
4. **Detail Bottom Sheet / Modal**:
   - 예약 블록을 클릭/터치하면 모바일에서는 하단에서 부드럽게 올라오는 Bottom Sheet, 데스크톱에서는 팝업 Modal 형태로 회의실 상세, 예약 시간, 예약자, 회의명을 표시합니다.

---

## 6. Reservation Data & Presentation Policy

### 6.1 DTO Extension
Groupware API 실제 응답 필드 분석에 기반하여 `Reservation` DTO를 확장했습니다:
- `reserver_name: Optional[str]` (API 필드: `userName`, `empName`, `reserverName`, `registerName`, `writer`)
- `meeting_title: Optional[str]` (API 필드: `title`, `subject`, `meetingTitle`, `scheduleTitle`)

### 6.2 Centralized Presentation Policy
개인정보 정책에 따라 Core 데이터를 영구 삭제하지 않고 `AppConfig` 환경 설정으로 마스킹을 제어합니다:
- `TIMELINE_START_HOUR`: 시간축 시작 시각 (기본값: `8`)
- `TIMELINE_END_HOUR`: 시간축 종료 시각 (기본값: `20`)
- `SHOW_RESERVER_NAME`: 예약자명 표시 여부 (기본값: `true`)
- `SHOW_MEETING_TITLE`: 회의명 표시 여부 (기본값: `true`)

---

## 7. Favorites Integration

- 기존 `UserKey` 기반 `FavoriteService` 및 `JsonFavoriteRepository`를 100% 재사용합니다.
- 상단 `[⭐ 즐겨찾기]` 필터 버튼 터치 시 사용자가 등록한 즐겨찾기 회의실/층만 즉각 필터링됩니다.
- 즐겨찾기가 없는 경우 친절한 안내 메시지("⭐ 즐겨찾기된 회의실이 없습니다. 챗봇에서 자주 찾는 회의실을 등록해보세요.")를 제공합니다.

---

## 8. Test & Quality Assurance

- **Baseline Tests**: 기존 239건 전건 유지 및 통과 (`239 passed`)
- **New Tests (Phase 2.3A)**: 22건 신규 단위 및 통합 테스트 작성 (`22 passed`)
- **Total Tests**: `261 passed, 0 failed, 0 skipped`
- **End-to-End Smoke Test**: `scripts/smoke_test_phase2_3a.py` 9단계 전 검증 통과

---

## 9. Next Steps: Phase 2.3B Telegram Mini App Adapter

Phase 2.3B에서는 본 Web App을 수정 없이 그대로 감싸는 Adapter를 구현합니다:
1. Telegram Bot 인라인 키보드에 `web_app=WebAppInfo(url=...)` 버튼 연결
2. Telegram `initData` 기반 검증 및 Seamless WebSession 매핑
3. Mini App 내 iframe 허용을 위한 CSP / X-Frame-Options 정책 정밀 조정
4. 모바일 Telegram 내 뒤로가기 버튼 / 햅틱 피드백 이벤트 연동
