# SureMeetingRoom Bot v0.2 Phase 2: Production Deployment Decision & HTTPS Account Linking Plan

**문서 버전**: v1.1 (Phase 2.1 Production Foundation 반영)  
**작성일**: 2026-10-19  
**대상 브랜치**: `feature/v0.2-platform-abstraction`  
**기준 태그 / 커밋**:  
- Release Base Tag: `v0.1-local-mvp`  
- Task Base Commit: `79ecbe9506285866480a906c804aca49e2d79d66`  
**상태**: Phase 2.1 Production Foundation 완료 / 운영 의사결정 대기 (실제 Cloud/DNS/방화벽 변경 보류)  

---

## 1. Current Deployment Architecture & Single-Process Pilot Constraint

현재 SureMeetingRoom Bot의 실행 구조는 단일 Python 프로세스 내에서 Telegram Polling 봇과 FastAPI 웹 서버를 비동기 이벤트 루프(`asyncio`)로 동시 구동하는 형태입니다.

```text
+-----------------------------------------------------------------------------------------+
| Single Python Process (asyncio Event Loop) - [MANDATORY PILOT CONSTRAINT]               |
|                                                                                         |
|  +-----------------------------------+     +-----------------------------------------+  |
|  |     Telegram Bot Application      |     |           FastAPI Web Server            |  |
|  |   (python-telegram-bot Polling)   |     |      (Uvicorn: 1 Worker ONLY)           |  |
|  +-----------------+-----------------+     +--------------------+--------------------+  |
|                    |                                            |                       |
|                    v                                            v                       |
|  +-----------------------------------------------------------------------------------+  |
|  |                       In-Memory Shared Singletons                                 |  |
|  |                                                                                   |  |
|  |   1. session_manager (UserSessionManager) - in-memory dictionary                  |  |
|  |      - storage_key -> GroupwareClient (HTTP Session with GOSSOcookie)             |  |
|  |                                                                                   |  |
|  |   2. token_service (AccountLinkTokenService) - in-memory dictionary               |  |
|  |      - token -> TokenData(user_id, expires_at, is_used)                           |  |
|  |                                                                                   |  |
|  |   3. user_state_mgr (UserStateManager) - in-memory UI wizard state                |  |
|  +-----------------+--------------------------------------------+--------------------+  |
+--------------------|--------------------------------------------|-----------------------+
                     |                                            |
                     v (asyncio.to_thread)                        v (asyncio.to_thread)
         +-----------------------+                    +-----------------------+
         |  data/favorites.json  |                    |  Groupware API        |
         |  (Atomic File Repo)   |                    |  gw.suresofttech.com  |
         +-----------------------+                    +-----------------------+
```

### 1.1 Single-Process Pilot Constraint (단일 프로세스 운영 제약)
> [!IMPORTANT]
> **Production Pilot 제약사항**:
> 현재 아키텍처에서는 세션(`UserSessionManager`), 토큰(`AccountLinkTokenService`), 대화 상태(`UserStateManager`)가 모두 프로세스 인메모리 딕셔너리로 관리됩니다.
> 따라서 Production Pilot 환경에서는 반드시 다음 조건을 엄격히 유지해야 합니다:
> - **Server Instance = 1**
> - **Python Process = 1**
> - **Uvicorn Worker = 1** (`--workers 1` 필수)

**현재 금지 사항**:
- `uvicorn --workers 2` 이상 다중 워커 구동 금지
- 여러 Application Process / Daemon 분산 금지
- 다중 Container Replica (예: Kubernetes Deployment replicas > 1, ECS tasks > 1) 금지
- 복수 VM / Load Balanced 타겟 금지

**사유**:
Telegram Bot 핸들러가 토큰을 생성한 프로세스와 브라우저가 `/link/{token}` 요청을 전달받은 프로세스가 다르면, 인메모리 토큰을 찾지 못해 계정 연결이 실패합니다. 또한 로그인 완료 후 등록된 `GroupwareClient` 세션도 프로세스 간 공유되지 않습니다.

**향후 다중 인스턴스 스케일아웃 계획**:
다중 인스턴스/워커 구성은 향후 별도 Phase에서 **Shared TokenStore(Redis/DB)** 및 **Shared SessionStore(암호화된 세션 저장소)**를 도입한 이후에 활성화합니다.

---

## 2. Production Pilot Requirements (운영 환경 필수 조건)

사내 임직원 대상 상시 파일럿 운영을 위한 핵심 요건입니다:

| 번호 | 요구사항 | 파일럿 운영 충족 조건 |
|---|---|---|
| **REQ-1** | **24시간 무중단 가동** | 개발자 PC 종료와 무관하게 서버/VM 인프라에서 단일 프로세스 서비스 데몬 형태로 상시 동작 |
| **REQ-2** | **Pilot 사용자 격리 및 비차단 I/O** | `UserKey`(`telegram:123456`) 기반 완전 세션 격리 및 `asyncio.to_thread`를 통한 동기 I/O 격리로 다중 사용자 간 응답 지연 전파 방지 |
| **REQ-3** | **모바일 원클릭 계정 연결** | 스마트폰 텔레그램 앱의 인라인 버튼 클릭 시 외부 브라우저가 열려 로그인 완료 후 복귀 가능 |
| **REQ-4** | **공인 HTTPS 적용** | 모바일 브라우저 및 Telegram In-App Browser에서 보안 경고 없는 유효한 공인 SSL/TLS 인증서 통신 |
| **REQ-5** | **Groupware API 접근** | 봇 실행 인프라에서 사내 그룹웨어(`https://gw.suresofttech.com`)로의 원활한 HTTPS Egress 통신 (후보 호스트에서 실제 네트워크 테스트 필수) |
| **REQ-6** | **사용자별 Favorites 유지** | 서버 재시작 시에도 임직원이 등록한 즐겨찾기 목록 보존 (Atomic File Replace 및 손상 복구 적용) |
| **REQ-7** | **보안 및 민감정보 보호** | Referrer-Policy, Cache-Control no-store, Frame-ancestors none 적용 및 패스워드 로깅 0건 유지 |

---

## 3. Hosting Alternatives (인프라 호스팅 후보 비교)

> **보안 원칙**: 개인 소유 VPS나 개인 Cloud 계정은 임직원의 회사 그룹웨어 세션 및 인증 쿠키를 취급하므로 **운영 후보에서 완전 배제**합니다.  
> 인프라는 **사내 서버/VM**과 **회사 승인 공식 Cloud**의 2가지 경로로 한정하여 비교합니다.

| 평가 기준 | 후보 A: 사내 서버 / 사내 VM | 후보 B: 회사 승인 Cloud (AWS/GCP 등) |
|---|---|---|
| **1. Groupware API 접근성** | 사내망 내 위치할 가능성이 높아 연결이 수월할 수 있으나, **후보 호스트에서 실제 API 도달 가능 여부 네트워크 테스트(curl/ping) 필수** | VPC/NAT 또는 공인망을 통해 도달 가능한지 **후보 호스트에서 실제 네트워크 테스트 필수** (VPN/Direct Connect 필요 여부는 네트워크 테스트 결과에 따름) |
| **2. 외부 HTTPS 제공** | DMZ 공인 IP 매핑, 사내 방화벽 Inbound 443 오픈 및 도메인 연결 승인 필요 (또는 사내 기존 Web Gateway 활용) | Route53/Cloud DNS + Managed ALB + ACM(자동 갱신 무료 인증서) 즉시 제공 가능 |
| **3. Telegram Outbound** | 사내 보안 정책상 `api.telegram.org:443` 방화벽 아웃바운드 허용 필요 | NAT Gateway/인터넷 게이트웨이를 통해 아웃바운드 통신 가능 |
| **4. 보안 정책 부합성** | 그룹웨어 세션 데이터가 사내 물리 인프라 내부망에 머무르므로 사내 보안 승인에 유리 | 회사 승인 CSP 계정 및 보안 규정(IAM, 암호화) 심의 필요 |
| **5. 가동 제약** | Single-Process Pilot 제약(1 Instance, 1 Worker)을 준수하는 Systemd 데몬 운영 | 단일 컨테이너(replicas: 1) 또는 단일 VM 인스턴스로 제약 준수 |

---

## 4. HTTPS Architecture & Account Linking Target Flow

### 4.1 HTTPS 전환 목표 구조
- **기존 (로컬)**: `http://localhost:8000/link/<token>` (터미널 복사 방식)
- **운영 (HTTPS)**: `https://<approved-domain>/link/<token>` (텔레그램 인라인 버튼 클릭 방식)

```text
[Mobile Telegram App]
         |
         | 1. "🔐 회사 계정 연결" 버튼 탭 (InlineKeyboardButton url="https://<approved-domain>/link/<token>")
         v
[External Mobile Browser]
         |
         | 2. GET /link/{token} (HTTPS 443)
         v
+-----------------------------------------------------------------------------------------+
| Reverse Proxy / Ingress Gateway (SSL/TLS Termination)                                   |
|   - Domain: <approved-domain>                                                           |
|   - Valid Public SSL Certificate                                                        |
|   - HTTP -> HTTPS 301 Redirect                                                          |
|   - Header Injection: X-Forwarded-Proto=https, X-Forwarded-For                          |
+-----------------------------------------------------------------------------------------+
         |
         | 3. HTTP Proxy Pass (Internal Port 8000, 1 Uvicorn Worker)
         v
+-----------------------------------------------------------------------------------------+
| FastAPI Account Link Server                                                             |
|   - Response Headers: Referrer-Policy: no-referrer, Cache-Control: no-store, X-Frame-Options: DENY
|   - GET /link/{token} -> HTML 로그인 폼 렌더링                                          |
|   - POST /link/{token} -> Token 소각, IP Rate Limit 확인 및 Groupware API 로그인 (to_thread)
|   - 인증 성공 -> session_manager.set_client(user_key, client) 등록                      |
|   - 완료 페이지 렌더링 ("로그인 완료! 텔레그램으로 돌아가세요.")                        |
+-----------------------------------------------------------------------------------------+
         |
         | 4. UserKey 기반 세션 메모리 등록
         v
+-----------------------------------------------------------------------------------------+
| Telegram Bot Application (Same Process / Shared Memory)                                 |
|   - 사용자가 텔레그램으로 복귀하여 메뉴 버튼 탭                                         |
|   - session_manager.has_session(user_key) -> True 확인                                  |
|   - 회의실 현황 즉시 조회 성공                                                          |
+-----------------------------------------------------------------------------------------+
```

### 4.2 Account Link URL Token 노출 방지 설계 (URL Exposure Mitigation)
- **현재 구조와 위험**:
  현재 `https://<domain>/link/<token>` URL은 브라우저 히스토리, 웹 프록시 로그, 리퍼러 헤더 등에 잔존할 수 있는 잠재적 위험이 있습니다.
- **Phase 2.1 적용 보안 헤더 (Implemented)**:
  - `Referrer-Policy: no-referrer`: 타 사이트로 이동 시 토큰 URL 유출 방지
  - `Cache-Control: no-store, no-cache, must-revalidate`: 브라우저/프록시 디스크 캐싱 방지
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` 및 `Content-Security-Policy: frame-ancestors 'none'`: Clickjacking 방어
  - `<meta name="referrer" content="no-referrer">`: 템플릿 레벨 리퍼러 차단
  > [!NOTE]
  > **보안 한계 명시**: 위 보안 헤더는 브라우저 캐싱과 외부 리퍼러 유출을 차단하지만, 브라우저 주소창 자체나 Reverse Proxy 액세스 로그에 남는 토큰 문자열을 완전히 제거하지는 못합니다.
- **운영 목표 교환 아키텍처 (Planned Architecture / Phase 2.2)**:
  1. `GET /link/<token>` 요청 수신 시 토큰 검증
  2. 일회성 Secure / HttpOnly / SameSite 쿠키 또는 단기 서버 세션 state로 교환
  3. `303 See Other` 리다이렉트 -> `/link/login`
  4. 브라우저 주소창에서 원본 토큰 파라미터 완전 제거
  5. 웹서버 access log 포맷에서 `/link/` 경로의 토큰 마스킹 설정 적용

---

## 5. Blocking Groupware I/O Isolation & Error Classification

### 5.1 Blocking I/O Thread Pool Isolation (`asyncio.to_thread`)
- `GroupwareClient`는 `requests.Session` 기반의 동기 HTTP 클라이언트입니다.
- Telegram Polling 및 FastAPI는 단일 비동기 이벤트 루프(`asyncio`)에서 구동됩니다.
- **Phase 2.1 적용**:
  - 대규모 비동기 HTTP 라이브러리(httpx/aiohttp) 전면 재작성 대신, 안정성이 검증된 `asyncio.to_thread(...)`를 경계(boundary)에 적용했습니다.
  - 적용 경로:
    - FastAPI: `client.login`
    - Telegram 핸들러: `get_available_rooms_now`, `get_available_rooms_at`, `get_locations`, `get_location_status`, `get_room_detail`
  - 이를 통해 특정 사용자의 그룹웨어 API 응답이 수 초간 지연되더라도 다른 사용자의 독립 비동기 태스크(이벤트 루프)가 블로킹되지 않습니다.

### 5.2 정밀 에러 분류 (Auth Error vs General API Error)
- `GroupwareAuthError` (401/403):
  - 자격 증명 만료로 판단 -> `session_mgr.remove_session(user_id)` 호출하여 세션 정리 -> `QueryStatus.SESSION_EXPIRED` 반환.
- `GroupwareAPIError` (500, 일시적 응답 포맷 오류):
  - 일시적 서버 장애로 판단 -> 세션 보존 -> `QueryStatus.GROUPWARE_API_ERROR` 반환.
- `GroupwareNetworkError` (DNS/타임아웃/연결 끊김):
  - 네트워크 단절로 판단 -> 세션 보존 -> `QueryStatus.NETWORK_ERROR` 반환.

---

## 6. Favorites Data Safety & Atomic Replace

- 파일 경로: `FAVORITES_FILE_PATH` 환경변수로 주입 가능 (기본 `data/favorites.json`).
- 동시성 제어: Python `threading.RLock()`으로 메모리 상태 및 파일 I/O 동기화.
- **Atomic Replace**:
  1. 쓰기 시 임시 파일(`favorites.json.tmp.<pid>.<uuid>`)에 전체 JSON 직렬화.
  2. `file.flush()` 후 `os.fsync(file.fileno())`로 OS 디스크 버퍼 강제 동기화.
  3. `os.replace(temp_path, final_path)`를 호출하여 원자적(Atomic) 교체 완료 (비정상 종료 시에도 파일 손상 방지).
- **데이터 손상 방어**:
  - JSON 파싱 오류 발견 시 빈 파일로 덮어쓰지 않고 `.corrupted.<timestamp>` 파일로 백업 격리 후 안전한 복구 예외 처리.

---

## 7. Production Configuration Mapping (실제 코드 연결 현황)

문서상의 제안 설정과 실제 코드 연결 상태를 명확히 구분합니다:

| 환경변수 | 기본값 | 연결 상태 | 코드 반영 위치 |
|---|---|:---:|---|
| `TELEGRAM_BOT_TOKEN` | `""` | **연결됨** | `bot.py` |
| `TELEGRAM_DATA_MODE` | `"mock"` | **연결됨** | `bot.py` |
| `ACCOUNT_LINK_BASE_URL` | `"http://localhost:8000"` | **연결됨** | `handlers.py`, `keyboards.py`, `app.py` |
| `ACCOUNT_LINK_HOST` | `"0.0.0.0"` | **연결됨** | `run_local_app.py`, `config.py` |
| `ACCOUNT_LINK_PORT` | `8000` | **연결됨** | `run_local_app.py`, `config.py` |
| `ACCOUNT_LINK_TOKEN_TTL` | `600` | **연결됨** (Phase 2.1) | `token_service.py`, `config.py` |
| `FORWARDED_ALLOW_IPS` | `"127.0.0.1"` | **연결됨** (Phase 2.1) | `config.py`, `scripts/run_local_app.py` (Uvicorn `forwarded_allow_ips`) |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `10` | **연결됨** (Phase 2.1) | `app.py` (IP별 sliding window 제한) |
| `GROUPWARE_BASE_URL` | `"https://gw.suresofttech.com"` | **연결됨** (Phase 2.1) | `client.py`, `config.py` |
| `FAVORITES_FILE_PATH` | `"data/favorites.json"` | **연결됨** (Phase 2.1) | `json_repository.py`, `config.py` |

---

## 8. Authentication Architecture Status (인증 아키텍처 상태)

- **현재 구현 (Implemented)**:
  - 직접 ID/PW 폼 기반 GroupwareClient 로그인 (`POST /api/login` -> `GOSSOcookie` 수신).
  - One-time burn-on-use token 서비스.
  - UserKey namespace (`telegram:123456`) 온전 유지 및 세션 매핑.
- **계획된 아키텍처 (Planned Architecture)**:
  - `AuthAdapter` 추상화 인터페이스: 향후 사내 공식 SSO(OAuth2/SAML/OIDC) 승인 시 직접 로그인 폼을 대체하는 SSO Provider 모듈. (현재는 구체화 계획 단계이며 코드 미구현 상태)

---

## 9. Company Decision Gate (회사/IT 확인 필요 6대 결정 관문)

Phase 2.2 이후의 실제 외부 Production 배포를 진행하기 전에 반드시 회사 인프라/보안/IT 부서로부터 확정받아야 하는 6대 필수 의사결정 관문입니다:

```text
+---------------------------------------------------------------------------------+
|                         COMPANY DECISION GATE (6 Items)                         |
+---------------------------------------------------------------------------------+
| 1. 운영 서버 인프라:                                                            |
|    - 사내 전산실 VM 활용 가능 여부                                              |
|    - 회사 승인 공식 Cloud(AWS/GCP) 인프라 활용 가능 여부                         |
+---------------------------------------------------------------------------------+
| 2. 외부 HTTPS 수신 경로:                                                        |
|    - 서버에 공인 IP 및 인바운드 443 포트 오픈 가능 여부                          |
|    - 또는 회사 전산팀이 운영 중인 기존 Web Gateway / Reverse Proxy 연동 가능 여부|
+---------------------------------------------------------------------------------+
| 3. 공인 도메인 및 인증서:                                                       |
|    - 사용할 사내 공식 서브도메인 (예: meeting-link.suresofttech.com)            |
|    - SSL/TLS 인증서 발급/관리 주체 (전산팀 와일드카드 인증서 vs Let's Encrypt)  |
+---------------------------------------------------------------------------------+
| 4. Telegram 아웃바운드 허용:                                                    |
|    - 후보 운영 서버에서 api.telegram.org:443 HTTPS Outbound 통신 허용 여부      |
+---------------------------------------------------------------------------------+
| 5. Groupware API 네트워크 도달성:                                               |
|    - 후보 운영 서버 인프라에서 gw.suresofttech.com HTTPS API 접근 가능 여부     |
|      (후보 호스트 배치 후 실제 curl/API 도달성 테스트 수행)                     |
+---------------------------------------------------------------------------------+
| 6. 사내 계정 인증 정책:                                                         |
|    - 회사 그룹웨어 공식 OAuth2 / OIDC / SAML SSO 엔드포인트 지원 여부            |
|    - 자체 구축 웹 페이지에서 사내 그룹웨어 ID/PW 입력을 받아 처리하는 방식에     |
|      대한 사내 보안 정책 승인 여부                                              |
+---------------------------------------------------------------------------------+
```
> [!CAUTION]
> **원칙**: 위 6대 항목이 사내 유관 부서와의 협의를 통해 최종 결정되기 전에는, 실제 외부 Production 인프라 프로비저닝(서버 생성, 공인 도메인/DNS 변경, 방화벽 개방)을 착수하지 않습니다.
