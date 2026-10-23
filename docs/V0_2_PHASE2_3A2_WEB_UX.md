# SureMeetingRoom Bot v0.2 - Phase 2.3A-2 Meeting Room Web App Core UX Integration

**문서 상태**: Approved (v0.2 Core UX Integration Baseline)  
**기준 커밋**: `1c562861cd4d876b8ddf95dd71728d20a6ba92f2`  
**브랜치**: `feature/v0.2-platform-abstraction`  
**작성일**: 2026-10-23  

---

## 1. 목적 (Purpose)

Phase 2.3A-2의 목적은 기존 텔레그램 봇에서 검증된 4가지 핵심 사용자 경험:
1. **지금 빈 회의실**
2. **언제 빈 회의실**
3. **어디 빈 회의실**
4. **즐겨찾기**

를 단순 복사/이식하는 것이 아니라, **웹 환경의 특성에 맞게 더 적은 터치와 직관적인 시인성**으로 단일 화면에 통합하는 것입니다.

기존 텔레그램 챗봇에서는 메뉴 선택 → 버튼 탭 → 페이지네이션 등 여러 단계의 메시지 교환을 거쳐야 했으나, 본 Web App에서는 상단 모드 탭(`[🟢 지금]`, `[🕐 언제]`, `[📊 전체]`), 층 선택 드롭다운(`[ 판교 7층 ▼ ]`), 즐겨찾기 세그먼트 토글(`[ 전체 ] [ ⭐ 즐겨찾기 ]`)을 통해 페이지 전체 reload 없이 즉시 원하는 정보를 탐색할 수 있습니다.

---

## 2. 3대 View Mode 정의

| 모드 | 탭 명칭 | 핵심 목적 | 주요 표시 정보 | 빈 상태 (Empty State) |
|---|---|---|---|---|
| **NOW** | `[🟢 지금]` | 현재 시각 기준 바로 사용할 수 있는 회의실 즉시 탐색 | 지금 사용 가능 여부, 정원, 다음 예약 시작 시각, 잔여 가용 시간(예: 약 55분 사용 가능) 또는 '오늘 남은 예약 없음' | "현재 바로 사용할 수 있는 회의실이 없습니다." |
| **WHEN** | `[🕐 언제]` | 특정 시작 시각 및 사용 시간 구간 전체의 빈 회의실 탐색 | 검색 조건(예: 14:00 ~ 15:00), 해당 구간 무경합 회의실, 정원, 가용 상태 | "선택한 시간에 사용 가능한 회의실이 없습니다." |
| **TIMELINE** | `[📊 전체]` | 오늘 08:00 ~ 20:00 전체 예약 및 시간대별 현황 시각화 | 고정 회의실 컬럼, 동적 시간축, 현재 시각 표시선, 예약 블록, 상세 바텀시트 모달 | "이 위치에 등록된 회의실이 없습니다." |

### 2.1 NOW 모드 (카드/리스트 뷰)
- 모바일에서 즉각적으로 빈 회의실을 확인하고 들어갈 수 있도록 **카드 뷰** 형태로 제공.
- 각 카드에는 회의실명, 정원 배지, `🟢 지금 사용 가능` 상태, 그리고 `다음 예약: 14:30 (약 55분 사용 가능)` 또는 `오늘 남은 예약 없음`을 강조 표시.
- 현재 사용 중인 회의실은 숨김 처리하여 즉각적인 의사결정 지원.

### 2.2 WHEN 모드 (구간 가용성 뷰)
- 사용자가 시작 시각(08:00 ~ 19:30, 30분 단위)과 사용 시간(`[ 30분 ] [ 1시간 ] [ 1시간 30분 ] [ 2시간 ]`)을 선택.
- 선택한 전체 구간 동안 단 1분이라도 예약이 겹치지 않는 회의실만 즉시 필터링하여 카드 목록으로 표시.
- 상단에 현재 검색 구간(예: `14:00 ~ 15:00 사용 가능`)을 명확히 명시.

### 2.3 TIMELINE 모드 (인터랙티브 그리드 뷰)
- Phase 2.3A에서 검증된 타임라인 전체 기능 100% 보존.
- 08:00 ~ 20:00 동적 시간축, 수직 현재 시각 마커(Red Line + Time Badge), 예약 블록 탭 시 예약자/회의명 상세 바텀시트 모달 노출.

---

## 3. 기존 Telegram Bot 기능과의 대응 관계

| Telegram Bot 기능 | Web App 대응 UX | 개선 및 통합 방식 |
|---|---|---|
| **지금 빈 회의실** | **NOW 모드** (`[🟢 지금]`) | 봇 텍스트 메시지 목록 대신 가독성 높은 반응형 카드 뷰로 즉시 렌더링. 다음 예약 시간 및 남은 분수 자동 계산. |
| **언제 빈 회의실** | **WHEN 모드** (`[🕐 언제]`) | 여러 단계의 시간/분 버튼 인라인 키보드 탐색 대신, 시작 시각 드롭다운과 4개 사용 시간 알약 버튼으로 원터치 전환. |
| **어디 빈 회의실** | **위치/층 드롭다운** (`[ 판교 7층 ▼ ]`) | 독립된 뷰 모드로 분리하지 않고, 상단 위치 선택 컴포넌트로 자연스럽게 통합. 선택 즉시 NOW/WHEN/TIMELINE 전체에 반영. |
| **즐겨찾기** | **Scope 세그먼트 토글** (`[ 전체 ] [ ⭐ 즐겨찾기 ]`) | 별도 메뉴 진입 없이 상단 토글 버튼으로 NOW, WHEN, TIMELINE 모든 모드에서 실시간 필터링. |

---

## 4. "어디" → Asset Selector 재해석

- 기존 Telegram의 "어디 빈 회의실" 메뉴는 층/위치를 먼저 고르게 하는 네비게이션 역할을 담당했습니다.
- Web App에서는 이를 별도 화면으로 나누지 않고 **상단 층/위치 선택 드롭다운**(`id="asset-select"`)으로 일원화하였습니다.
- 선택 목록은 코스튬이나 HTML 하드코딩이 아닌, Groupware API / Provider의 실제 `Asset` 데이터를 통해 동적으로 생성됩니다.
- 층 변경 이벤트 발생 시:
  - NOW 모드: `/api/web/timeline?asset_id=X` 갱신 후 즉시 카드 재렌더링.
  - WHEN 모드: `/api/web/availability?asset_id=X&start=...&duration_minutes=...` 호출 후 카드 재렌더링.
  - TIMELINE 모드: 타임라인 데이터 재조회 및 그리드 재렌더링.

---

## 5. Favorites Scope의 일관된 적용

즐겨찾기 토글(`[ 전체 ]` vs `[ ⭐ 즐겨찾기 ]`)은 특정 모드에 종속되지 않고 3개 모드 모두에서 완벽히 직교(orthogonal)하여 동작합니다:
- **NOW + 즐겨찾기**: 즐겨찾기로 등록된 회의실 중 **지금 바로 쓸 수 있는 회의실**만 표시.
- **WHEN + 즐겨찾기**: 즐겨찾기 회의실 중 **지정한 시간 구간에 비어 있는 회의실**만 표시.
- **TIMELINE + 즐겨찾기**: 즐겨찾기 회의실들만의 **타임라인 시간표** 표시.
- 각 모드에서 즐겨찾기 회의실이 없거나 가용 회의실이 없는 경우 모드별 전용 안내 메시지("즐겨찾기한 회의실이 없습니다.")가 출력됩니다.

---

## 6. Shared Core 비즈니스 로직 재사용 (중복 제거)

비즈니스 규칙의 파편화를 방지하기 위해 Web 계층에서 자체 가용성 판별 알고리즘을 구현하지 않고, 이미 검증된 Shared Core 서비스를 100% 재사용합니다:

1. **`RoomStatusService.calculate_status(room, reservations, now)`**:
   - 회의실의 현재 사용 가능 여부(`is_available`), 현재 예약 종료 시각, 다음 예약 시작 시각 계산.
   - NOW 모드 가용성 판별 및 `next_reservation_start`, `available_minutes` 도출에 재사용.
2. **`AvailabilityService.find_available_rooms(rooms, res_map, req_start, req_end)`**:
   - `res_start < req_end and res_end > req_start` 무경합 구간 검증.
   - 예약 시작과 요청 종료가 같거나(`res.start == req.end`), 예약 종료와 요청 시작이 같은(`res.end == req.start`) 경계 조건을 정확히 가용으로 판정.
   - WHEN 모드 가용 회의실 계산에 직접 호출.
3. **`MeetingRoomService.get_web_availability(...)` 및 `get_timeline_data(...)`**:
   - Core 서비스 레벨에서 구조화된 JSON 계약을 생성하여 Mock Provider와 Real Provider가 동일한 Core 로직을 공유.

---

## 7. Web API 명세

### 7.1 GET `/api/web/timeline` (기존 유지)
- **용도**: 타임라인 그리드 데이터 조회 및 층 변경.
- **파라미터**: `asset_id` (선택, 정수)
- **응답**: `rooms` 목록에 `is_available_now`, `next_reservation_start`, `available_until`, `available_minutes`가 보강되어 초기 부트스트랩 시 NOW 모드가 추가 네트워크 요청 없이 즉시 렌더링됨.

### 7.2 GET `/api/web/availability` (신규 추가)
- **용도**: WHEN 모드 회의실 가용성 구간 조회.
- **파라미터**:
  - `asset_id` (선택, 정수): 조회할 위치/층 ID (기본값: 첫 번째 에셋)
  - `start` (선택, 문자열): 시작 시각 `HH:MM` (기본값: `"14:00"`)
  - `duration_minutes` (선택, 정수): 예약 희망 시간(분) (기본값: `60`)
- **응답 구조**:
  ```json
  {
    "date": "2026-10-23",
    "date_display": "2026년 10월 23일 (금)",
    "start_time": "14:00",
    "end_time": "15:00",
    "duration_minutes": 60,
    "assets": [
      {"id": 70, "name": "[판교] 7층 회의실", "short_label": "7층 회의실", "selected": true}
    ],
    "selected_asset": {
      "id": 70,
      "name": "[판교] 7층 회의실",
      "short_label": "7층 회의실"
    },
    "rooms": [
      {
        "id": 170,
        "name": "회의실 7-1",
        "capacity": 6,
        "favorite": true,
        "available": true,
        "status_text": "사용 가능"
      }
    ],
    "total_rooms": 6,
    "available_rooms_count": 5
  }
  ```
  *(텔레그램 전용 마크다운, 이모지 문자열이 배제된 순수 구조화 DTO)*

---

## 8. Mobile & Desktop UX 반응형 설계

1. **상단 컨트롤 계층 분리**:
   - 1행: 3-Mode 세그먼트 버튼 (`[🟢 지금] [🕐 언제] [📊 전체]`)
   - 2행: 층 선택 드롭다운 + 즐겨찾기 토글 + 상태 칩 (`🟢 지금 사용 가능: 5 / 6개`)
   - 3행 (WHEN 모드 시에만 노출): 시작 시각 셀렉트 (`08:00 ~ 19:30`) + 사용 시간 캡슐 버튼 (`30분`, `1시간`, `1시간 30분`, `2시간`)
2. **뷰포트 대응 (360px, 390px, 430px, Desktop)**:
   - 모바일 좁은 화면(360px~430px)에서는 카드 그리드가 1열로 유려하게 배치되며 터치 타깃 최소 44px 준수.
   - 태블릿/데스크톱에서는 `cards-grid`가 다열 자동 확장(최대 폭 1200px 중앙 정렬).
3. **가벼운 로딩 및 에러 상태**:
   - 비동기 페치 시 `불러오는 중...` 스피너 칩 노출로 무반응 오인 방지.
   - 네트워크 단절 시 무한 재시도를 방지하고 명시적 `[다시 시도]` 버튼 제공.

---

## 9. 보안 및 플랫폼 독립성 (Security & Platform Independence)

1. **XSS 방지 강화**:
   - 서버 부트스트랩 데이터 삽입 시 Jinja2 `tojson` 필터를 사용하여 `</script><script>` 브레이크아웃 원천 차단.
   - 클라이언트 DOM 생성 시 `document.createElement`, `textContent`, 그리고 `escapeHtml()`을 엄격히 적용.
2. **인증 및 자격증명 격리**:
   - Groupware 로그인 비밀번호, 토큰 원문 등은 HTML, JS, API 어디에도 노출되지 않음.
   - `HttpOnly`, `SameSite=Lax`, `meetingroom_web_session` 쿠키를 통한 안전한 세션 검증.
3. **Zero Telegram Dependency**:
   - Web App 내부에 `Telegram.WebApp`, `telegram-web-app.js`, `initData`, `MainButton`, `BackButton`, `HapticFeedback` 등 텔레그램 전용 API 의존성이 **0개**임을 검증.
   - 브라우저 단독(Safari, Chrome, Mobile Web)에서도 독립적으로 완벽 동작.

---

## 10. 향후 단계 (Phase 2.3B)

- **Phase 2.3B Telegram Mini App Adapter**:
  - Web App 자체를 수정하지 않고, Telegram Mini App 컨텍스트 진입 시 동작하는 경량 어댑터 스크립트 추가.
  - `initData` 무결성 검증, 텔레그램 테마 색상(CSS variables) 동기화, 모바일 HapticFeedback 및 Viewport 자동 확장 연동.
