# shared/cache.py
import time
from typing import Any, Optional, Dict, List
from threading import Lock
import json
from datetime import datetime, timedelta


class InMemoryCache:
    """Thread-safe in-memory cache for microservices"""

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Initialize cache
        :param default_ttl: Default time-to-live in seconds (5 minutes)
        :param max_size: Maximum number of entries
        """
        self.cache: Dict[str, Dict] = {}
        self.lock = Lock()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "total_requests": 0
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self.lock:
            self.stats["total_requests"] += 1

            if key in self.cache:
                entry = self.cache[key]

                if time.time() > entry["expires_at"]:
                    del self.cache[key]
                    self.stats["evictions"] += 1
                    self.stats["misses"] += 1
                    return None

                entry["last_accessed"] = time.time()
                entry["access_count"] += 1
                self.stats["hits"] += 1

                return entry["value"]

            self.stats["misses"] += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        if ttl is None:
            ttl = self.default_ttl

        with self.lock:
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()

            expires_at = time.time() + ttl
            self.cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "last_accessed": time.time(),
                "created_at": time.time(),
                "access_count": 0,
                "ttl": ttl
            }
            self.stats["sets"] += 1

            if len(self.cache) % 50 == 0:
                self._cleanup_expired()

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats["deletes"] += 1
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            # Reset stats but keep type
            self.stats = {k: 0 for k in self.stats.keys()}

    def _evict_lru(self) -> None:
        """Remove least recently used entry"""
        if not self.cache:
            return

        lru_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k]["last_accessed"]
        )

        del self.cache[lru_key]
        self.stats["evictions"] += 1

    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry["expires_at"]
        ]

        for key in expired_keys:
            del self.cache[key]
            self.stats["evictions"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            hit_rate = (self.stats["hits"] / self.stats["total_requests"] * 100) if self.stats[
                                                                                        "total_requests"] > 0 else 0

            return {
                **self.stats,
                "total_entries": len(self.cache),
                "hit_rate_percent": round(hit_rate, 2),
                "memory_usage_estimate": self._estimate_memory_usage(),
                "max_size": self.max_size,
                "default_ttl": self.default_ttl
            }

    def _estimate_memory_usage(self) -> str:
        """Estimate memory usage of cache"""
        try:
            # Rough estimation
            total_size = len(str(self.cache).encode('utf-8'))
            if total_size < 1024:
                return f"{total_size} bytes"
            elif total_size < 1024 * 1024:
                return f"{total_size // 1024} KB"
            else:
                return f"{total_size // (1024 * 1024)} MB"
        except:
            return "Unknown"

    def get_keys(self) -> List[str]:
        """Get all cache keys"""
        with self.lock:
            return list(self.cache.keys())

    def get_entry_info(self, key: str) -> Optional[Dict]:
        """Get detailed info about cache entry"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                return {
                    "key": key,
                    "created_at": datetime.fromtimestamp(entry["created_at"]).isoformat(),
                    "last_accessed": datetime.fromtimestamp(entry["last_accessed"]).isoformat(),
                    "expires_at": datetime.fromtimestamp(entry["expires_at"]).isoformat(),
                    "access_count": entry["access_count"],
                    "ttl": entry["ttl"],
                    "is_expired": time.time() > entry["expires_at"],
                    "value_type": type(entry["value"]).__name__,
                    "value_size": len(str(entry["value"]))
                }
            return None


# Service-specific cache instances with different configurations
user_cache = InMemoryCache(default_ttl=600, max_size=500)  # 10 minutes, 500 users
car_cache = InMemoryCache(default_ttl=300, max_size=1000)  # 5 minutes, 1000 cars
rental_cache = InMemoryCache(default_ttl=180, max_size=2000)  # 3 minutes, 2000 rentals


class CacheService:
    """High-level cache management for all services"""

    @staticmethod
    def get_user(user_id: str) -> Optional[dict]:
        """Get user from cache"""
        return user_cache.get(f"user:{user_id}")

    @staticmethod
    def set_user(user_id: str, user_data: dict, ttl: int = 600) -> None:
        """Cache user data"""
        user_cache.set(f"user:{user_id}", user_data, ttl)

    @staticmethod
    def get_all_users() -> Optional[list]:
        """Get all users from cache"""
        return user_cache.get("all_users")

    @staticmethod
    def set_all_users(users_data: list, ttl: int = 300) -> None:
        """Cache all users data"""
        user_cache.set("all_users", users_data, ttl)

    @staticmethod
    def invalidate_user(user_id: str) -> None:
        """Remove user from cache"""
        user_cache.delete(f"user:{user_id}")
        user_cache.delete("all_users")

    @staticmethod
    def get_car(car_id: str) -> Optional[dict]:
        """Get car from cache"""
        return car_cache.get(f"car:{car_id}")

    @staticmethod
    def set_car(car_id: str, car_data: dict, ttl: int = 300) -> None:
        """Cache car data"""
        car_cache.set(f"car:{car_id}", car_data, ttl)

    @staticmethod
    def get_all_cars() -> Optional[list]:
        """Get all cars from cache"""
        return car_cache.get("all_cars")

    @staticmethod
    def set_all_cars(cars_data: list, ttl: int = 300) -> None:
        """Cache all cars data"""
        car_cache.set("all_cars", cars_data, ttl)

    @staticmethod
    def get_available_cars(location: str) -> Optional[list]:
        """Get available cars for location from cache"""
        return car_cache.get(f"available_cars:{location.lower()}")

    @staticmethod
    def set_available_cars(location: str, cars_data: list, ttl: int = 120) -> None:
        """Cache available cars for location"""
        car_cache.set(f"available_cars:{location.lower()}", cars_data, ttl)

    @staticmethod
    def get_cars_by_status(status: str) -> Optional[list]:
        """Get cars by status from cache"""
        return car_cache.get(f"cars_status:{status}")

    @staticmethod
    def set_cars_by_status(status: str, cars_data: list, ttl: int = 180) -> None:
        """Cache cars by status"""
        car_cache.set(f"cars_status:{status}", cars_data, ttl)

    @staticmethod
    def invalidate_car_cache(car_id: str = None) -> None:
        """Invalidate car cache"""
        if car_id:
            car_cache.delete(f"car:{car_id}")

        car_cache.delete("all_cars")
        keys_to_delete = [key for key in car_cache.get_keys()
                          if key.startswith("available_cars:") or key.startswith("cars_status:")]
        for key in keys_to_delete:
            car_cache.delete(key)

    @staticmethod
    def get_rental(rental_id: str) -> Optional[dict]:
        """Get rental from cache"""
        return rental_cache.get(f"rental:{rental_id}")

    @staticmethod
    def set_rental(rental_id: str, rental_data: dict, ttl: int = 180) -> None:
        """Cache rental data"""
        rental_cache.set(f"rental:{rental_id}", rental_data, ttl)

    @staticmethod
    def get_all_rentals() -> Optional[list]:
        """Get all rentals from cache"""
        return rental_cache.get("all_rentals")

    @staticmethod
    def set_all_rentals(rentals_data: list, ttl: int = 180) -> None:
        """Cache all rentals data"""
        rental_cache.set("all_rentals", rentals_data, ttl)

    @staticmethod
    def get_rental_metrics() -> Optional[dict]:
        """Get rental metrics from cache"""
        return rental_cache.get("rental_metrics")

    @staticmethod
    def set_rental_metrics(metrics_data: dict, ttl: int = 60) -> None:
        """Cache rental metrics (short TTL for fresh data)"""
        rental_cache.set("rental_metrics", metrics_data, ttl)

    @staticmethod
    def invalidate_rental_cache(rental_id: str = None) -> None:
        """Invalidate rental cache"""
        if rental_id:
            rental_cache.delete(f"rental:{rental_id}")

        rental_cache.delete("all_rentals")
        rental_cache.delete("rental_metrics")

    @staticmethod
    def get_all_cache_stats() -> dict:
        """Get statistics for all caches"""
        return {
            "user_cache": user_cache.get_stats(),
            "car_cache": car_cache.get_stats(),
            "rental_cache": rental_cache.get_stats(),
            "total_cache_entries": (
                    user_cache.get_stats()["total_entries"] +
                    car_cache.get_stats()["total_entries"] +
                    rental_cache.get_stats()["total_entries"]
            )
        }

    @staticmethod
    def clear_all_caches() -> None:
        """Clear all service caches"""
        user_cache.clear()
        car_cache.clear()
        rental_cache.clear()