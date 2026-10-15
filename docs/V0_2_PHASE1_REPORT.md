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
| `src/meeting_room_bot/models/user_key.py` | **신규 생성** | 순수 채널 식별자 `UserKey(platform, platform_user_id)` 불변 데이터클래스 정의 |
| `src/meeting_room_bot/models/__init__.py` | **수정** | `UserKey` 모듈 export 추가 |
| `src/meeting_room_bot/providers/mock_data.py` | **신규 생성** | `MockTelegramService`의 목 데이터셋을 플랫폼 독립 `MockMeetingRoomData`로 분리 |
| `src/meeting_room_bot/providers/mock_provider.py` | **수정** | `telegram` 패키지 import 제거, `mock_data` 참조 및 `UserKey` 지원 |
| `src/meeting_room_bot/telegram/mock_service.py` | **수정** | `mock_data`의 `MockMeetingRoomData`를 하위 호환 re-export |
| `src/meeting_room_bot/providers/base.py` | **수정** | `MeetingRoomQueryProvider` 인터페이스에 `UserKey` 지원 및 Transition Compatibility 명시 |
| `src/meeting_room_bot/providers/real_provider.py` | **수정** | 모든 쿼리 메서드에서 `Union[UserKey, str]` 지원 및 내부 정규화 |
| `src/meeting_room_bot/auth/session_manager.py` | **수정** | `UserKey` 플랫폼 격리 및 레거시 문자열 ID와의 양방향 호환 어댑터 구현 |
| `src/meeting_room_bot/favorites/repository.py` | **수정** | `FavoriteRepository` 인터페이스에 `Union[UserKey, str]` Transition Layer 명시 |
| `src/meeting_room_bot/favorites/json_repository.py` | **수정** | `_resolve_storage_key` 헬퍼를 통한 `UserKey` 및 레거시 JSON 키 호환 처리 |
| `src/meeting_room_bot/favorites/service.py` | **수정** | 즐겨찾기 도메인 서비스 메서드에 Transition Compatibility Layer 명시 |
| `src/meeting_room_bot/account_link/token_service.py` | **수정** | 1회성 토큰 생성 시 `Union[UserKey, str]` 수용 및 직렬화 바인딩 |
| `src/meeting_room_bot/telegram/handlers.py` | **수정** | `update.effective_user.id`를 명시적 `UserKey("telegram", ...)`로 변환 후 Core에 전달 |
| `tests/test_platform_abstraction.py` | **신규 생성** | UserKey 동작, 네임스페이스 격리, Hash 안정성, Core 무종속성(AST 검사) 14개 단위 테스트 추가 |
| `docs/V0_2_ARCHITECTURE_PLAN.md` | **수정** | UserKey 채널 식별자 정제, Ingress/Reverse Proxy 검토 표현 동기화 |
| `docs/V0_2_PHASE1_REPORT.md` | **수정** | Phase 1 최종 설계 보완 사항 및 테스트 결과 반영 |

---

## 3. UserKey 및 호환성 설계

### 3.1 최종 `UserKey` 구조 (순수 Channel Identity)
```python
@dataclass(frozen=True)
class UserKey:
    """Platform-independent channel identity identifying a user within a messaging platform.

    Architectural Principle:
    - UserKey represents ONLY the platform-specific channel identity (e.g. telegram:8296531540, kakao:k_12345).
    - It must NOT contain internal employee or corporate application user state (e.g. internal_user_id, emp_id),
      so that hash and equality remain strictly stable when used as dictionary/cache keys.
    """
    platform: str          # "telegram" | "kakao"
    platform_user_id: str  # "8296531540" | "k_hash_abc"

    def to_string(self) -> str:
        return f"{self.platform}:{self.platform_user_id}"

    @classmethod
    def from_string(cls, raw: str, default_platform: str = "telegram") -> "UserKey": ...

    @classmethod
    def from_any(cls, val: Union["UserKey", str, int], default_platform: str = "telegram") -> "UserKey": ...
```

### 3.2 핵심 설계 결정 및 원칙

1. **`internal_user_id` 제거 이유 (Hash & Equality 정합성)**:
   - `UserKey`는 세션 딕셔너리(`_sessions[user_key]`)나 즐겨찾기 저장소의 식별 키(Dict Key)로 직접 활용됩니다.
   - 만약 `UserKey` 내부에 `internal_user_id` 필드가 포함되면:
     `UserKey("telegram", "123", None)` 과 `UserKey("telegram", "123", "emp_001")`
     가 equality 및 hash 관점에서 서로 다른 객체로 판별되어, 계정 연동 전후에 기존 세션이나 즐겨찾기 조회 정합성이 파괴됩니다.
   - 따라서 `UserKey`는 순수한 **메신저 플랫폼 채널 식별자(Channel Identity)** 역할만 수행하며, 사내 임직원 식별 정보는 포함하지 않습니다.

2. **Internal App User 확장 모델 분리**:
   - 향후 사내 사용자는 `UserKey`에 필드를 추가하는 대신, 상위 모델(`AppUser`, `ChannelIdentity`, `AccountMapping`)로 별도 분리하여 N:1 매핑을 구성하도록 설계합니다.
   - 이번 Phase 1에서는 `AppUser`, DB, `AccountMapping`을 구현하지 않으며 아키텍처 경계만 분리합니다.

3. **Legacy Compatibility Layer 범위 및 원칙**:
   - Core 인터페이스의 `Union[UserKey, str]`은 v0.2 전환기 동안 v0.1 테스트와 기존 데이터를 지원하기 위한 **한시적 Transition Compatibility Layer**입니다.
   - **데이터 흐름 원칙**:
     - 메신저 어댑터(Platform Adapter) → 명시적 `UserKey` 생성 → Core 내부는 100% `UserKey` 사용.
     - 기존 `str user_id`는 v0.1 하위 호환 경로에서만 허용.
     - 향후 신규 Kakao 어댑터는 plain `str`을 넘기지 않고 반드시 명시적인 `UserKey("kakao", id)`를 생성해야 합니다 (오인 fallback 차단).

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

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\suresoft\Desktop\priv\30.vibe\06.meetingroom\suremeetingroom-bot
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.13.0
collected 171 items

tests\test_account_link.py .............                                 [  7%]
tests\test_account_link_localhost.py ......                              [ 11%]
tests\test_auth_session.py ....                                          [ 13%]
tests\test_availability_service.py .............                         [ 21%]
tests\test_bugs_safe_edit_and_next_res.py ........                       [ 25%]
tests\test_client.py .....                                               [ 28%]
tests\test_favorites.py .................                                [ 38%]
tests\test_flow_entry_state.py ......                                    [ 42%]
tests\test_meeting_room_service.py .......                               [ 46%]
tests\test_multi_user_isolation.py ...                                   [ 47%]
tests\test_platform_abstraction.py ..............                        [ 56%]
tests\test_precise_room_status.py .......                                [ 60%]
tests\test_providers.py ......                                           [ 63%]
tests\test_real_favorites.py ..........                                  [ 69%]
tests\test_real_mode_auth_flow.py ........                               [ 74%]
tests\test_room_detail_today_filter.py ......                            [ 77%]
tests\test_room_status_attribute.py .....                                [ 80%]
tests\test_room_status_service.py ...........                            [ 87%]
tests\test_telegram_bot.py ...............                               [ 95%]
tests\test_today_boundary_room_status.py .......                         [100%]

============================= 171 passed in 1.22s =============================
```

- **기존 테스트**: 157개 100% 통과 (Failed: 0, Skipped: 0)
- **신규 테스트 (`tests/test_platform_abstraction.py`)**: 14개 신규 통과
  1. `test_user_key_creation_and_fields` (필드 및 불변성 검증)
  2. `test_user_key_equality_and_hash_stability` (동일 platform/id 간 동일 hash/equality 및 Dict Key 검증)
  3. `test_user_key_serialization_and_str` (to_string / str 직렬화)
  4. `test_user_key_deserialization_from_string` (qualified 및 raw 파싱)
  5. `test_user_key_from_any_transition_layer` (전환기 호환 레이어)
  6. `test_user_key_equality_independent_of_internal_user_or_account_mapping` (내부 사원 매핑 정보와 UserKey equality의 독립성 검증)
  7. `test_new_platform_adapter_explicit_construction` (신규 어댑터의 명시적 UserKey 생성 필수 검증)
  8. `test_telegram_and_kakao_distinct_keys` (동일 ID 타 플랫폼 분리)
  9. `test_session_manager_platform_isolation` (세션 네임스페이스 격리)
  10. `test_session_manager_bidirectional_compatibility` (세션 양방향 레거시 호환)
  11. `test_favorites_repository_user_key_compatibility` (즐겨찾기 저장소 격리 및 호환)
  12. `test_mock_provider_does_not_import_telegram` (Mock AST 무종속성)
  13. `test_all_core_layers_have_zero_telegram_dependencies` (Core 6개 패키지 AST 무종속성 100% 검증)
  14. `test_mock_provider_query_with_user_key` (Provider 쿼리 동작 검증)

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
