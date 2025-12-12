import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)


class FirebaseManager:

    def __init__(self):
        try:
            self._initialize_firebase()
            self.db = firestore.client()
            self.users_collection = "users"
            self.events_collection = "events"
            logger.info("✅ Firebase initialized")
        except Exception as e:
            logger.error(f"🔥 Firebase init failed: {e}")
            raise

    def _initialize_firebase(self):
        if firebase_admin._apps:
            return

        firebase_creds = os.getenv('FIREBASE_CREDENTIALS')
        if firebase_creds:
            try:
                cred_dict = json.loads(firebase_creds)
                cred = credentials.Certificate(cred_dict)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in FIREBASE_CREDENTIALS: {e}")
                raise
        else:
            key_file = 'firebase-service-account.json'
            if os.path.exists(key_file):
                cred = credentials.Certificate(key_file)
            else:
                cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred)

    # ========== USER CRUD ==========

    def create_user(self, user_data: Dict[str, Any]) -> bool:
        try:
            user_id = str(user_data['telegram_id'])
            timestamp = datetime.utcnow()
            user_data.update({
                'created_at': timestamp,
                'updated_at': timestamp
            })
            self.db.collection(
                self.users_collection).document(user_id).set(user_data)
            return True
        except Exception as e:
            logger.error(f"[CREATE_USER] {e}")
            return False

    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        try:
            doc = self.db.collection(self.users_collection).document(
                str(telegram_id)).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"[GET_USER] {e}")
            return None

    def update_user(self, telegram_id: int, update_data: Dict[str,
                                                              Any]) -> bool:
        try:
            update_data['updated_at'] = datetime.utcnow()
            self.db.collection(self.users_collection).document(
                str(telegram_id)).update(update_data)
            return True
        except Exception as e:
            logger.error(f"[UPDATE_USER] {e}")
            return False

    def delete_user(self, telegram_id: int) -> bool:
        try:
            self.db.collection(self.users_collection).document(
                str(telegram_id)).delete()
            return True
        except Exception as e:
            logger.error(f"[DELETE_USER] {e}")
            return False

    def user_exists(self, telegram_id: int) -> bool:
        try:
            return self.db.collection(self.users_collection).document(
                str(telegram_id)).get().exists
        except Exception as e:
            logger.error(f"[USER_EXISTS] {e}")
            return False

    def get_all_users(self) -> List[Dict[str, Any]]:
        try:
            docs = self.db.collection(self.users_collection).get()
            return [{
                **doc_dict, 'telegram_id': int(doc.id)
            } for doc in docs if (doc_dict := doc.to_dict()) is not None]
        except Exception as e:
            logger.error(f"[GET_ALL_USERS] {e}")
            return []

    def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        try:
            docs = self.db.collection(self.users_collection).where(
                'role', '==', role).get()
            return [{
                **doc_dict, 'telegram_id': int(doc.id)
            } for doc in docs if (doc_dict := doc.to_dict()) is not None]
        except Exception as e:
            logger.error(f"[GET_USERS_BY_ROLE] {e}")
            return []

    # ========== EVENT LOGGING ==========

    def log_event(self, event_data: Dict[str, Any]) -> bool:
        try:
            event_data['timestamp'] = datetime.utcnow()
            self.db.collection(self.events_collection).add(event_data)
            return True
        except Exception as e:
            logger.error(f"[LOG_EVENT] {e}")
            return False

    # ========== GAME UTILS ==========

    def update_hp(self, telegram_id: int, new_hp: int) -> bool:
        return self.update_user(telegram_id, {'hp': new_hp})

    # ========== AUTH / ROLE CHECK - IMPROVED WITH CASE-INSENSITIVE LOOKUP ==========

    def check_user_authorization(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Check if user is authorized with case-insensitive username matching.
        First tries exact match, then falls back to case-insensitive search.
        """
        if not username:
            logger.warning("Empty username provided for authorization check")
            return None

        # Normalize username (remove @ and strip whitespace, convert to lowercase)
        clean_username = username.lstrip('@').strip().lower()

        if not clean_username:
            logger.warning("Username is empty after cleaning")
            return None

        # Ensure username has @ prefix for storage format
        formatted_username = f"@{clean_username}"

        # First try exact match (faster)
        logger.info(f"Checking authorization for username: '{formatted_username}' (exact match)")
        user_data = self._check_exact_username_match(formatted_username)

        if user_data:
            logger.info(f"✅ Found exact match for user '{formatted_username}'")
            return user_data

        # If no exact match, try case-insensitive search
        logger.info(f"No exact match found, trying case-insensitive search for: '{clean_username}'")
        user_data = self._check_case_insensitive_username_match(clean_username)

        if user_data:
            stored_username = user_data.get('username', '').lstrip('@')
            logger.info(f"✅ Found case-insensitive match: '{clean_username}' -> '{stored_username}'")
            return user_data

        logger.warning(f"❌ No user found with username: '{clean_username}' (tried exact and case-insensitive)")
        return None

    def _check_exact_username_match(self, username: str) -> Optional[Dict[str, Any]]:
        """Check for exact username match across all collections."""

        # METHOD 1: Check EXCO collection first
        try:
            exco_ref = self.db.collection('Users').document('EXCO').collection('EXCO')
            doc_ref = exco_ref.document(username)
            doc = doc_ref.get()

            if doc.exists:
                user_data = doc.to_dict()
                logger.info(f"Found user in EXCO collection: {user_data}")

                # Check if user is active
                is_active = user_data.get('is_active', False)
                if isinstance(is_active, str):
                    is_active = is_active.lower() == 'true'

                if is_active:
                    logger.info(f"✅ EXCO User '{username}' authorized and active")
                    return user_data
                else:
                    logger.warning(f"EXCO User '{username}' found but is_active is False")
        except Exception as e:
            logger.error(f"Error checking EXCO collection: {e}")

        # METHOD 2: Check Alliance collections
        try:
            users_root = self.db.collection("Users")
            alliance_docs = users_root.list_documents()

            for alliance_doc in alliance_docs:
                alliance_name = alliance_doc.id

                # Skip EXCO as we already checked it
                if alliance_name == 'EXCO':
                    continue

                logger.debug(f"Checking alliance: {alliance_name}")

                # Get all group collections under this alliance
                group_collections = alliance_doc.collections()
                for group_collection in group_collections:
                    group_name = group_collection.id
                    logger.debug(f"Checking group: {alliance_name}/{group_name}")

                    # Check if user exists in this group
                    doc_ref = group_collection.document(username)
                    doc = doc_ref.get()

                    if doc.exists:
                        user_data = doc.to_dict()
                        logger.info(f"Found user in {alliance_name}/{group_name}: {user_data}")

                        # Check if user is active
                        is_active = user_data.get('is_active', False)
                        if isinstance(is_active, str):
                            is_active = is_active.lower() == 'true'

                        if is_active:
                            # Add alliance and group info to user data
                            user_data.update({
                                'alliance': alliance_name,
                                'group': group_name,
                                'username': username
                            })
                            logger.info(f"✅ Alliance User '{username}' authorized and active in {alliance_name}/{group_name}")
                            return user_data
                        else:
                            logger.warning(f"Alliance User '{username}' found in {alliance_name}/{group_name} but is_active is False")

        except Exception as e:
            logger.error(f"Error checking alliance collections: {e}")

        return None

    def _check_case_insensitive_username_match(self, username_lower: str) -> Optional[Dict[str, Any]]:
        """
        Perform case-insensitive username search across all collections.
        This is slower but more thorough.
        """

        # METHOD 1: Check EXCO collection
        try:
            logger.debug("Checking EXCO collection for case-insensitive match")
            exco_ref = self.db.collection('Users').document('EXCO').collection('EXCO')
            docs = exco_ref.get()

            for doc in docs:
                if doc.exists:
                    user_data = doc.to_dict()
                    if not user_data or not user_data.get('is_active', False):
                        continue

                    stored_username = user_data.get('username', '').lstrip('@').strip().lower()

                    # Case-insensitive comparison
                    if stored_username == username_lower:
                        logger.info(f"Found case-insensitive match in EXCO: '{username_lower}' -> '{stored_username}'")
                        return user_data

        except Exception as e:
            logger.error(f"Error in case-insensitive search for EXCO: {e}")

        # METHOD 2: Check Alliance collections
        try:
            users_root = self.db.collection("Users")
            alliance_docs = users_root.list_documents()

            for alliance_doc in alliance_docs:
                alliance_name = alliance_doc.id

                # Skip EXCO as we already checked it
                if alliance_name == 'EXCO':
                    continue

                logger.debug(f"Checking {alliance_name} for case-insensitive match")

                # Get all group collections under this alliance
                group_collections = alliance_doc.collections()
                for group_collection in group_collections:
                    group_name = group_collection.id
                    logger.debug(f"Checking {alliance_name}/{group_name} for case-insensitive match")

                    docs = group_collection.get()

                    for doc in docs:
                        if doc.exists:
                            user_data = doc.to_dict()
                            if not user_data or not user_data.get('is_active', False):
                                continue

                            stored_username = user_data.get('username', '').lstrip('@').strip().lower()

                            # Case-insensitive comparison
                            if stored_username == username_lower:
                                # Add alliance and group info to user data
                                user_data.update({
                                    'alliance': alliance_name,
                                    'group': group_name,
                                    'username': f"@{stored_username}"
                                })
                                logger.info(f"Found case-insensitive match in {alliance_name}/{group_name}: '{username_lower}' -> '{stored_username}'")
                                return user_data

        except Exception as e:
            logger.error(f"Error in case-insensitive search for alliances: {e}")

        return None

    def is_exco_or_owner(self, username: str) -> bool:
        user_data = self.check_user_authorization(username)
        return bool(user_data
                    and user_data.get('role', '').lower() in ('exco', 'owner'))

    def set_user_active_status(self, username: str, is_active: bool) -> bool:
        """Set user's active status - for admin use"""
        try:
            if not username.startswith('@'):
                username = f"@{username}"
            username = username.lower().strip()

            exco_ref = self.db.collection('Users').document('EXCO').collection(
                'EXCO')
            doc_ref = exco_ref.document(username)
            doc = doc_ref.get()

            if doc.exists:
                doc_ref.update({'is_active': is_active})
                status = "activated" if is_active else "deactivated"
                logger.info(f"User '{username}' has been {status}")
                return True

            logger.warning(
                f"No user found to update active status for username: '{username}'"
            )
            return False

        except Exception as e:
            logger.error(f"Error updating active status for '{username}': {e}")
            return False

    def get_all_exco_users(self) -> List[Dict[str, Any]]:
        """Get all EXCO users (for admin purposes)"""
        try:
            exco_ref = self.db.collection('Users').document('EXCO').collection(
                'EXCO')
            docs = exco_ref.stream()
            users = []

            for doc in docs:
                user_data = doc.to_dict()
                if user_data:
                    user_data['doc_id'] = doc.id
                    users.append(user_data)

            return users

        except Exception as e:
            logger.error(f"Error getting all EXCO users: {e}")
            return []

    def test_connection(self) -> bool:
        """Test Firebase connection"""
        try:
            # Try to read from EXCO collection
            exco_ref = self.db.collection('Users').document('EXCO').collection(
                'EXCO')
            docs = list(exco_ref.limit(1).stream())

            logger.info("✅ Firebase connection test successful")
            return True

        except Exception as e:
            logger.error(f"❌ Firebase connection test failed: {e}")
            return False

    # ========== ROUTING DATA ==========

    def get_routing_for_user(self, user_data: dict) -> List[dict]:
        return self.get_routing_by_alliance_and_group(user_data['alliance'],
                                                      user_data['group'])

    def get_routing_by_alliance_and_group(self, alliance: str,
                                          group: str) -> List[dict]:
        try:
            routing_root = self.db.collection("Routing").document(
                alliance).collection(group)

            schedules = []
            for day_doc in routing_root.stream():
                day_label = day_doc.id
                day_ref = routing_root.document(day_label)
                for time_collection in day_ref.collections():
                    time_str = time_collection.id
                    for game_doc in time_collection.stream():
                        game_data = game_doc.to_dict()
                        game_data.update({
                            'day': day_label,
                            'time': f"{day_label} {time_str}",
                            'game': game_doc.id,
                        })
                        schedules.append(game_data)
            return schedules
        except Exception as e:
            logger.error(f"[ROUTING_FETCH] Failed to get routing: {e}")
            return []

    # ========== ALLIANCE MEMBER LOOKUP ==========

    def get_alliance_members(self, alliance: str) -> List[Dict[str, Any]]:
        try:
            members = []
            alliance_ref = self.db.collection("Users").document(alliance)
            for group in alliance_ref.collections():
                for doc in group.stream():
                    user_data = doc.to_dict()
                    if user_data:
                        user_data['username'] = doc.id
                        user_data['alliance'] = alliance
                        members.append(user_data)
            return members
        except Exception as e:
            logger.error(f"[GET_ALLIANCE_MEMBERS] {e}")
            return []

    def get_suballiances(self, alliance: str) -> List[str]:
        try:
            routing_ref = self.db.collection("Routing").document(alliance)
            suballiances = []

            collections = routing_ref.collections()
            for col in collections:
                suballiances.append(col.id)

            return sorted(suballiances)
        except Exception as e:
            logger.error(f"[GET_SUBALLIANCES] {e}")
            return []