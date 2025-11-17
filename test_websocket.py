import asyncio
import websockets
import json
import sys

async def test_security_websocket():
    try:
        print("🔗 Testing Security WebSocket...")
        async with websockets.connect('ws://localhost:8000/ws/security/') as websocket:
            print("✅ Security WebSocket: Connected successfully!")
            
            # Wait for initial connection message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"�� Security - Initial message: {data}")
            
            # Test heartbeat
            heartbeat_msg = json.dumps({'type': 'heartbeat'})
            await websocket.send(heartbeat_msg)
            print("📤 Security - Sent heartbeat")
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Security - Heartbeat response: {data}")
            
            # Test activity reporting
            activity_msg = json.dumps({
                'type': 'report_activity', 
                'activity_type': 'page_view',
                'page': '/dashboard',
                'action': 'view'
            })
            await websocket.send(activity_msg)
            print("📤 Security - Sent activity report")
            
    except Exception as e:
        print(f"❌ Security WebSocket error: {e}")
        return False
    return True

async def test_notification_websocket():
    try:
        print("\n🔗 Testing Notification WebSocket...")
        async with websockets.connect('ws://localhost:8000/ws/notifications/') as websocket:
            print("✅ Notification WebSocket: Connected successfully!")
            
            # Wait for initial connection message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Notification - Initial message: {data}")
            
            # Test heartbeat
            heartbeat_msg = json.dumps({'type': 'heartbeat'})
            await websocket.send(heartbeat_msg)
            print("📤 Notification - Sent heartbeat")
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Notification - Heartbeat response: {data}")
            
    except Exception as e:
        print(f"❌ Notification WebSocket error: {e}")
        return False
    return True

async def main():
    print("🚀 Starting WebSocket Connection Tests...")
    print("=" * 50)
    
    security_success = await test_security_websocket()
    notification_success = await test_notification_websocket()
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS:")
    print(f"   Security WebSocket: {'✅ PASS' if security_success else '❌ FAIL'}")
    print(f"   Notification WebSocket: {'✅ PASS' if notification_success else '❌ FAIL'}")
    
    if security_success and notification_success:
        print("\n🎉 ALL TESTS PASSED! WebSocket system is working correctly!")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())
