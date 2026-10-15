# SureMeetingRoom Bot v0.2 Phase 2: Production Deployment Decision & HTTPS Account Linking Plan

**문서 버전**: v1.0  
**작성일**: 2026-10-15  
**대상 브랜치**: `feature/v0.2-platform-abstraction`  
**기준 커밋**: `4c771c2966f881c4aba626df8abadf921fcff0fb` (v0.2 Pre-Phase 2 Date Fix 완료 시점)  
**상태**: Phase 2 설계 및 운영 의사결정 계획 확정 (구현 착수 전)  

---

## 1. Current Deployment Architecture (현재 로컬 실행 구조 분석)

현재 SureMeetingRoom Bot의 로컬 실행 구조(`scripts/run_local_app.py`)는 단일 Python 프로세스 내에서 Telegram Polling 봇과 FastAPI 웹 서버를 비동기 이벤트 루프로 동시 구동하는 형태입니다.

```text
+-----------------------------------------------------------------------------------------+
| Single Python Process (asyncio Event Loop)                                              |
|                                                                                         |
|  +-----------------------------------+     +-----------------------------------------+  |
|  |     Telegram Bot Application      |     |           FastAPI Web Server            |  |
|  |   (python-telegram-bot Polling)   |     |                (Uvicorn)                |  |
|  +-----------------+-----------------+     +--------------------+--------------------+  |
|                    |                                            |                       |
|                    v                                            v                       |
|  +-----------------------------------------------------------------------------------+  |
|  |                       In-Memory Shared Singletons                                 |  |
|  |                                                                                   |  |
|  |   1. session_manager (UserSessionManager)                                         |  |
|  |      - storage_key -> GroupwareClient (HTTP Session with GOSSOcookie)             |  |
|  |                                                                                   |  |
|  |   2. token_service (AccountLinkTokenService)                                      |  |
|  |      - token -> TokenData(user_id, expires_at, is_used)                           |  |
|  +-----------------+--------------------------------------------+--------------------+  |
+--------------------|--------------------------------------------|-----------------------+
                     |                                            |
                     v                                            v
         +-----------------------+                    +-----------------------+
         |  data/favorites.json  |                    |  Groupware API        |
         |  (Local File Repo)    |                    |  gw.suresofttech.com  |
         +-----------------------+                    +-----------------------+
```

### 1.1 Telegram Bot과 FastAPI의 세션 공유 방식
- **동일 프로세스 메모리 공유**: `run_local_app.py`에서 `create_app()`과 `build_application()`이 동일 인터프리터에서 실행됩니다.
- `src/meeting_room_bot/auth/session_manager.py`의 모듈 레벨 전역 객체 `session_manager = UserSessionManager()`를 양쪽에서 import하여 메모리 딕셔너리(`_sessions`)를 직접 공유합니다.
- **Account Linking 라이프사이클**:
  1. Telegram 핸들러가 미인증 상태(`QueryStatus.NOT_AUTHENTICATED`) 감지 시 `token_service.create_token(user_key)`로 1회성 토큰 발급.
  2. 사용자가 브라우저에서 `GET /link/{token}` 접속 -> `POST /link/{token}`으로 아이디/비밀번호 제출.
  3. FastAPI의 `process_login` 엔드포인트가 `GroupwareClient().login()`을 호출하여 인증 성공 시, `session_manager.set_client(user_id, client)`를 호출하여 메모리에 세션 등록.
  4. 사용자가 Telegram 봇으로 복귀하여 버튼을 누르면, Telegram 핸들러가 `session_manager.get_client(user_key)`를 조회하여 즉시 인증된 상태로 회의실 조회 수행.

### 1.2 로컬 개발 모드의 한계점
- **Localhost 제약**: `ACCOUNT_LINK_BASE_URL=http://localhost:8000` 환경에서는 모바일 텔레그램 인라인 버튼에 `http://localhost...` URL을 넣을 수 없음 (Telegram API 규격상 localhost/IP URL 버튼 전송 시 `BadRequest` 에러 발생). 따라서 현재는 터미널 로그에 URL을 출력하고 PC 브라우저로 복사/붙여넣기하는 방식을 취하고 있음.
- **프로세스 수명 종속성**: 개발자 PC가 꺼지거나 프로세스가 종료되면 봇 응답이 중단되고 모든 인메모리 세션이 초기화됨.

---

## 2. Production Requirements (운영 환경 필수 조건)

실제 사내 임직원 대상 상시 운영을 위해 만족해야 하는 8대 핵심 요건은 다음과 같습니다:

| 번호 | 요구사항 | 운영 충족 조건 |
|---|---|---|
| **REQ-1** | **24시간 무중단 가동** | 개발자 PC 종료와 무관하게 서버/VM/컨테이너 인프라에서 데몬/서비스 형태로 상시 동작 |
| **REQ-2** | **다중 사용자 동시성** | 수십~수백 명의 사용자가 동시에 봇 쿼리 및 계정 연결을 진행해도 세션 오염/충돌 없음 (Phase 1 Stateless화 완료 검증됨) |
| **REQ-3** | **모바일 원클릭 계정 연결** | 스마트폰 텔레그램 앱의 인라인 버튼 클릭 시 외부 브라우저가 열려 로그인 완료 후 복귀 가능 |
| **REQ-4** | **공인 HTTPS 적용** | 모바일 브라우저 및 Telegram In-App Browser에서 보안 경고 없는 유효한 공인 SSL/TLS 인증서 통신 |
| **REQ-5** | **Groupware API 접근** | 봇 실행 인프라에서 사내 그룹웨어(`https://gw.suresofttech.com/api/*`)로의 원활한 HTTPS Egress 통신 |
| **REQ-6** | **사용자별 Session 격리** | `UserKey`(`telegram:123456`) 기반으로 HTTP 세션 및 인증 쿠키 완벽 분리 |
| **REQ-7** | **사용자별 Favorites 유지** | 서버 재시작 시에도 임직원이 등록한 즐겨찾기 회의실 목록 보존 |
| **REQ-8** | **민감정보 로그 미노출** | 봇 토큰, 그룹웨어 비밀번호, 세션 쿠키(`GOSSOcookie`, `connect.sid`) 일체 로그 출력 금지 |

---

## 3. Hosting Alternatives (인프라 호스팅 후보 비교)

> **보안 원칙**: 개인 소유 VPS나 개인 Cloud 계정은 임직원의 회사 그룹웨어 세션 및 인증 쿠키를 취급하므로 **운영 후보에서 완전 배제**합니다.  
> 인프라는 **사내 서버/VM**과 **회사 승인 공식 Cloud**의 2가지 경로로 한정하여 비교합니다.

| 평가 기준 | 후보 A: 회사 내부 서버 / 사내 VM | 후보 B: 회사 승인 Cloud (AWS/GCP 등) |
|---|---|---|
| **1. Groupware API 접근** | **최우수**: 사내망 내 위치하므로 방화벽 예외나 VPN 터널링 없이 즉시 연동 가능 | **보통**: 사내망 연동(Direct Connect, VPN) 또는 사내 방화벽에서 Cloud Egress IP 허용 필요 |
| **2. 외부 HTTPS 제공** | **보통**: DMZ 공인 IP 매핑, 사내 방화벽 Inbound 443 오픈 및 도메인 연결 승인 필요 | **최우수**: Route53/Cloud DNS + Managed ALB/CloudFront + ACM(자동 갱신 무료 인증서) 즉시 제공 |
| **3. Telegram Outbound** | 사내 보안 정책상 `api.telegram.org:443` 방화벽 아웃바운드 허용 필요 | NAT Gateway/인터넷 게이트웨이를 통해 즉시 아웃바운드 통신 가능 |
| **4. 향후 Kakao Inbound** | 카카오 i 오픈빌더 웹훅 수신을 위해 사내 DMZ 인바운드 443 포워딩 허용 필요 | API Gateway / ALB를 통해 즉시 공인 웹훅 엔드포인트 노출 가능 |
| **5. 보안 정책 부합성** | 그룹웨어 세션 데이터가 사내 물리 인프라 내부망에 머무르므로 사내 보안 규정상 가장 안전 | 회사 승인 CSP 계정 및 보안 규정(IAM, 암호화) 준수 심의 필요 |
| **6. 운영 비용** | 기존 유휴 서버/VM 활용 시 추가 인프라 비용 **0원** | ALB + NAT Gateway + 소형 인스턴스 기준 월 수만~십수만 원 인프라 비용 발생 |
| **7. 24시간 가동성** | 사내 전산실 항온항습/UPS 인프라 기반으로 안정적 | 클라우드 SLA(99.9%+) 기반의 최고 수준 고가용성 제공 |
| **8. 유지보수 공수** | OS 패치, SSL 갱신, 하드웨어 점검 등 자체 관리 공수 필요 | 매니지드 서비스 활용으로 인프라 관리 공수 최소화 |
| **9. Secret 관리** | 서버 내 권한 제한 파일(`.env`, chmod 600) 또는 사내 Vault | AWS Secrets Manager, SSM Parameter Store 등 IAM 연동 |

### 호스팅 종합 평가 및 권고
- **사내 전산망에서 DMZ 인바운드 443 및 아웃바운드 허용이 가능한 경우**: **후보 A(사내 서버/VM)**가 그룹웨어 연동 및 내부 보안 승인 측면에서 가장 단순하고 비용 효율적입니다.
- **사내 방화벽 정책상 외부 인바운드 유입이 엄격히 금지된 경우**: **후보 B(회사 승인 Cloud)**를 채택하고, Cloud와 사내 그룹웨어 간 Egress 연동을 승인받는 방식을 취합니다.

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
         | 3. HTTP Proxy Pass (Internal Port 8000)
         v
+-----------------------------------------------------------------------------------------+
| FastAPI Account Link Server                                                             |
|   - GET /link/{token} -> HTML 로그인 폼 렌더링                                          |
|   - POST /link/{token} -> Token 소각 및 Groupware API 인증 시도                         |
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

### 4.2 로컬 개발 모드와의 완벽한 공존 보장
- `src/meeting_room_bot/telegram/keyboards.py`의 `is_localhost_url()` 로직에 의해:
  - `ACCOUNT_LINK_BASE_URL=http://localhost:8000` 설정 시: 로컬 개발 모드로 자동 판별되어 URL 버튼 대신 안내 메시지 및 터미널 출력 유지.
  - `ACCOUNT_LINK_BASE_URL=https://<approved-domain>` 설정 시: 즉시 `InlineKeyboardButton(url=...)` 버튼 활성화.
  - 별도의 코드 수정 없이 환경변수 변경만으로 로컬/운영 환경이 매끄럽게 전환됩니다.

---

## 5. Ingress / Reverse Proxy Candidates

FastAPI 애플리케이션에 직접 공인 SSL 인증서를 바인딩하는 것은 보안 및 인증서 자동 갱신 측면에서 권장되지 않습니다. 앞단에 Ingress/Reverse Proxy 계층을 두어 TLS를 종단(Termination)하고 백엔드로 평문 HTTP(127.0.0.1:8000)를 전달하는 구조를 적용합니다.

| 구현 방식 | 적용 인프라 | 구성 및 동작 원리 | 장단점 |
|---|---|---|---|
| **1. Reverse Proxy (Nginx / Caddy)** | 사내 서버 / VM 또는 Cloud VM | - 서버 내에 Nginx 설치<br>- Let's Encrypt Certbot 연동으로 90일 자동 갱신<br>- 포트 80 접속 시 443으로 301 영구 리다이렉트<br>- `proxy_pass http://127.0.0.1:8000;`<br>- 프록시 헤더(`X-Forwarded-Proto`, `X-Forwarded-For`) 전달 | **장점**: 가장 널리 쓰이며 설정이 직관적, VM 1대에서 완결 가능.<br>**단점**: 웹서버 설정 및 SSL 갱신 cron 관리 필요. |
| **2. Managed Load Balancer (ALB / Cloud LB)** | 회사 승인 Cloud (AWS/GCP) | - Cloud Managed ALB 생성<br>- AWS Certificate Manager(ACM) 연동으로 관리형 SSL 발급<br>- 80 -> 443 리다이렉트 리스너 룰 설정<br>- 타겟 그룹(Target Group)으로 EC2/컨테이너 포트 8000 연결 | **장점**: 인증서 갱신/서버 관리 완전 자동화, WAF 연동 용이.<br>**단점**: ALB 고정 비용 발생. |
| **3. 회사 기존 Web Gateway** | 사내 전산망 / 사내 인프라 | - 회사 IT 전산팀이 운영 중인 중앙 Reverse Proxy/Gateway에 서브도메인 등록 요청<br>- 사내 공인 와일드카드 인증서 사용<br>- 봇 서버의 사내 IP:8000으로 라우팅 | **장점**: 자체 인증서 관리 불필요, 사내 보안 규정 100% 충족.<br>**단점**: 전산팀 티켓 요청 및 승인 일정 소요. |

---

## 6. Account Linking Security Gap Analysis (보안 갭 분석)

현재 `src/meeting_room_bot/account_link/` 및 관련 실제 소스코드를 점검한 보안 기능 분석 결과입니다.

| 보안 점검 항목 | 현재 상태 | 판정 분류 | 상세 현황 및 Phase 2 필요 조치 |
|---|---|:---:|---|
| **One-time Link Token** | 구현됨 | **Implemented** | `secrets.token_urlsafe(32)` 기반 암호학적 난수 토큰 생성. 1회 사용 시 소각 |
| **Token TTL** | 구현됨 | **Implemented** | 기본 600초(10분) 만료 적용. `now > expires_at` 시 무효화 |
| **Burn-on-use** | 구현됨 | **Implemented** | `consume_token()`을 통해 로그인 시도 즉시 `is_used = True` 처리 (재시도 불가) |
| **Replay Attack 방어** | 구현됨 | **Implemented** | 소각 및 TTL 검증으로 재전송 공격 원천 차단 |
| **Credential Logging 방지** | 구현됨 | **Implemented** | 로그인 시도 및 에러 시 패스워드 로깅 0건 유지. 세션 등록 시 식별자만 기록 |
| **Password Storage 금지** | 구현됨 | **Implemented** | 패스워드는 메모리 폼 데이터로 일시 전달될 뿐 디스크/DB 어디에도 저장되지 않음 |
| **Cookie/Session Handling** | 구현됨 | **Implemented** | `requests.Session` 객체를 메모리 내에만 보관. 민감 쿠키 파일 저장 없음 |
| **Session Expiration** | 구현됨 | **Implemented** | Groupware API 401 수신 시 세션 자동 파기 및 재인증 유도 흐름 완비 |
| **CSRF Protection** | 미구현 | **Required** | 현재 `<form method="POST">`에 CSRF 토큰 부재. 로그인 폼 렌더링 시 세션 토큰 연계 CSRF 검증 필드 추가 필요 |
| **Rate Limiting / Brute-force** | 미구현 | **Required** | `POST /link/{token}`에 대한 IP별/토큰별 시도 횟수 제한 없음. SlowAPI 또는 Sliding-window Rate Limiter 필수 |
| **HTTP -> HTTPS Enforcement** | 미구현 | **Required** | FastAPI 자체의 HSTS 헤더 및 프록시 레벨의 HTTPS 강제 리다이렉트 설정 필요 |
| **Proxy Headers Trust** | 미구현 | **Required** | Reverse Proxy 환경에서 클라이언트 실제 IP를 안전하게 식별하기 위한 `ProxyHeadersMiddleware` 설정 필요 |
| **UserKey 일관 전달** | 부분구현 | **Required** | `keyboards.py`에서 `token_service.create_token(str(user_id))` 호출 시 `UserKey` 객체를 일관되게 전달하도록 보완 |
| **Logout / Unlink 기능** | 미구현 | **Optional** | 사용자가 명시적으로 계정 연결을 끊을 수 있는 `/unlink` 명령 또는 버튼 (향후 추가 가능) |

---

## 7. Official SSO Considerations (공식 SSO 연동 검토)

- **현황**:
  - 현재 슈어소프트 그룹웨어(`https://gw.suresofttech.com`) 연동은 `POST /api/login`을 호출하여 `GOSSOcookie`를 수신하는 직접 인증 방식을 취하고 있습니다.
  - 사내 포털이나 그룹웨어가 SAML 2.0, OAuth 2.0 / OIDC, 또는 사내 통합인증 SSO API를 공식 지원하는지 여부는 아직 IT 전산팀을 통해 확인되지 않았습니다.
- **원칙 및 정책**:
  - **공식 SSO 최우선 원칙**: 사내에 공식 SSO(OAuth2/SAML)가 존재할 경우, 사용자에게 비밀번호를 입력받는 대신 회사 공식 SSO 페이지로 리다이렉트하는 방식을 우선 채택해야 합니다.
  - 현재의 직접 ID/PW 폼 방식은 공식 SSO가 부재하거나 연동이 제한될 때를 대비한 "표준 인증 어댑터"이며, 추후 SSO 확인 결과에 따라 `AuthAdapter`를 교체할 수 있는 유연한 설계를 유지합니다.

---

## 8. Persistence Decision (영속화 결정 및 전략)

### 8.1 세션 영속화 (Session Persistence) 보류
- **결정**: Phase 2에서는 Session DB(Redis/RDBMS/AES 암호화 필드)를 당장 도입하지 않습니다.
- **사유**:
  - 그룹웨어 인증 세션(`GOSSOcookie`)은 본래 수 시간~수 일 단위로 만료되며, 401 발생 시 재로그인이 필요합니다.
  - 봇 서버 배포나 재시작 시 인메모리 세션이 초기화되더라도, 사용자가 텔레그램에서 "🔐 계정 연결" 버튼을 1회 눌러 10초 만에 재인증할 수 있으므로, 초기 운영 파일럿 단계에서는 충분히 수용 가능합니다.
  - 불필요한 인프라 복잡도(외부 Redis 설치, 암호화 키 관리)를 유예하고 HTTPS 연결 안정성에 집중합니다.

### 8.2 즐겨찾기 영속화 (Favorites Persistence)
- **결정**: 즐겨찾기는 사용자가 설정한 개인 데이터이므로 서버 재시작 시에도 유지되어야 합니다.
- **전략**: 현재의 `data/favorites.json` 기반 `JsonFavoriteRepository`로 단일 서버 운영 환경의 영속성을 완전히 충족할 수 있습니다. 단, 동시 쓰기 파일 충돌을 방지하기 위한 파일 락(Lock) 보강만 소규모로 진행하고, 본격적인 DB 도입(SQLite/PostgreSQL)은 다중 인스턴스 스케일아웃 시점으로 유예합니다.

---

## 9. Local / Production Environment Configuration (환경 설정)

코드 수정 없이 환경변수 주입만으로 Local과 Production을 완벽하게 전환할 수 있도록 지원하는 표준 환경변수 명세입니다:

```ini
# ==============================================================================
# SureMeetingRoom Bot Environment Configuration
# ==============================================================================

# 1. Platform & Data Mode
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
TELEGRAM_DATA_MODE=real                                # "real" or "mock"

# 2. Account Linking & HTTPS Configuration
# Local Mode: http://localhost:8000
# Production: https://<approved-domain>
ACCOUNT_LINK_BASE_URL=https://meeting-link.suresofttech.com
ACCOUNT_LINK_HOST=0.0.0.0
ACCOUNT_LINK_PORT=8000
ACCOUNT_LINK_TOKEN_TTL=600                             # Token expiry in seconds (default 10m)

# 3. Security & Proxy Settings
FORWARDED_ALLOW_IPS=127.0.0.1                          # Trusted Reverse Proxy IP
RATE_LIMIT_LOGIN_PER_MINUTE=10                         # Brute-force throttling

# 4. Groupware Integration
GROUPWARE_BASE_URL=https://gw.suresofttech.com

# 5. Data Persistence
FAVORITES_FILE_PATH=data/favorites.json
```

---

## 10. Phase 2 Implementation Steps (구현 태스크 분할 제안)

코드 분석 결과에 따라 가장 안전하고 단계적인 4단계 구현 순서를 제안합니다:

```text
+-----------------------------------------------------------------------------------+
| Phase 2.1: Production Config & UserKey Flow Consolidation                         |
|   - Config 모듈 도입 및 ACCOUNT_LINK_BASE_URL / PROXY 설정 표준화                |
|   - keyboards.py와 handlers.py의 UserKey 일관 전달 정리                           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Phase 2.2: Account Link Security Hardening                                        |
|   - SlowAPI 기반 Rate Limiting (IP/토큰별 무차별 대입 방어)                       |
|   - Login Form CSRF Protection 강화                                               |
|   - Uvicorn ProxyHeadersMiddleware 및 Security Response Headers 추가              |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Phase 2.3: Ingress / HTTPS Staging Verification                                   |
|   - Reverse Proxy (Nginx/Caddy 또는 Local Mock TLS) 연동 테스트 환경 검증         |
|   - HTTP -> HTTPS 리다이렉션 및 X-Forwarded-Proto 정합성 확인                     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Phase 2.4: Mobile Telegram Account Linking Pilot                                  |
|   - 스마트폰 텔레그램 앱에서 "🔐 회사 계정 연결" 버튼 탭 E2E 파일럿               |
|   - 모바일 브라우저 로그인 -> 텔레그램 복귀 후 회의실 조회 동작 검증              |
+-----------------------------------------------------------------------------------+
```

---

## 11. Decisions Required From Company / User (회사/사용자 확인 필요 항목)

운영 배포 환경 구성을 위해 IT 인프라/보안 담당자 또는 프로젝트 의사결정권자로부터 확인받아야 할 5가지 항목입니다:

1. **호스팅 인프라 확정**:
   - 사내 전산실 VM 활용 vs 회사 승인 Cloud(AWS/GCP) 인프라 활용 여부
2. **공인 도메인 및 SSL 인증서 발급 주체**:
   - 사용할 서브도메인 명칭(예: `meeting-bot.suresofttech.com`) 및 인증서 발급 주체(전산팀 사내 와일드카드 인증서 vs Let's Encrypt 자동 갱신)
3. **네트워크 인바운드 방화벽 오픈**:
   - 외부 사용자의 모바일 접속을 위한 443 포트 포워딩 또는 기존 사내 Web Gateway 라우팅 지원 가능 여부
4. **사내 네트워크 아웃바운드 정책**:
   - 사내 서버 채택 시, 서버에서 텔레그램 서버(`api.telegram.org:443`)로의 HTTPS 아웃바운드 통신이 허용되는지 여부
5. **그룹웨어 공식 SSO 지원 여부**:
   - 그룹웨어 자체의 OAuth2/SAML 기반 공식 SSO 엔드포인트 존재 여부 및 사내 개발자 접근 권한 확인
