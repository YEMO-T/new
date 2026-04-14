import asyncio
from service.llm_service import rate_limiter

async def test_rate_limiter():
    print("Testing rate limiter...")
    
    # Test 1: Multiple calls within time frame
    user_id = "test_user"
    print(f"\nTesting multiple calls for user: {user_id}")
    
    for i in range(35):  # Try to make more than the limit (30)
        allowed = await rate_limiter.check_limit(user_id)
        print(f"Call {i+1}: {'Allowed' if allowed else 'Rate limited'}")
        if not allowed:
            print("Rate limit reached!")
            break
        await asyncio.sleep(0.1)  # Short delay between calls
    
    # Test 2: Wait and test again
    print("\nWaiting for rate limit to reset...")
    await asyncio.sleep(65)  # Wait more than the time frame (60 seconds)
    
    print("\nTesting again after reset")
    allowed = await rate_limiter.check_limit(user_id)
    print(f"Call after reset: {'Allowed' if allowed else 'Rate limited'}")

if __name__ == "__main__":
    asyncio.run(test_rate_limiter())
