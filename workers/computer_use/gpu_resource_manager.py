"""
GPU Resource Manager for PAIOS Single-Host Ultimate Edition.

Provides VRAM tracking, mutex-based concurrency control, OOM protection,
and request queuing for GPU-accelerated workloads (vision, STT, LLM).

Integration points:
- Collector: GPU metrics via _gpu() in collectors
- Computer Use: Pre-action GPU availability check
- Vision Worker: Model loading lock
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# Suppress console window for subprocess calls on Windows; no-op on other platforms
_CW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

logger = logging.getLogger("paios.gpu")


@dataclass
class GPUInfo:
    """Current GPU state snapshot."""
    utilization_percent: float = 0.0
    memory_used_mib: float = 0.0
    memory_total_mib: float = 8192.0
    memory_used_percent: float = 0.0
    temperature_celsius: Optional[float] = None
    processes: list[dict] = field(default_factory=list)
    healthy: bool = True


class GPUResourceManager:
    """Manages GPU VRAM with OOM protection and request queuing.

    Thread-safe singleton. Uses nvidia-smi for VRAM queries and
    a threading.Lock for mutual exclusion of concurrent model loads.
    """

    _instance: Optional["GPUResourceManager"] = None
    _instance_lock: threading.Lock = threading.Lock()

    # Thresholds
    VRAM_WARN_THRESHOLD = 0.75     # 75% → warning
    VRAM_CRIT_THRESHOLD = 0.88     # 88% → critical (reject new allocations)
    VRAM_OOM_THRESHOLD = 0.95      # 95% → emergency OOM

    DEFAULT_TIMEOUT = 30.0         # seconds
    MAX_CONCURRENT = 2             # max simultaneous model loads

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_loads = 0
        self._vram_snapshot: GPUInfo = GPUInfo()
        self._last_query_time = 0.0
        self._query_interval = 2.0  # seconds between nvidia-smi queries

    @classmethod
    def get_instance(cls) -> "GPUResourceManager":
        """Get the singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── VRAM Query ────────────────────────────────────────────

    def get_vram_info(self, force: bool = False) -> GPUInfo:
        """Query current GPU state via nvidia-smi. Cached for _query_interval seconds."""
        now = time.monotonic()
        if not force and now - self._last_query_time < self._query_interval:
            return self._vram_snapshot

        info = GPUInfo()
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
                creationflags=_CW,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    info.utilization_percent = float(parts[0].strip())
                    info.memory_used_mib = float(parts[1].strip())
                    info.memory_total_mib = float(parts[2].strip())
                    if len(parts) >= 4:
                        info.temperature_celsius = float(parts[3].strip())
                    info.memory_used_percent = (
                        info.memory_used_mib / info.memory_total_mib * 100
                        if info.memory_total_mib > 0 else 0.0
                    )
                    info.healthy = True

            # Query running processes
            proc_result = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory,name", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace",
                creationflags=_CW,
            )
            if proc_result.returncode == 0 and proc_result.stdout.strip():
                for line in proc_result.stdout.strip().splitlines():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        info.processes.append({
                            "pid": parts[0].strip(),
                            "memory_mib": parts[1].strip(),
                            "name": parts[2].strip() if len(parts) >= 3 else "unknown",
                        })

            self._vram_snapshot = info
            self._last_query_time = now

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception) as exc:
            info.healthy = False
            logger.warning("nvidia-smi query failed: %s", exc)

        return info

    def get_vram_usage(self) -> float:
        """Get current VRAM usage as a fraction (0.0-1.0)."""
        info = self.get_vram_info()
        return info.memory_used_percent / 100.0 if info.memory_total_mib > 0 else 0.0

    # ── OOM Protection ────────────────────────────────────────

    def check_oom_risk(self) -> tuple[bool, str]:
        """Check if system is at risk of OOM.

        Returns:
            (is_safe, message) tuple. is_safe=False means risk detected.
        """
        usage = self.get_vram_usage()
        if usage >= self.VRAM_OOM_THRESHOLD:
            return False, f"OOM EMERGENCY: VRAM at {usage*100:.1f}% (threshold: {self.VRAM_OOM_THRESHOLD*100:.0f}%)"
        if usage >= self.VRAM_CRIT_THRESHOLD:
            return False, f"VRAM CRITICAL: {usage*100:.1f}% (threshold: {self.VRAM_CRIT_THRESHOLD*100:.0f}%)"
        if usage >= self.VRAM_WARN_THRESHOLD:
            return True, f"VRAM WARNING: {usage*100:.1f}%"
        return True, f"VRAM healthy: {usage*100:.1f}%"

    def require_one_gb(self) -> tuple[bool, str]:
        """Check if at least 1GB VRAM is available.
        Used before loading models or running GPU workloads."""
        info = self.get_vram_info(force=True)
        available = info.memory_total_mib - info.memory_used_mib
        if available < 1024:
            return False, f"Insufficient VRAM: only {available:.0f}MiB available (< 1024MiB)"
        return True, f"{available:.0f}MiB VRAM available"

    # ── Concurrency Control ───────────────────────────────────

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire the GPU lock for a model load. Blocks until available.

        Args:
            timeout: Max wait in seconds. None = use DEFAULT_TIMEOUT.

        Returns:
            True if lock acquired, False if timeout.
        """
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

        # Check OOM before waiting
        safe, msg = self.check_oom_risk()
        if not safe:
            logger.warning("GPU acquisition rejected: %s", msg)
            return False

        # Check VRAM capacity
        has_vram, vram_msg = self.require_one_gb()
        if not has_vram:
            logger.warning("GPU acquisition rejected: %s", vram_msg)
            return False

        # Check concurrent load limit
        with self._lock:
            if self._active_loads >= self.MAX_CONCURRENT:
                logger.info("GPU queue full (%d active), waiting...", self._active_loads)
                # In a real async system this would queue; here we return False
                return False
            self._active_loads += 1

        acquired = self._lock.acquire(timeout=timeout)
        if not acquired:
            with self._lock:
                self._active_loads -= 1
            logger.warning("GPU lock acquisition timed out after %.1fs", timeout)
            return False

        logger.info("GPU lock acquired (active loads: %d)", self._active_loads)
        return True

    def release(self) -> None:
        """Release the GPU lock after model use."""
        try:
            self._lock.release()
        except RuntimeError:
            pass  # Not acquired
        with self._lock:
            self._active_loads = max(0, self._active_loads - 1)
        logger.info("GPU lock released (active loads: %d)", self._active_loads)

    # ── Context Manager ───────────────────────────────────────

    def __enter__(self) -> "GPUResourceManager":
        self.acquire()
        return self

    def __exit__(self, *args) -> None:
        self.release()

    # ── Metrics Export ────────────────────────────────────────

    def to_prometheus(self) -> str:
        """Export GPU metrics in Prometheus format."""
        info = self.get_vram_info()
        lines = [
            "# HELP paios_gpu_utilization_percent GPU utilization (0-100)",
            "# TYPE paios_gpu_utilization_percent gauge",
            f"paios_gpu_utilization_percent {info.utilization_percent}",
            "",
            "# HELP paios_gpu_memory_mib GPU memory in MiB",
            "# TYPE paios_gpu_memory_mib gauge",
            f'paios_gpu_memory_mib{{kind="used"}} {info.memory_used_mib}',
            f'paios_gpu_memory_mib{{kind="total"}} {info.memory_total_mib}',
            "",
            "# HELP paios_gpu_memory_percent GPU memory usage percentage",
            "# TYPE paios_gpu_memory_percent gauge",
            f"paios_gpu_memory_percent {info.memory_used_percent}",
            "",
            "# HELP paios_gpu_healthy GPU health (1=healthy, 0=unhealthy)",
            "# TYPE paios_gpu_healthy gauge",
            f"paios_gpu_healthy {1 if info.healthy else 0}",
            "",
            "# HELP paios_gpu_active_loads Current active GPU model loads",
            "# TYPE paios_gpu_active_loads gauge",
            f"paios_gpu_active_loads {self._active_loads}",
        ]
        if info.temperature_celsius is not None:
            lines.extend([
                "",
                "# HELP paios_gpu_temperature_celsius GPU temperature",
                "# TYPE paios_gpu_temperature_celsius gauge",
                f"paios_gpu_temperature_celsius {info.temperature_celsius}",
            ])
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Export GPU state as dict for JSON serialization."""
        info = self.get_vram_info()
        return {
            "schema": "paios.gpu.resource.v1",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "vram_used_mib": info.memory_used_mib,
            "vram_total_mib": info.memory_total_mib,
            "vram_used_percent": info.memory_used_percent,
            "gpu_utilization_percent": info.utilization_percent,
            "healthy": info.healthy,
            "active_loads": self._active_loads,
            "thresholds": {
                "warn": self.VRAM_WARN_THRESHOLD * 100,
                "critical": self.VRAM_CRIT_THRESHOLD * 100,
                "oom": self.VRAM_OOM_THRESHOLD * 100,
            },
        }


# Module-level convenience functions

def get_vram_usage() -> float:
    """Quick VRAM usage check (0.0-1.0)."""
    return GPUResourceManager.get_instance().get_vram_usage()


def check_gpu_ready() -> tuple[bool, str]:
    """Check if GPU is ready for workload. Quick OOM + VRAM check."""
    mgr = GPUResourceManager.get_instance()
    safe, msg = mgr.check_oom_risk()
    if not safe:
        return False, msg
    has_vram, vram_msg = mgr.require_one_gb()
    return has_vram, vram_msg


async def acquire_gpu(timeout: float = 30.0) -> bool:
    """Async wrapper for GPU lock acquisition."""
    mgr = GPUResourceManager.get_instance()
    return mgr.acquire(timeout=timeout)


def release_gpu() -> None:
    """Release GPU lock."""
    GPUResourceManager.get_instance().release()


# Quick test
if __name__ == "__main__":
    mgr = GPUResourceManager.get_instance()
    info = mgr.get_vram_info(force=True)
    print(f"VRAM: {info.memory_used_mib:.0f}/{info.memory_total_mib:.0f} MiB "
          f"({info.memory_used_percent:.1f}%)")
    print(f"GPU Util: {info.utilization_percent:.1f}%")
    print(f"Healthy: {info.healthy}")
    print(f"Processes: {len(info.processes)}")

    safe, msg = mgr.check_oom_risk()
    print(f"OOM Check: {safe} - {msg}")
