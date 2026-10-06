"""
MintStatLab - System Data & Telemetry Collector
Harvests live process statistics, system event timestamps, and time-series buffers.
"""

import time
import subprocess
import json
from typing import Dict, List, Any
import numpy as np
import psutil


class ProcessRecord:
    def __init__(self, pid: int, name: str, user: str, cpu_pct: float, rss_mb: float, vms_mb: float,
                 threads: int, status: str, create_time: float, age_seconds: float, category: str):
        self.pid = pid
        self.name = name
        self.user = user
        self.cpu_pct = cpu_pct
        self.rss_mb = rss_mb
        self.vms_mb = vms_mb
        self.threads = threads
        self.status = status
        self.create_time = create_time
        self.age_seconds = age_seconds
        self.category = category
        self.mod_z_rss = 0.0
        self.mod_z_cpu = 0.0
        self.is_outlier = False


class TelemetrySnapshot:
    def __init__(self):
        self.timestamp = time.time()
        self.processes: List[ProcessRecord] = []
        self.total_rss_mb = 0.0
        self.total_cpu_pct = 0.0
        self.mem_percent = 0.0
        self.cpu_count = psutil.cpu_count(logical=True) or 1
        self.kernel_thread_count = 0
        self.user_app_count = 0
        self.daemon_count = 0


def classify_process(name: str, pid: int, user: str, rss_mb: float) -> str:
    """Categorizes process into User App, System Daemon, or Kernel Worker."""
    if rss_mb == 0.0 or pid < 100 or name.startswith("kworker") or name.startswith("ksoftirqd"):
        return "Kernel Worker"
    
    gui_names = {
        "cinnamon", "firefox", "xed", "nemo", "discord", "mintinstall", "gnome-terminal-server",
        "mint-autoclicker", "statdisk", "mintsweep", "python3", "code", "vscodium"
    }
    
    if user == "sam" and (name.lower() in gui_names or any(g in name.lower() for g in ["terminal", "panel", "cinnamon", "browser", "chat"])):
        return "User Application"
    
    return "System Daemon"


def collect_process_snapshot() -> TelemetrySnapshot:
    """Collects comprehensive snapshot of all processes running on Linux Mint."""
    snap = TelemetrySnapshot()
    vm = psutil.virtual_memory()
    snap.mem_percent = vm.percent
    now = time.time()

    procs: List[ProcessRecord] = []

    for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'num_threads', 'status', 'create_time']):
        try:
            info = p.info
            pid = info['pid']
            name = info['name'] or f"proc_{pid}"
            user = info['username'] or "system"
            cpu_pct = float(info['cpu_percent'] or 0.0)
            mem_info = info['memory_info']
            rss_mb = (mem_info.rss / 1024**2) if mem_info else 0.0
            vms_mb = (mem_info.vms / 1024**2) if mem_info else 0.0
            threads = int(info['num_threads'] or 1)
            status = info['status'] or "running"
            ctime = float(info['create_time'] or now)
            age_sec = max(0.0, now - ctime)

            cat = classify_process(name, pid, user, rss_mb)
            if cat == "Kernel Worker":
                snap.kernel_thread_count += 1
            elif cat == "User Application":
                snap.user_app_count += 1
            else:
                snap.daemon_count += 1

            record = ProcessRecord(
                pid=pid,
                name=name,
                user=user,
                cpu_pct=cpu_pct,
                rss_mb=rss_mb,
                vms_mb=vms_mb,
                threads=threads,
                status=status,
                create_time=ctime,
                age_seconds=age_sec,
                category=cat
            )
            procs.append(record)
            snap.total_rss_mb += rss_mb
            snap.total_cpu_pct += cpu_pct
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    snap.processes = procs
    return snap


def collect_system_events(max_events: int = 300) -> List[float]:
    """Retrieves timestamps of recent system journal events."""
    timestamps: List[float] = []
    try:
        cmd = ['journalctl', '-n', str(max_events), '-o', 'json', '--quiet']
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3)
        if p.returncode == 0:
            for line in p.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if '__REALTIME_TIMESTAMP' in entry:
                        timestamps.append(float(entry['__REALTIME_TIMESTAMP']) / 1e6)
                except Exception:
                    continue
    except Exception:
        pass

    if len(timestamps) < 10:
        # Fallback to simulated process start timestamps if journal is restricted
        now = time.time()
        for p in psutil.process_iter(['create_time']):
            try:
                ct = p.info.get('create_time')
                if ct and ct > now - 86400:
                    timestamps.append(float(ct))
            except Exception:
                continue

    return sorted(timestamps)


class SystemTimeSeriesBuffer:
    """Maintains a rolling temporal window of system load metrics for drift regression."""
    def __init__(self, max_points: int = 300):
        self.max_points = max_points
        self.timestamps: List[float] = []
        self.ram_mb_series: List[float] = []
        self.cpu_pct_series: List[float] = []
        self.process_count_series: List[int] = []

    def append_sample(self, ram_mb: float, cpu_pct: float, proc_count: int):
        self.timestamps.append(time.time())
        self.ram_mb_series.append(ram_mb)
        self.cpu_pct_series.append(cpu_pct)
        self.process_count_series.append(proc_count)

        if len(self.timestamps) > self.max_points:
            self.timestamps.pop(0)
            self.ram_mb_series.pop(0)
            self.cpu_pct_series.pop(0)
            self.process_count_series.pop(0)

    def size(self) -> int:
        return len(self.timestamps)

    def get_ram_series(self) -> List[float]:
        return list(self.ram_mb_series)

    def get_cpu_series(self) -> List[float]:
        return list(self.cpu_pct_series)
