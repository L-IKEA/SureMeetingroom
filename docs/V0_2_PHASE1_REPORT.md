# SureMeetingRoom Bot v0.2 Phase 1 결과 보고서
(Platform Abstraction & UserKey Decoupling)

**문서 상태**: Complete  
**기준 버전**: `v0.1-local-mvp` (Commit: `f214e39`)  
**작업 브랜치**: `feature/v0.2-platform-abstraction`  
**작성일**: 2026-10-15  

---

## 1. 변경 목적

v0.1-local-mvp는 로컬 단일 인스턴스 환경에서 Telegram Bot 및 Groupware API 연동과 사용자별 데이터 격리를 검증한 버전이었습니다. 그러나:
- 사용자 식별자가 텔레그램의 숫자형 `user_id`로 단일화되어 향후 카카오톡 챗봇 확장 시 네임스페이스 충돌 및 멀티플랫폼 식별의 한계가 존재했습니다.
- `providers/mock_provider.py`가 UI 계층인 `meeting_room_bot.telegram.mock_service`를 역참조하는 클린 아키텍처 위반이 존재했습니다.

이에 따라 v0.2 Phase 1에서는 **"기존 Telegram 기능을 100% 정상 유지하면서, 플랫폼 독립성을 확보하고 향후 카카오 및 운영 배포 확장을 위한 기초 추상화"**를 완료하는 것을 목표로 진행되었습니다.

---

## 2. 실제 변경 파일 목록

| 파일 경로 | 변경 구분 | 주요 변경 내용 |
|---|---|---|
| `src/meeting_room_bot/models/user_key.py` | **신규 생성** | 순수 채널 식별자 `UserKey(platform, platform_user_id)` 불변 데이터클래스 정의 (정규화/유효성 검증 내장) |
| `src/meeting_room_bot/models/__init__.py` | **수정** | `UserKey` 모듈 export 추가 |
| `src/meeting_room_bot/providers/mock_data.py` | **신규 생성** | 플랫폼 독립 Mock 데이터셋 분리 및 네임스페이스 보존 |
| `src/meeting_room_bot/providers/mock_provider.py` | **수정** | `telegram` 패키지 import 제거, UserKey 네임스페이스(`to_string()`) 완전 보존 |
| `src/meeting_room_bot/telegram/mock_service.py` | **수정** | `mock_data`의 목 데이터를 하위 호환 re-export |
| `src/meeting_room_bot/providers/base.py` | **수정** | `MeetingRoomQueryProvider` 인터페이스에 `UserKey` 지원 및 Transition Compatibility 명시 |
| `src/meeting_room_bot/providers/real_provider.py` | **수정** | 공유 mutable service 제거, UserKey 정규화 및 Stateless 호출 구조 확립 |
| `src/meeting_room_bot/services/meeting_room_service.py` | **수정** | FavoriteService 호출 시 `meeting_room_service=self` 명시적 전달 (Stateless 지원) |
| `src/meeting_room_bot/auth/session_manager.py` | **수정** | `UserKey` 플랫폼 격리 및 레거시 문자열 ID와의 양방향 호환 어댑터 구현 |
| `src/meeting_room_bot/favorites/repository.py` | **수정** | `FavoriteRepository` 인터페이스에 `Union[UserKey, str]` Transition Layer 명시 |
| `src/meeting_room_bot/favorites/json_repository.py` | **수정** | `_resolve_storage_key` 헬퍼를 통한 `UserKey` 및 레거시 JSON 키 호환 처리 |
| `src/meeting_room_bot/favorites/service.py` | **수정** | `__init__`에서 `meeting_room_service` 제거 및 `get_favorite_rooms` 호출별 서비스 전달 필수화로 완전 Stateless화 |
| `src/meeting_room_bot/account_link/token_service.py` | **수정** | 1회성 토큰 생성 시 `UserKey` 수용 및 직렬화 바인딩 |
| `src/meeting_room_bot/telegram/handlers.py` | **수정** | `update.effective_user.id`를 명시적 `UserKey("telegram", ...)`로 변환 후 Core에 전달 |
| `scripts/pack_review_bundle.py` | **신규 생성** | Review Bundle 자동 패키징, 정합성 검증, 독립 임시 환경 내 Self-Test 자동화 스크립트 |
| `tests/test_favorites.py` | **수정** | Stateless FavoriteService 인터페이스에 맞춰 per-call 서비스 전달로 갱신 (17개 테스트) |
| `tests/test_platform_abstraction.py` | **신규 생성** | UserKey 콜론/문자 검증, round-trip, 정규화, 동시성/Statelessness, Account Linking E2E 등 27개 단위 테스트 |
| `docs/V0_2_ARCHITECTURE_PLAN.md` | **수정** | UserKey 채널 식별자 정제, Ingress/Reverse Proxy 검토 표현 동기화 |
| `docs/V0_2_PHASE1_REPORT.md` | **수정** | Phase 1 Complete 보완 사항 및 184개 테스트 통과 결과 반영 |

---

## 3. UserKey 및 아키텍처 하드닝 (Final Hardening)

### 3.1 최종 `UserKey` 구조 및 정규화/유효성 검증
`UserKey`는 플랫폼상의 채널 사용자 식별자(`platform`, `platform_user_id`)만 표현하며, 생성 시 자동으로 canonical representation을 보장합니다.

```python
@dataclass(frozen=True)
class UserKey:
    """Platform-independent channel identity identifying a user within a messaging platform."""
    platform: str          # "telegram" | "kakao" (lowercase, stripped)
    platform_user_id: str  # "8296531540" | "k_hash_abc" (stripped string)

    def __post_init__(self):
        """Canonicalize and strictly validate platform and platform_user_id fields."""
        if not isinstance(self.platform, str):
            raise TypeError(f"platform must be a str, got {type(self.platform).__name__}")
        canon_platform = self.platform.strip().lower()
        if not canon_platform:
            raise ValueError("platform must not be empty")

        if self.platform_user_id is None:
            raise ValueError("platform_user_id must not be None")
        canon_user_id = str(self.platform_user_id).strip()
        if not canon_user_id:
            raise ValueError("platform_user_id must not be empty")

        object.__setattr__(self, "platform", canon_platform)
        object.__setattr__(self, "platform_user_id", canon_user_id)

    def to_string(self) -> str:
        return f"{self.platform}:{self.platform_user_id}"

    @classmethod
    def from_string(cls, raw: str, default_platform: str = "telegram") -> "UserKey": ...

    @classmethod
    def from_any(cls, val: Union["UserKey", str, int], default_platform: str = "telegram") -> "UserKey": ...
```

- **Canonicalization**: `UserKey(" Telegram ", 123)` 생성 시 자동으로 `UserKey("telegram", "123")`로 정규화되어 hash/equality 안정성이 100% 보장됩니다.
- **Strict Validation**: 
  - 플랫폼명에 콜론(`:`) 포함 시 `ValueError` 발생 (`to_string()`과 `from_string()`의 일대일 round-trip 분해 보장).
  - 플랫폼명에 허용되지 않는 특수문자 차단 (`^[a-z0-9_-]+$`, 영문 소문자/숫자/언더스코어/하이픈만 허용).
  - 빈 문자열(`""`, `"   "`)이나 `None` 입력 시 즉시 `ValueError`를 발생시켜 잘못된 식별자 생성을 원천 차단.

### 3.2 FavoriteService 완전 Stateless화 및 공유 mutable 상태 제거
- **기존 문제점**: `RealMeetingRoomProvider._get_service()`에서 싱글톤 `self.favorite_service.meeting_room_service = service`로 사용자별 서비스를 할당하여, 동시 요청 시 사용자 A의 요청에 사용자 B의 GroupwareClient가 오염될 수 있는 동시성 결함이 존재했습니다. 또한 `FavoriteService.__init__`에 레거시 `meeting_room_service` 인스턴스 변수가 남아 있었습니다.
- **완전 Stateless화 완료**:
  - `FavoriteService.__init__(repo)`만 남기고 `meeting_room_service` 인스턴스 속성을 완전 제거.
  - `FavoriteService.get_favorite_rooms(user_id, meeting_room_service)`에서 호출별 per-call service 전달을 필수화(`None` 전달 시 `ValueError`).
  - `RealMeetingRoomProvider` 및 `MeetingRoomService`에서 호출 시마다 사용자 인스턴스를 명시적으로 전달.
  - `MeetingRoomService`의 `get_available_favorite_rooms_now` 및 `get_available_favorite_rooms_at` 파라미터 타입을 `user_id: Union[UserKey, str]`로 정합성 보완.
  - 다중 사용자 교차 호출 동시성 테스트(`test_concurrent_users_no_shared_mutable_meeting_room_service`) 및 완전 무상태성 검증 테스트(`test_favorite_service_complete_statelessness`) 통과.

### 3.3 MockProvider 및 MockMeetingRoomData 네임스페이스 보존
- `MockMeetingRoomProvider`가 UserKey 수신 시 `user_id.platform_user_id`로 플랫폼을 절삭하던 문제를 해결하여 `user_id.to_string()`을 사용하도록 수정.
- `MockMeetingRoomData.has_favorites()` 및 `get_mock_favorites()`에서 불필요하게 `:` 기준으로 platform prefix를 제거하던 로직을 제거하여, Mock 환경에서도 `telegram:123`과 `kakao:123`이 서로 다른 독립 주체로 격리되도록 보장.

### 3.4 Account Linking E2E 검증 완료
- `account_link/app.py` 1-hop consumer와의 연동을 검증하는 통합 테스트(`test_telegram_user_key_account_linking_integration`) 추가.
- Telegram UserKey → 토큰 발급 → HTTP POST 로그인 → 세션 등록 → Telegram UserKey 조회 흐름이 완벽히 동작하며 Kakao와 네임스페이스가 격리됨을 입증.

### 3.5 Runtime Closure 패키징 및 Standalone Self-Test 검증
- Review Bundle 생성 시 5개 핵심 테스트가 단독 실행(`pytest`)될 수 있도록 최소 런타임 종속성(`availability_service.py`, `room_status_service.py`, `pytest.ini`, 템플릿 등)을 정밀 포함.
- 번들 패키징 스크립트(`scripts/pack_review_bundle.py`)가 임시 디렉터리에 번들을 추출하여 **57개 테스트의 독립 실행을 100% 자가 검증(Self-Test)**하도록 개선.

---

## 4. 제거한 Telegram Dependency

| 위치 | 기존 코드 | 변경 후 코드 | 효과 |
|---|---|---|---|
| `providers/mock_provider.py` | `from meeting_room_bot.telegram.mock_service import MockTelegramService` | `from meeting_room_bot.providers.mock_data import MockMeetingRoomData` | Core 계층이 UI/Telegram 패키지를 역참조하던 유일한 위반 지점 완전 제거 |
| `telegram/handlers.py` | `provider.get_available_rooms_now(user_id=str(user_id))` | `user_key = UserKey("telegram", user_id)`<br>`provider.get_available_rooms_now(user_id=user_key)` | 메신저 핸들러에서 플랫폼 식별자를 명시적 `UserKey`로 승격하여 Core에 전달 |

### Core 계층 무종속성 검증 (Static AST Inspection)
- 검사 대상: `src/meeting_room_bot/{auth, favorites, groupware, models, providers, services}`
- 검사 결과: **`telegram` 라이브러리 및 `meeting_room_bot.telegram` 임포트 0건 확인** (테스트 `test_all_core_layers_have_zero_telegram_dependencies` 통과).

---

## 5. 기존 기능 영향 여부

**영향 없음 (100% 호환 유지 및 정상 동작)**
- **사용자 UI 및 인터랙션**: Telegram 버튼 문구, 이모지, 텍스트 배치 일체 변경 없음.
- **/start 및 네비게이션**: 정상 동작 및 메뉴 복귀 유지.
- **지금 빈 회의실 / 언제 빈 회의실 / 어디 빈 회의실**: 당일/익일 경계 계산 및 회의실 상태 정상 조회.
- **즐겨찾기 추가 / 삭제 / 조회**: 기존 `data/favorites.json` 데이터 읽기/쓰기 호환.
- **계정 연동 (Account Linking)**: 로컬 FastAPI 로그인 폼 및 1회성 토큰 발급/검증 정상 동작.

---

## 6. 테스트 결과

### 6.1 전체 저장소 회귀 테스트
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\suresoft\Desktop\priv\30.vibe\06.meetingroom\suremeetingroom-bot
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.13.0
collected 184 items

tests\test_account_link.py .............                                 [  7%]
tests\test_account_link_localhost.py ......                              [ 10%]
tests\test_auth_session.py ....                                          [ 12%]
tests\test_availability_service.py .............                         [ 19%]
tests\test_bugs_safe_edit_and_next_res.py ........                       [ 23%]
tests\test_client.py .....                                               [ 26%]
tests\test_favorites.py .................                                [ 35%]
tests\test_flow_entry_state.py ......                                    [ 39%]
tests\test_meeting_room_service.py .......                               [ 42%]
tests\test_multi_user_isolation.py ...                                   [ 44%]
tests\test_platform_abstraction.py ...........................           [ 59%]
tests\test_precise_room_status.py .......                                [ 63%]
tests\test_providers.py ......                                           [ 66%]
tests\test_real_favorites.py ..........                                  [ 71%]
tests\test_real_mode_auth_flow.py ........                               [ 76%]
tests\test_room_detail_today_filter.py ......                            [ 79%]
tests\test_room_status_attribute.py .....                                [ 82%]
tests\test_room_status_service.py ...........                            [ 88%]
tests\test_telegram_bot.py ...............                               [ 96%]
tests\test_today_boundary_room_status.py .......                         [100%]

============================= 184 passed in 1.67s =============================
```

### 6.2 Standalone Review Bundle Self-Test (ZIP 단독 환경)
```text
============================= 57 passed in 1.63s ==============================
```
- **기존 테스트 157개**: 100% PASS (Zero Regression)
- **Phase 1 전체 추가/수정 테스트 27개**: 100% PASS
- **Review ZIP 단독 57개 테스트**: 100% PASS
- **합계**: **184 passed, 0 failed, 0 skipped**
```

- **기존 테스트**: 157개 100% 통과 (Failed: 0, Skipped: 0)
- **신규 테스트 (`tests/test_platform_abstraction.py`)**: 27개 통과 (Zero Regression)
  1. `test_user_key_creation_and_fields` (필드 및 불변성 검증)
  2. `test_user_key_equality_and_hash_stability` (동일 platform/id 간 동일 hash/equality 및 Dict Key 검증)
  3. `test_user_key_serialization_and_str` (to_string / str 직렬화)
  4. `test_user_key_deserialization_from_string` (qualified 및 raw 파싱)
  5. `test_user_key_from_any_transition_layer` (전환기 호환 레이어)
  6. `test_user_key_equality_independent_of_internal_user_or_account_mapping` (내부 사원 매핑 정보와 UserKey equality의 독립성 검증)
  7. `test_new_platform_adapter_explicit_construction` (신규 어댑터의 명시적 UserKey 생성 필수 검증)
  8. `test_user_key_canonicalization_lowercase_and_strip` (platform 소문자/공백제거 정규화 검증)
  9. `test_user_key_integer_id_normalization` (정수형 ID 문자열 자동 정규화 검증)
  10. `test_user_key_empty_platform_rejected` (빈 platform 입력 즉시 거부 검증)
  11. `test_user_key_empty_platform_user_id_rejected` (빈 user_id/None 입력 즉시 거부 검증)
  12. `test_user_key_canonicalized_hash_and_equality_stability` (정규화 변종 간 완벽한 equality/hash 정합성 검증)
  13. `test_user_key_colon_in_platform_rejected` (콜론 포함 시 ValueError 발생 검증)
  14. `test_user_key_platform_character_validation` (플랫폼명 안전 문자 규칙 검증)
  15. `test_user_key_serialization_round_trip` (to_string / from_string 일대일 복원 및 Hash 불변성 검증)
  16. `test_telegram_and_kakao_distinct_keys` (동일 ID 타 플랫폼 분리)
  17. `test_session_manager_platform_isolation` (세션 네임스페이스 격리)
  18. `test_session_manager_bidirectional_compatibility` (세션 양방향 레거시 호환)
  19. `test_favorites_repository_user_key_compatibility` (즐겨찾기 저장소 격리 및 호환)
  20. `test_mock_provider_does_not_import_telegram` (Mock AST 무종속성)
  21. `test_all_core_layers_have_zero_telegram_dependencies` (Core 7개 패키지 AST 무종속성 100% 검증)
  22. `test_mock_provider_query_with_user_key` (Provider 쿼리 동작 검증)
  23. `test_mock_provider_preserves_platform_namespace` (MockProvider에서 UserKey namespace 완전 보존 검증)
  24. `test_mock_provider_favorites_namespace_isolation` (MockProvider 즐겨찾기 네임스페이스 격리 검증)
  25. `test_concurrent_users_no_shared_mutable_meeting_room_service` (다중 사용자 동시/교차 요청 시 Client 오염 방지 및 Statelessness 검증)
  26. `test_favorite_service_complete_statelessness` (FavoriteService의 100% 무상태성 및 per-call service 검증)
  27. `test_telegram_user_key_account_linking_integration` (FastAPI TestClient 연동 E2E Account Linking 검증)

---

## 7. 남은 Telegram Coupling 분석

이번 Phase 1은 안전한 최소 리팩터링 원칙에 따라 의도적으로 다음 결합을 Telegram 계층 내에 유지했습니다.

1. **Telegram 메시지 포맷팅 (Presenter) 결합**:
   - `telegram/handlers.py` 내부에서 회의실 목록 텍스트 조합(`"🟢 현재 빈 회의실\n..."`)과 이모지를 직접 조립하고 있습니다.
   - 이는 Core에 넣는 대신 플랫폼 전용 렌더러 원칙에 부합하지만, 향후 `telegram/renderer.py`로 분리하면 핸들러 코드 가독성이 대폭 향상됩니다.
2. **`user_state_mgr` (`UserStateManager`)**:
   - `telegram/states.py`에 위치하며, 텔레그램 콜백 흐름(`when_time`, `when_dur`, `where` 등)의 단계별 선택 상태를 인메모리 관리하고 있습니다. 카카오톡 웹훅의 블록 파라미터와는 구조가 다르므로 텔레그램 전용 상태로 정상 격리되어 있습니다.

---

## 8. 다음 Phase에서 해야 할 일

Phase 1의 플랫폼 추상화 및 Core 무종속성 기반 위에서 순차적으로 다음 단계를 추진합니다.

### Phase 2: Production HTTPS Account Linking 준비
- [ ] 공인 HTTPS endpoint 및 ingress/reverse proxy 방식 검토 (예: Nginx 등 연동 방안 검토).
  *(참고: 사내 서버 vs 회사 승인 Cloud, Reverse Proxy vs Managed Ingress는 아직 확정되지 않았으며 보안/네트워크 정책 검토 후 결정)*
- [ ] Telegram 핸들러에서 공인 HTTPS 도메인 감지 시 `InlineKeyboardButton(url=link_url)` 활성화 (로컬 모드 터미널 링크 복사 탈피).
- [ ] 웹 로그인 폼에 CSRF 방어 및 Rate Limiting 기초 보안 적용.

### Phase 3: Persistence 추상화 및 Telegram 운영 검증
- [ ] `SessionStore` 추상 인터페이스 정의 및 세션 쿠키 암호화(선택 사항) 검토.
- [ ] `FavoriteRepository` 파일 락(Lock) 보강.
- [ ] 사내 서버 또는 승인 Cloud 인프라에서 Telegram 봇 1차 실운영 검증.

### Phase 4: Kakao Skill Adapter 개발 (Telegram 운영 안정화 이후)
- [ ] 카카오 i 오픈빌더 스킬 요청/응답 DTO 작성.
- [ ] FastAPI 기반 `/api/kakao/skill` 웹훅 엔드포인트 구현 (5초 타임아웃 대응).
- [ ] Shared Core(`RealMeetingRoomProvider`)의 구조화 데이터를 호출하여 카카오 카드/텍스트 렌더러 구현.
