"""Real implementation of MeetingRoomQueryProvider connecting to Groupware API."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Union

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import (
    GroupwareAPIError,
    GroupwareAuthError,
    GroupwareNetworkError,
)
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.base import (
    MeetingRoomQueryProvider,
    QueryResult,
    QueryStatus,
)
from meeting_room_bot.services.meeting_room_service import MeetingRoomService
from meeting_room_bot.utils.date_utils import resolve_date_str

logger = logging.getLogger(__name__)
SEOUL_TZ = timezone(timedelta(hours=9))


class RealMeetingRoomProvider(MeetingRoomQueryProvider):
    """Provides real meeting room data via UserSessionManager, MeetingRoomService, and FavoriteService."""

    def __init__(
        self,
        session_mgr: UserSessionManager,
        favorite_service: FavoriteService,
    ):
        self.session_mgr = session_mgr
        self.favorite_service = favorite_service

    def _get_service(self, user_id: Union[UserKey, str]) -> Optional[MeetingRoomService]:
        """Helper to get MeetingRoomService for authenticated user."""
        client = self.session_mgr.get_client(user_id)
        if not client or not client.is_authenticated:
            return None
        return MeetingRoomService(client)

    def check_authentication(self, user_id: Union[UserKey, str]) -> QueryResult:
        """Check if user has an active authenticated Groupware session."""
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)
        return QueryResult(status=QueryStatus.SUCCESS)

    def get_locations(self, user_id: Union[UserKey, str]) -> QueryResult:
        """Query list of meeting room location assets via Groupware API."""
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            assets = service.get_meeting_assets()
            locations = []
            for a in assets:
                short_label = a.name.replace("[판교] ", "").replace("[대전] ", "")
                if "10층" in short_label:
                    short_label = "10층"
                locations.append({
                    "id": a.id,
                    "name": a.name,
                    "short_label": short_label,
                    "is_fav": False,
                })
            return QueryResult(status=QueryStatus.SUCCESS, data={"locations": locations})
        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Error fetching locations for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))

    def get_available_rooms_now(self, user_id: Union[UserKey, str], scope: str = "fav") -> QueryResult:
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            if scope in ("fav", "favorites"):
                fav_rooms = self.favorite_service.get_favorite_rooms(user_id, meeting_room_service=service)
                if not fav_rooms:
                    return QueryResult(status=QueryStatus.NO_FAVORITES)

                raw_results = service.get_available_favorite_rooms_now(
                    user_id=user_id, favorite_service=self.favorite_service
                )

                groups_dict: Dict[str, List[Dict[str, Any]]] = {}
                for item in raw_results:
                    asset_name = item["asset"].name
                    if asset_name not in groups_dict:
                        groups_dict[asset_name] = []

                    room = item["room"]
                    status_info = item["status"]
                    note = (
                        f"{status_info.next_reservation_start.strftime('%H:%M')}부터 예약"
                        if status_info.next_reservation_start
                        else "오늘 추가 예약 없음"
                    )
                    groups_dict[asset_name].append({
                        "name": room.name,
                        "note": note,
                    })

                groups = [
                    {"asset_name": aname, "rooms": rlist}
                    for aname, rlist in groups_dict.items()
                ]

                return QueryResult(
                    status=QueryStatus.SUCCESS,
                    data={"scope_title": "⭐ 즐겨찾기 기준", "groups": groups},
                )
            else:
                raw_results = service.get_available_rooms_now(asset_ids=None)

                groups_dict: Dict[str, List[Dict[str, Any]]] = {}
                for item in raw_results:
                    asset_name = item["asset"].name
                    if asset_name not in groups_dict:
                        groups_dict[asset_name] = []

                    room = item["room"]
                    status_info = item["status"]
                    note = (
                        f"{status_info.next_reservation_start.strftime('%H:%M')}부터 예약"
                        if status_info.next_reservation_start
                        else "오늘 추가 예약 없음"
                    )
                    groups_dict[asset_name].append({
                        "name": room.name,
                        "note": note,
                    })

                groups = [
                    {"asset_name": aname, "rooms": rlist}
                    for aname, rlist in groups_dict.items()
                ]

                return QueryResult(
                    status=QueryStatus.SUCCESS,
                    data={"scope_title": "🌐 전체 위치", "groups": groups},
                )

        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Groupware API error for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))

    def get_available_rooms_at(
        self,
        user_id: Union[UserKey, str],
        date_str: str,
        start_time: str,
        duration: int,
        scope: str = "fav",
    ) -> QueryResult:
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            date_str = resolve_date_str(date_str)

            st_hour, st_min = map(int, start_time.split(":"))
            dt_base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=SEOUL_TZ)
            st_dt = dt_base.replace(hour=st_hour, minute=st_min)
            end_dt = st_dt + timedelta(minutes=duration)

            if scope in ("fav", "favorites"):
                fav_rooms = self.favorite_service.get_favorite_rooms(user_id, meeting_room_service=service)
                if not fav_rooms:
                    return QueryResult(status=QueryStatus.NO_FAVORITES)

                raw_results = service.get_available_favorite_rooms_at(
                    user_id=user_id,
                    favorite_service=self.favorite_service,
                    start_time=st_dt,
                    end_time=end_dt,
                )

                available_rooms = []
                for group in raw_results:
                    for room in group["available_rooms"]:
                        available_rooms.append(f"🟢 {room.name}")

                return QueryResult(
                    status=QueryStatus.SUCCESS,
                    data={
                        "date": date_str,
                        "start_time": start_time,
                        "end_time": end_dt.strftime("%H:%M"),
                        "scope": scope,
                        "available_rooms": available_rooms,
                    },
                )
            else:
                raw_results = service.get_available_rooms_at(
                    asset_ids=None,
                    start_time=st_dt,
                    end_time=end_dt,
                )

                available_rooms = []
                for group in raw_results:
                    for room in group["available_rooms"]:
                        available_rooms.append(f"🟢 {room.name}")

                return QueryResult(
                    status=QueryStatus.SUCCESS,
                    data={
                        "date": date_str,
                        "start_time": start_time,
                        "end_time": end_dt.strftime("%H:%M"),
                        "scope": scope,
                        "available_rooms": available_rooms,
                    },
                )

        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Groupware API error for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))

    def get_location_status(self, user_id: Union[UserKey, str], asset_id: int) -> QueryResult:
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            raw = service.get_location_status(asset_id=asset_id)
            asset = raw["asset"]
            statuses = raw["room_statuses"]

            rooms_info = []
            for st in statuses:
                room = st.room
                status_text = "🟢 사용 가능" if st.is_available else "🔴 사용 중"

                if st.is_available:
                    if st.next_reservation_start:
                        note = f"{st.next_reservation_start.strftime('%H:%M')}부터 예약"
                    else:
                        note = "오늘 추가 예약 없음"
                else:
                    lines = []
                    if st.current_reservation_end:
                        lines.append(f"현재 예약: {st.current_reservation_end.strftime('%H:%M')} 종료")

                    if st.next_reservation_start:
                        lines.append(f"다음 예약: {st.next_reservation_start.strftime('%H:%M')}부터")
                    else:
                        lines.append("이후 예약 없음")

                    if st.available_from and st.current_reservation_end and st.available_from > st.current_reservation_end:
                        lines.append(f"실제 사용 가능: {st.available_from.strftime('%H:%M')}부터")

                    note = "\n".join(lines)

                rooms_info.append({
                    "id": room.id,
                    "name": room.name,
                    "status": status_text,
                    "note": note,
                })

            return QueryResult(
                status=QueryStatus.SUCCESS,
                data={
                    "asset_id": asset_id,
                    "asset_name": asset.name,
                    "rooms": rooms_info,
                },
            )
        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Groupware API error for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))

    def get_room_detail(self, user_id: Union[UserKey, str], asset_id: int, room_id: int) -> QueryResult:
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            raw = service.get_room_detail(asset_id=asset_id, room_id=room_id)
            room = raw["room"]
            status_info = raw["status"]
            slots = raw["reservation_slots"]

            schedules = [
                f"{st.strftime('%H:%M')} ~ {et.strftime('%H:%M')}"
                for st, et in slots
            ]

            status_text = "🟢 사용 가능" if status_info.is_available else "🔴 사용 중"

            return QueryResult(
                status=QueryStatus.SUCCESS,
                data={
                    "room_id": room.id,
                    "asset_id": asset_id,
                    "name": room.name,
                    "capacity": room.capacity or 6,
                    "status_text": status_text,
                    "schedules": schedules,
                },
            )
        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Groupware API error for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))

    def get_favorites(self, user_id: Union[UserKey, str]) -> QueryResult:
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        fav_tuples = self.favorite_service.get_favorite_rooms(user_id, meeting_room_service=service)
        asset_names = list({a.name for a, _ in fav_tuples})
        room_names = [f"🚪 {r.name}" for _, r in fav_tuples]

        uid_str = user_id.to_string() if isinstance(user_id, UserKey) else str(user_id)
        return QueryResult(
            status=QueryStatus.SUCCESS,
            data={
                "user_id": uid_str,
                "assets": asset_names if asset_names else ["(없음)"],
                "rooms": room_names if room_names else ["(없음)"],
            },
        )

    def get_timeline(
        self,
        user_id: Union[UserKey, str],
        asset_id: Optional[int] = None,
        target_date: Optional[datetime] = None,
    ) -> QueryResult:
        """Fetch and return timeline grid dataset for specified user and asset."""
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            user_key = UserKey.from_any(user_id)
            data = service.get_timeline_data(
                asset_id=asset_id,
                user_key=user_key,
                favorite_service=self.favorite_service,
                target_date=target_date,
            )
            return QueryResult(status=QueryStatus.SUCCESS, data=data)
        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error in get_timeline for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error in get_timeline for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Error in get_timeline for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))

    def get_web_availability(
        self,
        user_id: Union[UserKey, str],
        asset_id: Optional[int] = None,
        start_time: str = "14:00",
        duration: int = 60,
        target_date: Optional[datetime] = None,
    ) -> QueryResult:
        """Fetch and return room availability for WHEN mode in Web App."""
        if not self.session_mgr.has_session(user_id):
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        service = self._get_service(user_id)
        if not service:
            return QueryResult(status=QueryStatus.NOT_AUTHENTICATED)

        try:
            user_key = UserKey.from_any(user_id)
            data = service.get_web_availability(
                asset_id=asset_id,
                start_time=start_time,
                duration=duration,
                user_key=user_key,
                favorite_service=self.favorite_service,
                target_date=target_date,
            )
            return QueryResult(status=QueryStatus.SUCCESS, data=data)
        except GroupwareAuthError as e:
            logger.warning(f"401 Auth error for user {user_id}: {e}")
            self.session_mgr.remove_session(user_id)
            return QueryResult(status=QueryStatus.SESSION_EXPIRED, error_message=str(e))
        except GroupwareNetworkError as e:
            logger.error(f"Network error in get_web_availability for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.NETWORK_ERROR, error_message=str(e))
        except GroupwareAPIError as e:
            logger.error(f"Groupware API error in get_web_availability for user {user_id}: {e}")
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
        except Exception as e:
            logger.error(f"Error in get_web_availability for user {user_id}: {e}", exc_info=True)
            return QueryResult(status=QueryStatus.GROUPWARE_API_ERROR, error_message=str(e))
