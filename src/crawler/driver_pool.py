# Generated: 2025-10-06 18:15:00 KST
"""
ChromeDriver 연결 풀 관리자
- 드라이버 재사용으로 안정성 향상
- 자동 재생성 및 헬스체크
- 스레드 세이프 구현
"""

import threading
import time
from typing import Optional
from queue import Queue, Empty
from loguru import logger
from contextlib import contextmanager


class DriverPool:
    """ChromeDriver 연결 풀"""

    def __init__(self, pool_size: int = 3, max_uses_per_driver: int = 50):
        """
        Args:
            pool_size: 풀에 유지할 드라이버 수
            max_uses_per_driver: 드라이버당 최대 사용 횟수 (이후 재생성)
        """
        self.pool_size = pool_size
        self.max_uses_per_driver = max_uses_per_driver
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self.driver_stats = {}  # driver_id -> use_count
        self.driver_options = None
        self.driver_service = None
        self.initialized = False

    def initialize(self, chrome_options, chrome_service):
        """풀 초기화"""
        self.driver_options = chrome_options
        self.driver_service = chrome_service

        with self.lock:
            if self.initialized:
                logger.warning("Driver pool already initialized")
                return

            logger.info(f"Initializing driver pool with {self.pool_size} drivers")
            for i in range(self.pool_size):
                driver = self._create_driver()
                if driver:
                    driver_id = id(driver)
                    self.driver_stats[driver_id] = 0
                    self.pool.put(driver)
                    logger.info(f"Added driver {i+1}/{self.pool_size} to pool (id={driver_id})")

            self.initialized = True
            logger.info(f"Driver pool initialized with {self.pool.qsize()} drivers")

    def _create_driver(self):
        """새 ChromeDriver 생성"""
        try:
            from selenium import webdriver

            driver = webdriver.Chrome(
                service=self.driver_service,
                options=self.driver_options
            )

            # WebDriver 속성 숨기기 (봇 탐지 우회)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                '''
            })

            logger.debug(f"Created new driver: {id(driver)}")
            return driver

        except Exception as e:
            logger.error(f"Failed to create driver: {e}")
            return None

    def _is_driver_healthy(self, driver) -> bool:
        """드라이버 헬스체크"""
        try:
            # 간단한 JavaScript 실행으로 드라이버 상태 확인
            driver.execute_script("return document.readyState")
            return True
        except:
            return False

    @contextmanager
    def get_driver(self, timeout: int = 30):
        """
        Context Manager로 드라이버 가져오기

        Usage:
            with driver_pool.get_driver() as driver:
                driver.get(url)
                # ... 작업 수행
        """
        driver = None
        driver_id = None
        acquired = False

        try:
            # 풀에서 드라이버 가져오기
            driver = self.pool.get(timeout=timeout)
            driver_id = id(driver)
            acquired = True

            # 헬스체크
            if not self._is_driver_healthy(driver):
                logger.warning(f"Driver {driver_id} is unhealthy, recreating...")
                try:
                    driver.quit()
                except:
                    pass
                driver = self._create_driver()
                if driver:
                    driver_id = id(driver)
                    self.driver_stats[driver_id] = 0
                else:
                    raise RuntimeError("Failed to recreate driver")

            # 사용 횟수 증가
            self.driver_stats[driver_id] = self.driver_stats.get(driver_id, 0) + 1

            # 최대 사용 횟수 체크
            if self.driver_stats[driver_id] >= self.max_uses_per_driver:
                logger.info(f"Driver {driver_id} reached max uses ({self.max_uses_per_driver}), will recreate")
                # yield 후 재생성됨

            yield driver

        except Empty:
            logger.error(f"Timeout waiting for driver from pool (timeout={timeout}s)")
            raise RuntimeError("No driver available in pool")

        except Exception as e:
            logger.error(f"Error getting driver from pool: {e}")
            raise

        finally:
            # 드라이버를 풀로 반환 또는 재생성
            if driver and acquired:
                try:
                    # 최대 사용 횟수 도달 시 재생성
                    if self.driver_stats.get(driver_id, 0) >= self.max_uses_per_driver:
                        logger.info(f"Recreating driver {driver_id} after {self.driver_stats[driver_id]} uses")
                        driver.quit()
                        new_driver = self._create_driver()
                        if new_driver:
                            new_driver_id = id(new_driver)
                            self.driver_stats[new_driver_id] = 0
                            self.pool.put(new_driver)
                            del self.driver_stats[driver_id]
                        else:
                            # 재생성 실패 시 기존 드라이버 재사용
                            logger.error("Failed to recreate driver, reusing old one")
                            self.pool.put(driver)
                    else:
                        # 정상 반환
                        self.pool.put(driver)

                except Exception as e:
                    logger.error(f"Error returning driver to pool: {e}")
                    # 드라이버 종료 시도
                    try:
                        if driver:
                            driver.quit()
                    except:
                        pass

    def shutdown(self):
        """풀 종료 - 모든 드라이버 정리"""
        logger.info("Shutting down driver pool...")

        with self.lock:
            while not self.pool.empty():
                try:
                    driver = self.pool.get_nowait()
                    driver.quit()
                    logger.debug(f"Closed driver: {id(driver)}")
                except Empty:
                    break
                except Exception as e:
                    logger.error(f"Error closing driver: {e}")

            self.driver_stats.clear()
            self.initialized = False
            logger.info("Driver pool shutdown complete")

    def get_stats(self) -> dict:
        """풀 통계 반환"""
        return {
            'pool_size': self.pool_size,
            'available_drivers': self.pool.qsize(),
            'driver_stats': dict(self.driver_stats),
            'total_drivers': len(self.driver_stats)
        }
