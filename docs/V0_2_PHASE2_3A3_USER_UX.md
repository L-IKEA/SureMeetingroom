# SureMeetingRoom Bot v0.2 - Phase 2.3A-3 Meeting Room Web App User UX Completion

**문서 상태**: Approved (v0.2 User UX Completion Baseline)  
**기준 커밋**: `fed9b037b70331288ff95db048377e74968b0f2e`  
**브랜치**: `feature/v0.2-platform-abstraction`  
**작성일**: 2026-10-26  

---

## 1. 개요 및 목적 (Overview & Goals)

Phase 2.3A-3의 핵심 목적은 **SureMeetingRoom Web App의 사용자 기능과 UX를 완성**하는 것입니다.  
텔레그램 챗봇 환경을 넘어 단일 반응형 웹 인터페이스에서:
1. **4대 View Mode 완성**: `[🟢 지금]`, `[🕐 언제]`, `[👤 누가]`, `[📊 타임라인]`
2. **전체 위치 (All Locations) 지원**: 층/위치 드롭다운 최상단에 `[전체 위치]`를 추가하여 전사 모든 회의실을 단일 뷰에서 탐색
3. **"누가" (WHO) View Mode 신설**: 오늘 회의실 예약을 "사람(예약자)" 중심으로 빠르게 확인하고 실시간 한글 부분 일치 검색 제공
4. **예약자명 및 회의명 기본 표시**: 사내 파일럿 정책에 따라 예약자 및 회의명을 안전하게 표시
5. **모바일 360px 뷰포트 최적화**: 4개 모드 탭이 줄바꿈 없이 미려하게 동작하는 반응형 세그먼트 컨트롤 구축
6. **비동기 경쟁 상태 및 플랫폼 독립성 보존**: Request sequence, AbortController, Shared Core 서비스 재사용 및 텔레그램 비의존 구조 유지

*(※ 본 단계에서는 Telegram Mini App 연동, Kakao 연동, 예약 생성/취소 기능은 구현하지 않으며 Web App 자체의 UX 완결성에 집중합니다.)*

---

## 2. 4대 View Mode 구조 및 명칭 정립

기존 3개 모드 `[🟢 지금] [🕐 언제] [📊 전체]` 체계에서 모호했던 "전체"라는 명칭을 제거하고, 4개 모드로 확장 및 명확화하였습니다:

| View Mode | UI 탭 버튼 | 내부 ID | 목적 및 특징 | Empty State 문구 |
|---|---|---|---|---|
| **NOW** | `[🟢 지금]` | `#mode-now-btn` | 현재 시각 기준 즉시 사용 가능한 회의실 카드 목록 | "현재 사용 가능한 회의실이 없습니다." |
| **WHEN** | `[🕐 언제]` | `#mode-when-btn` | 지정 시간 구간(예: 14:00~15:00) 전체 동안 비어 있는 회의실 | "선택한 시간에 사용 가능한 회의실이 없습니다." |
| **WHO** | `[👤 누가]` | `#mode-who-btn` | 오늘 예약을 예약자 중심으로 확인 및 실시간 검색 | "검색한 예약자를 찾을 수 없습니다." / "오늘 예약이 없습니다." |
| **TIMELINE** | `[📊 타임라인]` | `#mode-timeline-btn` | 08:00~20:00 전체 회의실 예약 타임라인 그리드 시각화 | "오늘 예약이 없습니다." / "이 위치에 등록된 회의실이 없습니다." |

> **명칭 구분 원칙**:
> - **View Mode**: 기존 `전체` -> **`타임라인`**으로 변경 (`#mode-timeline-btn`)
> - **Scope Filter**: `[전체]` vs `[⭐ 즐겨찾기]`의 **`전체`**는 즐겨찾기 해제 범위를 의미하므로 그대로 유지 (`#filter-all-btn`)

---

## 3. 전체 위치 (All Locations) 설계 및 State 관리

### 3.1 명시적 Scope 모델 (`"all"`)
- 드롭다운 최상단에 `<option value="all">전체 위치</option>`를 동적으로 배치합니다.
- HTML이나 JS에 자산(Asset) 목록을 하드코딩하지 않고 Provider/Service에서 동적으로 받아와 prepend 합니다.
- 실제 그룹웨어 Asset ID와 충돌하지 않도록 ID `0` 같은 가짜 숫자로 가장하지 않고, 명시적 문자열 `"all"`로 관리합니다.

### 3.2 View Mode별 전체 위치 동작

1. **전체 위치 + NOW**:
   - 전사 모든 층/Asset의 현재 빈 회의실을 조회합니다.
   - 각 회의실 카드에 `[판교 7층]`, `[판교 5층]` 등 위치/층 배지(`.location-badge`)를 표시하여 동명 회의실 간 혼동을 방지합니다.
2. **전체 위치 + WHEN**:
   - 전사 모든 Asset에 걸쳐 지정 시간 구간(시작 시각 + 사용 시간) 동안 단 1분도 경합하지 않는 회의실을 조회합니다.
   - 기존 `AvailabilityService` 무경합 알고리즘을 100% 재사용하며, 회의실 카드에 위치/층 배지와 정원을 함께 표시합니다.
3. **전체 위치 + TIMELINE**:
   - 모바일 환경에서 전사 모든 회의실을 단순 나열하면 과도한 스크롤 및 층간 구분 모호성이 발생하므로, Asset/층 단위 섹션 헤더(`.timeline-asset-section-header`)를 삽입하여 층별로 시각적으로 그룹화합니다.
   - 특정 단일 Asset 선택 시의 기존 타임라인 그리드 UX는 온전히 유지됩니다.
4. **전체 위치 + WHO**:
   - 전사 모든 회의실의 오늘 예약 목록을 수집하여 예약자 중심으로 나열합니다.

---

## 4. "누가" (WHO) View Mode 상세

### 4.1 목적 및 UX 설계
- 특정 동료가 어느 회의실에서 회의 중인지, 혹은 특정 미팅의 예약자가 누구인지 빠르게 찾기 위한 사람 중심 뷰입니다.
- 결과 카드에는 **예약자명**, **회의 시간**, **위치/층 배지 및 회의실명**, **회의명**을 한눈에 식별할 수 있도록 배치합니다.

### 4.2 한글 실시간 부분 일치 검색
- 상단에 검색 바(`.who-search-bar`)를 제공: `[ 🔍 예약자 이름 검색... ]`
- 한글 이름(예: `홍길동`) 및 영문 이름에 대해 대소문자 무관(case-insensitive) 부분 문자열 매칭을 수행합니다.
- 키 입력마다 과도한 API 호출이 발생하지 않도록 **300ms Debounce**(`whoSearchDebounceTimer`)를 적용하였습니다.
- 검색 입력창 우측에 빠른 입력 지움 버튼(`.search-clear-btn`)을 제공합니다.
- 검색 결과가 없는 경우 자연스러운 빈 상태 안내(`"검색한 예약자를 찾을 수 없습니다."`)를 노출합니다.

### 4.3 WHO + 위치 Scope & 즐겨찾기 연동
- **위치 Scope**: 위치 드롭다운이 `전체 위치`일 때는 전사 예약, `판교 7층`일 때는 7층 회의실 예약만 필터링합니다.
- **즐겨찾기 Scope**: WHO 모드에서 `[⭐ 즐겨찾기]`가 활성화되면 **사용자가 즐겨찾기한 회의실의 예약만** 필터링되어 표시됩니다. (사람 즐겨찾기가 아닌 회의실 즐겨찾기 정책 일관성 유지)

---

## 5. 실제 Groupware 필드 매핑 및 개인정보 보안 정책

### 5.1 실제 Groupware `daily.json` 구조 기반 필드 매핑
그룹웨어 실제 API 응답 구조를 분석하여 정확한 1순위 authoritative source와 fallback compatibility를 정립하였습니다:

1. **예약자명 (`reserver_name`) 매핑 우선순위**:
   - **1순위 (Authoritative)**: `res_dict["user"]["name"]`
   - **Fallback 1**: `properties` 배열 중 `attributeId == 51`의 `content`
   - **Fallback 2 (Legacy / Mock 호환)**: `userName`, `empName`, `reserverName`, `registerName`, `writer`
   - *우선순위 원칙*: `user.name`이 존재하면 property 51의 값(예: 부서명/별칭 "개발팀")과 다르더라도 반드시 `user.name`(예: "김철수")을 최종 예약자명으로 확정합니다.

2. **회의명 (`meeting_title`) 매핑 우선순위**:
   - **1순위 (Authoritative)**: `properties` 배열 중 `attributeId == 50`의 `content` (예: `"주간 회의"`, `"스프린트 계획"`)
   - **Fallback (Legacy / Mock 호환)**: `title`, `subject`, `meetingTitle`, `scheduleTitle`

3. **익명 예약 (`useAnonym`) 보호 정책**:
   - 실제 그룹웨어 응답의 `useAnonym` 필드가 `true`인 경우:
     - Web App에서 원본 예약자명 및 회의명을 강제 노출하지 않고 `reserver_name = "비공개"`, `meeting_title = "비공개"`로 마스킹합니다.
     - 개인정보 및 사내 비공개 미팅의 보안 정책을 철저히 준수합니다.

4. **표시 정책 기본값**:
   - 사내 파일럿 기본값 설정:
     ```python
     SHOW_RESERVER_NAME = True
     SHOW_MEETING_TITLE = True
     ```
   - 데이터 부재 시 `"예약자 정보 없음"`, `"회의명 없음"`으로 자연스럽게 fallback 처리합니다.

5. **위치 Label 일관성 및 상세 Modal 이중 괄호 방지**:
   - 전체 위치(All Locations) 모드에서 생성된 라벨(`"[판교] 7층"`, `"[대전] 회의실"`)이 상세 바텀시트 모달(`openDetailModal`)에서 `[[판교] 7층]`처럼 이중 괄호로 감싸지지 않도록 라벨 포매터 반환값을 그대로 바인딩합니다.
   - 단일 자산 뷰에서는 컴팩트 라벨(`"7층 회의실"`, `"회의실"`)로 표시되며, 모달 메타는 `${locLabel} · ${capPart}` (예: `[판교] 7층 · 정원: 6인실`, `7층 회의실 · 정원: 6인실`)로 깔끔하게 렌더링됩니다.

### 5.2 보안 및 기밀 보호
- **토큰/쿠키 유출 원천 차단**: Groupware ID/PW, GOSSOcookie, WebSession ID, LinkSession ID, Telegram Bot Token 등 민감한 인증 정보는 Web App API 응답에 절대 포함되지 않습니다. (Secret Scan 100% Clean)
- **XSS 방어 체계**: 사용자 입력(검색 쿼리) 및 외부 그룹웨어 데이터(`reserver_name`, `meeting_title`, `room_name`, `asset_name`)는 HTML에 직접 삽입하지 않고 `textContent`, `safe DOM API`, Jinja2 `tojson`을 통해 엄격히 이스케이프하여 DOM Injection을 원천 차단합니다.

### 5.3 성능 및 실데이터 검증 주의사항 (Performance Note)
- **Known Validation Item**: 전체 위치(All Locations) 모드는 전사 Asset(13개 층/구역)을 순회하므로 실제 Groupware 환경에서는 API 호출 수가 증가합니다.
- 본 단계에서는 `requests.Session` 동시성 및 사내 그룹웨어 서버 부하 안정성을 고려하여 무리한 multithreading을 도입하지 않았으며, **"전체 위치 실데이터 성능은 Local Real-mode Smoke에서 확인 필요"**를 주요 검증 항목으로 관리합니다.

---

## 6. Backend API 아키텍처

플랫폼 독립적인 구조적 JSON을 반환하는 신규 엔드포인트를 구현하였습니다:

### `GET /api/web/reservations`
- **Query Parameters**:
  - `asset_id`: 특정 자산 ID 또는 `"all"` (전체 위치)
  - `query`: 예약자 이름 검색어 (선택 사항)
  - `favorite_only`: 즐겨찾기 회의실만 포함 여부 (`true` / `false`)
- **Response Schema**:
  ```json
  {
    "reservations": [
      {
        "room_id": 701,
        "room_name": "회의실 7-1",
        "asset_id": 70,
        "asset_name": "[판교] 7층 회의실",
        "asset_short_label": "판교 7층",
        "start": "14:00",
        "end": "15:00",
        "reserver_name": "홍길동",
        "meeting_title": "VCU 검증 회의",
        "favorite": true
      }
    ],
    "selected_asset": {
      "id": "all",
      "name": "전체 위치",
      "short_label": "전체 위치"
    },
    "assets": [...],
    "query": "홍길동",
    "total_count": 1
  }
  ```
- 텔레그램 포맷팅 텍스트를 포함하지 않는 순수 데이터 모델입니다.

---

## 7. Shared Core 재사용 및 비동기 경쟁 상태 보호

### 7.1 Core 서비스 무중복 재사용
- 회의실 가용성 판정: `AvailabilityService` (NOW, WHEN 공통)
- 즐겨찾기 조회 및 관리: `FavoriteService` (Web App 및 Telegram 봇 공유)
- 데이터 공급자 계층: `BaseMeetingRoomProvider` -> `MockMeetingRoomData` / `RealGroupwareProvider`
- 웹 프레젠테이션 계층에 독자적인 overlap 알고리즘을 중복 구현하지 않고 Shared Core를 100% 호출합니다.

### 7.2 Async Race Protection (Last User Intent Wins)
- 4개 모드 및 전체 위치 전환, 빠른 검색어 입력 시 발생할 수 있는 Out-of-Order 네트워크 응답 덮어쓰기 방지:
  - Sequence counters: `timelineRequestSeq`, `whenRequestSeq`, `whoRequestSeq`
  - AbortControllers: `timelineAbortController`, `whenAbortController`, `whoAbortController`
  - Active request counter: `activeRequestsCount` (네트워크 인디케이터 연동)
- 응답 수신 시 `requestSeq !== currentSeq || requestedAssetId !== currentAssetId` 조건을 검증하여 지연 도착한 이전 응답을 안전하게 무시합니다.

---

## 8. 모바일 반응형 UI (360px 최적화)

상단 탭이 4개로 증가함에 따라 초소형 모바일 화면(360px ~ 380px)에서도 레이아웃이 깨지지 않도록 CSS 디자인을 정밀 조정하였습니다:
- 네비게이션 컨테이너 max-width 560px 설정 및 `display: flex; gap: 4px;`
- `@media (max-width: 380px)`:
  - `font-size: 0.8rem`, `padding: 8px 4px`
  - `white-space: nowrap` 적용으로 탭 텍스트 줄바꿈 방지
  - 세그먼트 버튼 너비 균등 배분(`flex: 1`)
- 스크린 리더 및 키보드 접근성: `native button` 사용, `aria-pressed` / `aria-selected` 속성 유지, 검색 input의 `aria-label` 부여.

---

## 9. 테스트 및 검증 결과

### 9.1 Pytest 전체 테스트 스위트
- **Baseline**: 302 passed, 0 failed, 0 skipped
- **Phase 2.3A-3 신규 테스트**: 38개 추가 (`tests/test_phase2_3a3_user_ux.py`)
  - 4개 View Mode 및 네비게이션 라벨 검증
  - 전체 위치 (All Locations) 옵션, NOW, WHEN, WHO 연동
  - WHO 모드 예약자 목록, 한글 이름 검색, 부분 일치, 빈 상태
  - WHO + Asset + Favorites 필터링
  - 예약자명/회의명 표시 및 XSS 공격 방어 (스크립트/이미지 태그 안전 처리)
  - 세션 쿠키 및 토큰 미유출 검증
  - 비동기 경쟁 상태 및 시퀀스 보호
  - 실제 Groupware daily.json 중첩 user.name 1순위 매핑
  - properties attributeId 50 회의명 1순위 매핑
  - user.name vs property 51 우선순위 (user.name 엄격 우선)
  - properties/user 부재 시 legacy 필드 안전 fallback
  - useAnonym=True 시 '비공개' 마스킹 정책
  - 전체 위치 판교/대전 지역명 보존 라벨 헬퍼 검증
- **최종 결과**: **340 passed, 0 failed, 0 skipped (100% PASS)**

### 9.2 UX Smoke Test (Scenarios A ~ P)
`scripts/smoke_test_phase2_3a3.py`를 통해 총 16개 UX 시나리오 전체 PASS:
- **Scenario A**: NOW 모드 즉시 가용 회의실 판정
- **Scenario B**: WHEN 모드 구간 무경합 가용성 검증
- **Scenario C**: Universal 즐겨찾기 스코프 토글
- **Scenario D**: Asset / 층 드롭다운 전환
- **Scenario E**: TIMELINE 모드 그리드 및 바텀시트 예약 상세
- **Scenario F**: 빈 상태(Empty States) 핸들링 (NOW, WHEN, WHO, Favorites)
- **Scenario G**: Cross-Mode Asset State 일관성
- **Scenario H**: Async Race & Out-of-Order 보호
- **Scenario I**: 전체 위치 + NOW 모드 (위치 배지 노출)
- **Scenario J**: 전체 위치 + WHEN 모드 (전사 구간 검색)
- **Scenario K**: WHO 모드 전체 예약자 목록
- **Scenario L**: WHO 모드 한글 이름 검색 (홍길동 등)
- **Scenario M**: WHO + Asset + Favorites 복합 필터
- **Scenario N**: TIMELINE 라벨 변경, Scope 전체 유지, 360px 모바일 레이아웃
- **Scenario O**: 실제 Groupware daily.json 구조 매핑, user.name 우선순위, useAnonym 마스킹
- **Scenario P**: 전체 위치 판교/대전 지역명 보존 배지 라벨 검증

---

## 10. 향후 로드맵 (Phase 2.3B)

Phase 2.3A-3으로 완성된 Web App은 다음과 같은 구조로 다음 단계인 **Phase 2.3B**에 연동될 준비가 완료되었습니다:
- **Phase 2.3B Telegram Mini App Adapter**:
  - `window.Telegram.WebApp` SDK 감지 및 `initDataUnsafe` 검증
  - 텔레그램 테마 파라미터(`themeParams`) 동적 연동
  - 텔레그램 봇 메인 메뉴의 Web App 인라인 버튼 연동
  - 플랫폼 독립적인 현재 Web App 코어는 변경하지 않고 외곽 Adapter 계층만 추가
