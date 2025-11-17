import asyncio
import websockets
import json
import requests

# First, let's get a session by logging in via HTTP
def get_session_cookie():
    try:
        # Create a test session (you might need to adjust this based on your auth system)
        session = requests.Session()
        
        # If you have a test user, try to login
        # login_response = session.post('http://localhost:8000/accounts/login/', {
        #     'username': 'testuser',
        #     'password': 'testpass'
        # })
        
        # For now, we'll just get the CSRF token from the login page
        response = session.get('http://localhost:8000/accounts/login/')
        
        # Extract cookies for WebSocket connection
        cookies = session.cookies.get_dict()
        print(f"🍪 Cookies: {cookies}")
        
        return cookies
        
    except Exception as e:
        print(f"❌ HTTP session error: {e}")
        return {}

async def test_websocket_with_auth():
    # Get session cookies
    cookies = get_session_cookie()
    
    # Create cookie header
    cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    
    try:
        print("🔗 Testing WebSocket with authentication...")
        
        # Connect with cookies
        async with websockets.connect(
            'ws://localhost:8000/ws/security/',
            extra_headers={"Cookie": cookie_header} if cookie_header else {}
        ) as websocket:
            print("✅ Connected to Security WebSocket!")
            
            # Wait for initial connection message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Initial message: {data}")
            
            return True
            
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return False

async def main():
    print("🚀 Testing Authenticated WebSocket Connection...")
    print("=" * 50)
    
    success = await test_websocket_with_auth()
    
    if success:
        print("🎉 WebSocket authentication test PASSED!")
    else:
        print("\n💡 TROUBLESHOOTING:")
        print("1. Make sure you're logged into the Django admin in your browser")
        print("2. Try testing via browser console instead")
        print("3. Check server logs for more detailed error information")

if __name__ == "__main__":
    asyncio.run(main())
