import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_calls: int, time_frame: int):
        """
        初始化速率限制器
        max_calls: 时间框架内最大调用次数
        time_frame: 时间框架（秒）
        """
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.calls = defaultdict(list)  # {user_id: [timestamp1, timestamp2, ...]}
    
    def check_limit(self, user_id: str) -> bool:
        """
        检查用户是否超过速率限制
        返回 True 表示允许调用，False 表示超过限制
        """
        current_time = time.time()
        
        # 清理过期的调用记录
        self.calls[user_id] = [t for t in self.calls[user_id] if current_time - t < self.time_frame]
        
        # 检查是否超过限制
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        
        # 记录本次调用
        self.calls[user_id].append(current_time)
        return True

# 测试速率限制器
def test_rate_limiter():
    print("Testing rate limiter...")
    
    # 创建速率限制器（每60秒最多30次调用）
    rate_limiter = RateLimiter(max_calls=30, time_frame=60)
    
    # 测试1: 在短时间内多次调用
    user_id = "test_user"
    print(f"\nTesting multiple calls for user: {user_id}")
    
    for i in range(35):  # 尝试超过限制（30次）
        allowed = rate_limiter.check_limit(user_id)
        print(f"Call {i+1}: {'Allowed' if allowed else 'Rate limited'}")
        if not allowed:
            print("Rate limit reached!")
            break
        time.sleep(0.1)  # 调用之间的短暂延迟
    
    # 测试2: 等待一段时间后再次测试
    print("\nWaiting for rate limit to reset...")
    time.sleep(65)  # 等待超过时间框架（60秒）
    
    print("\nTesting again after reset")
    allowed = rate_limiter.check_limit(user_id)
    print(f"Call after reset: {'Allowed' if allowed else 'Rate limited'}")

if __name__ == "__main__":
    test_rate_limiter()
