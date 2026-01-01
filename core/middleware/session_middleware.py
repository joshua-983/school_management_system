# core/middleware/session_middleware.py
import logging
import asyncio
from asgiref.sync import sync_to_async
from django.utils.deprecation import MiddlewareMixin
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.base import CreateError
import json

logger = logging.getLogger(__name__)

class SessionProtectionMiddleware(MiddlewareMixin):
    """
    Middleware to protect against session corruption and fix issues
    - Async compatible version
    """
    sync_capable = True
    async_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        if asyncio.iscoroutinefunction(self.get_response):
            self._is_coroutine = asyncio.coroutines._is_coroutine
    
    def __call__(self, request):
        # If we're in async context (ASGI), use async handling
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        # Otherwise use sync handling (WSGI)
        return super().__call__(request)
    
    async def __acall__(self, request):
        """Async version of __call__"""
        await self.process_request_async(request)
        response = await self.get_response(request)
        response = await self.process_response_async(request, response)
        return response
    
    async def process_request_async(self, request):
        """Async version of process_request"""
        # Skip for non-authenticated users and static files
        if (not hasattr(request, 'user') or 
            request.path.startswith('/static/') or 
            request.path.startswith('/media/')):
            return None
        
        # Check if session exists and is valid
        if hasattr(request, 'session'):
            try:
                session_key = request.session.session_key
                
                # If no session key, create one
                if not session_key:
                    await sync_to_async(request.session.create)()
                    logger.info("Created new session for request")
                    return None
                
                # Verify session exists in database and is not corrupted
                try:
                    session_obj = await sync_to_async(Session.objects.get)(session_key=session_key)
                    # Test session data decoding
                    await sync_to_async(session_obj.get_decoded)()
                    
                except Session.DoesNotExist:
                    logger.warning(f"Session {session_key} not found in database")
                    # Create new session
                    await sync_to_async(request.session.flush)()
                    await sync_to_async(request.session.create)()
                    logger.info("Created new session after database lookup failed")
                    
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Session data corrupted for {session_key}: {str(e)}")
                    # Delete corrupted session and create new one
                    try:
                        await sync_to_async(Session.objects.filter(session_key=session_key).delete)()
                    except:
                        pass
                    await sync_to_async(request.session.flush)()
                    await sync_to_async(request.session.create)()
                    logger.info("Created new session after corruption detection")
                    
            except CreateError as e:
                logger.error(f"Failed to create session: {str(e)}")
                # Continue without session
                request.session = {}
                
            except Exception as e:
                logger.error(f"Unexpected session error: {str(e)}")
                # Continue without modifying session
        
        return None
    
    def process_request(self, request):
        """Sync version of process_request"""
        # Same logic but sync
        if (not hasattr(request, 'user') or 
            request.path.startswith('/static/') or 
            request.path.startswith('/media/')):
            return None
        
        if hasattr(request, 'session'):
            try:
                session_key = request.session.session_key
                
                if not session_key:
                    request.session.create()
                    logger.info("Created new session for request")
                    return None
                
                try:
                    session_obj = Session.objects.get(session_key=session_key)
                    session_obj.get_decoded()
                    
                except Session.DoesNotExist:
                    logger.warning(f"Session {session_key} not found in database")
                    request.session.flush()
                    request.session.create()
                    logger.info("Created new session after database lookup failed")
                    
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Session data corrupted for {session_key}: {str(e)}")
                    try:
                        Session.objects.filter(session_key=session_key).delete()
                    except:
                        pass
                    request.session.flush()
                    request.session.create()
                    logger.info("Created new session after corruption detection")
                    
            except CreateError as e:
                logger.error(f"Failed to create session: {str(e)}")
                request.session = {}
                
            except Exception as e:
                logger.error(f"Unexpected session error: {str(e)}")
        
        return None
    
    async def process_response_async(self, request, response):
        """Async version of process_response"""
        # Clean up session if it's causing issues
        if hasattr(request, 'session') and hasattr(request, 'user'):
            try:
                # Don't save empty sessions to reduce database writes
                if (not request.session.modified and 
                    not request.session.keys() and 
                    not request.user.is_authenticated):
                    await sync_to_async(request.session.flush)()
                    
                # Limit session data size to prevent corruption
                if hasattr(request.session, '_session'):
                    session_size = len(str(request.session._session))
                    if session_size > 4096:  # 4KB limit
                        logger.warning(f"Session data too large: {session_size} bytes")
                        # Keep only essential data
                        essential_keys = ['_auth_user_id', '_auth_user_backend', '_auth_user_hash']
                        current_session = request.session._session.copy()
                        await sync_to_async(request.session.clear)()
                        for key in essential_keys:
                            if key in current_session:
                                request.session[key] = current_session[key]
                        
            except Exception as e:
                logger.error(f"Session cleanup error in response: {str(e)}")
        
        return response
    
    def process_response(self, request, response):
        """Sync version of process_response"""
        if hasattr(request, 'session') and hasattr(request, 'user'):
            try:
                if (not request.session.modified and 
                    not request.session.keys() and 
                    not request.user.is_authenticated):
                    request.session.flush()
                    
                if hasattr(request.session, '_session'):
                    session_size = len(str(request.session._session))
                    if session_size > 4096:
                        logger.warning(f"Session data too large: {session_size} bytes")
                        essential_keys = ['_auth_user_id', '_auth_user_backend', '_auth_user_hash']
                        current_session = request.session._session.copy()
                        request.session.clear()
                        for key in essential_keys:
                            if key in current_session:
                                request.session[key] = current_session[key]
                        
            except Exception as e:
                logger.error(f"Session cleanup error in response: {str(e)}")
        
        return response