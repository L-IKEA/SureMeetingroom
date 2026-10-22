# SureMeetingRoom Bot v0.2 Phase 2.2: Secure Account Linking & Web Session Foundation

**문서 버전**: v1.0  
**작성일**: 2026-10-23  
**대상 브랜치**: `feature/v0.2-platform-abstraction`  
**기준 태그 / 커밋**:  
- Release Base Tag: `v0.1-local-mvp`  
- Task Base Commit: `f03fb7522ff60d08a908a96753476080880c4349`  
**상태**: Phase 2.2 완료 (단일 프로세스 인메모리 세션 기반 완성, Timeline UI 본 개발은 Phase 2.3 예정)

---

## 1. 개요 및 목적 (Overview & Goals)

Phase 2.2의 목적은 **향후 `/timeline` 웹 인터페이스에서 활용될 안전한 웹 인증 세션 기반(Web Session Foundation)**을 마련하는 것입니다.

기존 v0.1/v0.2 Phase 2.1에서는:
- Telegram에서 발급된 일회용 토큰이 로그인 화면 및 POST 제출 URL(`https://<domain>/link/<token>`)에 지속적으로 노출되어 브라우저 히스토리나 로그에 잔존할 위험이 있었습니다.
- 로그인 성공 후에도 브라우저 세션이 발급되지 않아 웹 UI를 연계할 수 있는 기반이 없었습니다.

Phase 2.2에서는 다음을 구현하여 이 문제를 근본적으로 해결했습니다:
1. **토큰 즉시 소각 및 URL 제거 (303 Token Exchange Flow)**: 첫 GET 요청 즉시 일회용 토큰을 소각하고, 서버 인메모리 `LinkSession` 쿠키를 발급한 뒤 303 Redirect를 통해 주소창에서 토큰을 완전히 제거.
2. **CSRF 방어**: 암호학적 랜덤 토큰(`secrets.token_hex`)을 폼에 주입하고, 상수 시간 비교(`secrets.compare_digest`)로 검증.
3. **LinkSession과 WebSession의 명확한 분리**: 인증 전 임시 링크 세션과 인증 후 타임라인 접근용 영구 세션을 분리 관리.
4. **보호된 `/timeline` 플레이스홀더 및 `/logout` 엔드포인트**: 이중 세션(WebSession + GroupwareClient) 유효성 검증을 거치는 보호 경로 구축.

---

## 2. 전체 인증 흐름 (Complete Authentication & Token Exchange Flow)

```text
[Telegram User]
       |
       | 1. "🔐 회사 계정 연결" 탭
       |    (Handler가 AccountLinkTokenService.create_token(UserKey) 1회 호출)
       v
[External Browser]
       |
       | 2. GET /link/{one-time-token}
       v
+-----------------------------------------------------------------------------------------+
| FastAPI Server: exchange_token_and_redirect                                              |
|   - token_service.consume_token(token) 즉시 소각 (Burn-on-use)                           |
|   - LinkSession 생성 (session_id, user_key, csrf_token, expires_at: 300초)               |
|   - HttpOnly Cookie 발급: meetingroom_link_session=<opaque-session-id> (Path=/link)      |
|   - 303 See Other Redirect -> /link/login                                                |
+-----------------------------------------------------------------------------------------+
       |
       | 3. GET /link/login (토큰 문자열이 주소창에서 완전히 사라짐)
       v
+-----------------------------------------------------------------------------------------+
| FastAPI Server: get_login_page                                                          |
|   - meetingroom_link_session 쿠키 검증 및 LinkSession 조회                               |
|   - login.html 렌더링 (form action="/link/login", hidden input: csrf_token)              |
+-----------------------------------------------------------------------------------------+
       |
       | 4. 사용자 ID / PW 입력 후 Form 제출 (POST /link/login)
       v
+-----------------------------------------------------------------------------------------+
| FastAPI Server: process_session_login                                                   |
|   - LinkSession 쿠키 확인                                                               |
|   - secrets.compare_digest(session.csrf_token, form.csrf_token) 검증 (불일치 시 403 차단)|
|   - IP Rate Limit 확인 (request.client.host 기반)                                       |
|   - asyncio.to_thread(client.login, username, password) 비차단 그룹웨어 인증 시도       |
|   - [성공 시]                                                                           |
|       * session_manager.set_client(user_key, client) 등록                               |
|       * LinkSession 폐기 및 LinkSession 쿠키 삭제                                       |
|       * WebSession 생성 (session_id, user_key, expires_at: 86400초)                     |
|       * meetingroom_web_session 쿠키 발급 (Path=/, HttpOnly, SameSite=Lax)               |
|       * 303 See Other Redirect -> /timeline                                             |
|   - [실패 시]                                                                           |
|       * LinkSession 폐기 및 400 에러 페이지 (Telegram 재발급 안내)                      |
|       * 비밀번호/토큰은 파일, DB, 세션, 로그 어디에도 저장되지 않음                      |
+-----------------------------------------------------------------------------------------+
       |
       | 5. GET /timeline
       v
+-----------------------------------------------------------------------------------------+
| FastAPI Server: get_timeline_page (Protected Placeholder)                               |
|   - meetingroom_web_session 쿠키 확인                                                   |
|   - web_session_store 조회 (유효하지 않거나 만료 시 401 차단)                            |
|   - session_manager.has_session(user_key) 확인                                          |
|     (서버 재시작 등으로 그룹웨어 세션 유실 시 WebSession 즉시 폐기 및 401 차단)          |
|   - 모두 정상: "회의실 시간표 (Timeline UI는 Phase 2.3 제공 예정)" 플레이스홀더 렌더링   |
+-----------------------------------------------------------------------------------------+
```

---

## 3. 세션 모델 및 저장소 설계 (Session Models & Stores)

### 3.1 LinkSession vs WebSession 분리

| 구분 | `LinkSession` | `WebSession` |
|---|---|---|
| **목적** | 토큰 교환 후 로그인 폼 제출까지의 단기 인증 대기 상태 관리 | 로그인 완료 후 `/timeline` 등 웹 화면 접근 권한 유지 |
| **생성 시점** | `GET /link/{token}` 성공 시 | `POST /link/login` 그룹웨어 인증 성공 시 |
| **소각/폐기 시점** | 로그인 시도(성공/실패) 직후 즉시 소각 (1회용), 또는 만료 시 | `/logout` 호출 시, 또는 TTL 만료 시, 또는 서버 재시작 시 |
| **보유 데이터** | `session_id`, `user_key`, `csrf_token`, `expires_at` | `session_id`, `user_key`, `created_at`, `expires_at` |
| **기본 TTL** | 300초 (5분, `ACCOUNT_LINK_WEB_SESSION_TTL_SECONDS`) | 86400초 (24시간, `WEB_SESSION_TTL_SECONDS`) |
| **쿠키 이름** | `meetingroom_link_session` | `meetingroom_web_session` |
| **쿠키 Path** | `/link` (타 경로로 쿠키 불필요 전송 방지) | `/` (전체 웹 애플리케이션 범위) |

### 3.2 Opaque Session ID & UserKey 보호 원칙
- 브라우저 쿠키에는 **오직 암호학적으로 생성된 랜덤 문자열(`secrets.token_urlsafe(32)`)**만 저장됩니다.
- `UserKey`(`telegram:123456`)나 사용자 식별자 문자열은 쿠키에 절대 직접 들어가지 않으며, 서버 인메모리 딕셔너리에만 매핑됩니다.
- 비밀번호(Password)는 인증 과정에서 `GroupwareClient.login()` 호출에만 사용되며, `LinkSession`, `WebSession`, 로그, 파일 등에 절대 저장되거나 남지 않습니다.

---

## 4. CSRF 방어 정책 (CSRF Protection)

1. **CSRF 토큰 생성**:
   - `LinkSession` 생성 시 `secrets.token_hex(32)`로 256비트 암호학적 엔트로피를 가진 고유 CSRF 토큰 생성.
2. **Form 주입**:
   - `GET /link/login` 렌더링 시 `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` 필드로 전달.
   - CSRF 토큰을 URL 쿼리 파라미터로 노출하지 않음.
3. **POST 검증**:
   - `POST /link/login` 수신 시 `secrets.compare_digest(link_session.csrf_token, form_csrf_token)`으로 상수 시간 검증 수행.
   - 누락 또는 불일치 시 즉시 **HTTP 403 Forbidden** 응답을 반환하며, 그룹웨어 로그인 API를 일체 호출하지 않음.

---

## 5. 쿠키 보안 속성 및 Local vs Production 환경 제어

쿠키 보안 속성은 코드에 하드코딩되지 않고 `AppConfig.account_link_base_url`을 기준으로 동적으로 결정됩니다.

```python
@property
def is_secure_cookie(self) -> bool:
    return self.account_link_base_url.lower().startswith("https://")
```

| 속성 | Local 개발 환경 (`http://localhost:8000`) | Production 환경 (`https://...`) |
|---|---|---|
| `HttpOnly` | `True` (JavaScript의 `document.cookie` 접근 차단) | `True` (XSS 공격 방어) |
| `SameSite` | `Lax` (외부 사이트 통한 CSRF 방어) | `Lax` |
| `Secure` | **`False`** (HTTP 로컬 테스트 지원) | **`True`** (HTTPS 암호화 통신에서만 전송) |
| `Path` | `/link` (LinkSession) / `/` (WebSession) | `/link` (LinkSession) / `/` (WebSession) |

---

## 6. 보호된 Timeline 엔드포인트 및 이중 세션 검증

`GET /timeline` 접근 시 다음 이중 검증(Dual Validation)을 거칩니다:

1. **1차 검증 (WebSession)**:
   - `meetingroom_web_session` 쿠키를 추출하여 `web_session_store`에서 유효한 세션인지 확인.
   - 쿠키 부재 또는 세션 만료 시: **401 Unauthorized** ("인증되지 않은 접근입니다").
2. **2차 검증 (GroupwareClient Session in `session_manager`)**:
   - `session_manager.has_session(web_session.user_key)` 호출을 통해 실제 활성화된 사내 그룹웨어 세션이 존재하는지 확인.
   - **서버 재시작(Server Restart) 또는 401 만료로 인해 그룹웨어 세션이 유실된 경우**:
     - `web_session_store`에서 해당 세션을 즉시 무효화.
     - 브라우저 쿠키를 삭제 처리.
     - **401 Unauthorized** 반환 ("그룹웨어 세션이 만료되었습니다. 다시 계정을 연결해주세요").
3. **정상 인증 시**:
   - `timeline.html` 플레이스홀더 렌더링 (HTTP 200).
   - "회의실 시간표", "계정 연결이 완료되었습니다.", "Timeline UI는 다음 단계에서 제공됩니다." 안내 표시.
   - Phase 2.2에서는 예약 목록, 타임라인 그리드, 날짜 선택 등은 렌더링하지 않음.

---

## 7. 로그아웃 엔드포인트 (`POST /logout`)

- **HTTP Method**: `POST` (브라우저 prefetching이나 단순 링크 클릭으로 인한 파괴적 로그아웃 방지)
- **동작**:
  1. `request.cookies`에서 `meetingroom_web_session` 추출.
  2. `web_session_store`에서 세션 제거.
  3. `session_manager.remove_session(web_session.user_key)`를 호출하여 그룹웨어 HTTP 세션 완전 파기.
  4. 응답 헤더로 `meetingroom_web_session` 쿠키 만료(삭제) 전송.
  5. 303 Redirect -> `/link/login`.

---

## 8. 단일 프로세스 파일럿 제약 유지 (Single-Process Constraint)

> [!IMPORTANT]
> **Production Pilot 제약사항**:
> Phase 2.2의 `LinkSessionStore`와 `WebSessionStore`는 Pilot 단순성을 위해 프로세스 메모리(`dict`)로 관리됩니다.
> 따라서 Phase 2.1에서 확립한 단일 프로세스 제약이 계속 엄격하게 적용됩니다:
> - **Server Instance = 1**
> - **Python Process = 1**
> - **Uvicorn Worker = 1** (`--workers 1` 필수)
> 
> 서버가 재시작되면 모든 `WebSession`, `LinkSession`, `GroupwareClient`가 초기화되며, 사용자는 Telegram 봇을 통해 다시 계정을 연결해야 합니다.

---

## 9. 향후 Phase 2.3 Web Timeline UI 구현 계획

Phase 2.3에서는 본 세션 기반 위에 실제 타임라인 웹 인터페이스를 구축할 예정입니다:
1. **Shared Core / Provider 재사용**:
   - Web UI가 `GroupwareClient`를 ad-hoc으로 직접 호출하지 않고, 기존의 `MeetingRoomService` 및 Provider 계층(`RealMeetingRoomProvider`)을 재사용합니다.
2. **개인정보 보호 원칙 유지**:
   - Telegram 봇과 동일하게 타임라인 웹 뷰에서도 예약자 사번, 이름, 회의 제목, 개인 일정 정보는 마스킹하거나 표시하지 않으며, 오직 **"사용 중 / 예약 가능" 시간 블록**만 시각화합니다.
3. **타임라인 시간표 렌더러**:
   - 오늘/내일 날짜 탭, 층별/회의실별 가로형 시간표(10:00~19:00) 그리드 표시.
