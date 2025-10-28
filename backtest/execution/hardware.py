"""
Hardware detection and profiling module.

Provides hardware-aware configuration for optimal parallel execution.
Uses caching to avoid repeated detection on subsequent runs.
"""

import os
import json
import psutil
from typing import Optional


class HardwareProfile:
    """Hardware profile with one-time detection and caching."""
    
    CACHE_FILE = 'performance/hardware_profile.json'
    
    def __init__(self, physical_cores: int, logical_cores: int, total_ram_gb: float,
                 memory_per_worker_mb: float, signature: str):
        """
        Initialize hardware profile.
        
        Args:
            physical_cores: Number of physical CPU cores
            logical_cores: Number of logical CPU cores (with hyperthreading)
            total_ram_gb: Total RAM in GB
            memory_per_worker_mb: Estimated memory per worker process in MB
            signature: Hardware signature string for cache validation
        """
        self.physical_cores = physical_cores
        self.logical_cores = logical_cores
        self.total_ram_gb = total_ram_gb
        self.memory_per_worker_mb = memory_per_worker_mb
        self.signature = signature
    
    @classmethod
    def get_or_create(cls) -> 'HardwareProfile':
        """
        Load cached profile or detect if needed.
        
        Automatically redetects if hardware signature has changed.
        
        Returns:
            HardwareProfile instance
        """
        if os.path.exists(cls.CACHE_FILE):
            try:
                profile = cls._load_from_cache()
                if profile.signature_matches():
                    return profile
                # Signature mismatch - hardware changed, redetect
            except (json.JSONDecodeError, KeyError, ValueError):
                # Cache corrupted - redetect
                pass
        
        # First run or hardware changed - detect and cache
        return cls._detect_and_cache()
    
    def signature_matches(self) -> bool:
        """
        Check if current hardware matches cached signature.
        
        Returns:
            True if signature matches, False otherwise
        """
        current = self._get_current_signature()
        return current == self.signature
    
    @staticmethod
    def _get_current_signature() -> str:
        """
        Get current hardware signature (quick check without full profiling).
        
        Returns:
            Signature string: "{cores}c_{ram}gb"
        """
        physical_cores = psutil.cpu_count(logical=False)
        total_ram_gb = int(psutil.virtual_memory().total / (1024**3))
        return f"{physical_cores}c_{total_ram_gb}gb"
    
    @classmethod
    def _detect_and_cache(cls) -> 'HardwareProfile':
        """
        Detect hardware, profile memory usage, and save to cache.
        
        Returns:
            HardwareProfile instance
        """
        print("Detecting hardware capabilities...")
        
        # CPU detection
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        
        # Memory detection
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        
        # Memory profiling (run sample backtest to estimate per-worker memory)
        memory_per_worker_mb = cls._profile_memory_usage()
        
        # Create signature
        signature = cls._get_current_signature()
        
        profile = cls(
            physical_cores=physical_cores,
            logical_cores=logical_cores,
            total_ram_gb=total_ram_gb,
            memory_per_worker_mb=memory_per_worker_mb,
            signature=signature
        )
        
        profile._save_to_cache()
        print(f"✓ Hardware profile cached: {profile.signature}")
        return profile
    
    @classmethod
    def _profile_memory_usage(cls) -> float:
        """
        Profile memory usage by running a sample backtest.
        
        Returns:
            Estimated memory per worker in MB
        """
        try:
            import tracemalloc
            import pandas as pd
            from config.manager import ConfigManager
            from data.cache_manager import read_cache
            from backtest.engine import run_backtest
            from strategies import get_strategy_class
            
            # Create minimal config for profiling
            config = ConfigManager()
            
            # Try to get first available symbol/timeframe with cached data
            symbols = config.get_symbols()
            timeframes = config.get_timeframes()
            
            if not symbols or not timeframes:
                # No symbols or timeframes configured
                return 500.0
            
            # Find any combination with cached data
            for symbol in symbols[:5]:  # Try first 5 symbols
                for timeframe in timeframes[:2]:  # Try first 2 timeframes
                    df = read_cache(symbol, timeframe)
                    
                    # Filter by backtest date range if needed
                    if not df.empty:
                        start_date = config.get_start_date()
                        end_date = config.get_end_date()
                        start_dt = pd.to_datetime(start_date)
                        end_dt = pd.to_datetime(end_date)
                        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
                    
                    if not df.empty:
                        # Start memory tracking
                        tracemalloc.start()
                        
                        try:
                            # Run a sample backtest
                            strategy_class = get_strategy_class(config.get_strategy_name())
                            run_backtest(config, df, strategy_class, verbose=False)
                            
                            # Get peak memory
                            current, peak = tracemalloc.get_traced_memory()
                            
                            # Convert to MB and add safety margin
                            peak_mb = peak / (1024**2)
                            # Add 20% safety margin
                            estimated_per_worker = peak_mb * 1.2
                            
                            return max(estimated_per_worker, 300.0)  # Minimum 300 MB
                        finally:
                            tracemalloc.stop()
            
            # If no cached data found, use conservative estimate
            print("⚠️  No cached data found for memory profiling. Using conservative estimate.")
            return 500.0  # Conservative default
            
        except Exception as e:
            # If profiling fails, use conservative default
            print(f"⚠️  Memory profiling failed: {e}. Using conservative estimate.")
            return 500.0  # Conservative default in MB
    
    def _save_to_cache(self):
        """Save hardware profile to cache file."""
        os.makedirs('performance', exist_ok=True)
        
        cache_data = {
            'physical_cores': self.physical_cores,
            'logical_cores': self.logical_cores,
            'total_ram_gb': self.total_ram_gb,
            'memory_per_worker_mb': self.memory_per_worker_mb,
            'signature': self.signature
        }
        
        with open(self.CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    @classmethod
    def _load_from_cache(cls) -> 'HardwareProfile':
        """Load hardware profile from cache file."""
        with open(cls.CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        
        return cls(
            physical_cores=cache_data['physical_cores'],
            logical_cores=cache_data['logical_cores'],
            total_ram_gb=cache_data['total_ram_gb'],
            memory_per_worker_mb=cache_data['memory_per_worker_mb'],
            signature=cache_data['signature']
        )
    
    def calculate_optimal_workers(self, num_combinations: int, mode: str = 'auto',
                                   manual_workers: Optional[int] = None,
                                   memory_safety_factor: float = 0.75,
                                   cpu_reserve_cores: int = 1) -> int:
        """
        Calculate optimal worker count for given combination count.
        
        Args:
            num_combinations: Number of symbol/timeframe combinations to run
            mode: 'auto' or 'manual'
            manual_workers: Manual worker count (only used if mode='manual')
            memory_safety_factor: Fraction of RAM to use (default 0.75 = 75%)
            cpu_reserve_cores: Number of CPU cores to reserve (default 1)
        
        Returns:
            Optimal number of workers
        """
        if mode == 'manual' and manual_workers is not None:
            return max(1, manual_workers)
        
        # For very small runs, use single worker (no overhead)
        if num_combinations <= 3:
            return 1
        
        # Calculate constraints
        max_by_cpu = max(1, self.physical_cores - cpu_reserve_cores)
        max_by_memory = int((self.total_ram_gb * 1024 * memory_safety_factor) / self.memory_per_worker_mb)
        max_by_workload = num_combinations  # Never more workers than tasks
        
        # Take minimum of all constraints
        optimal = min(max_by_cpu, max_by_memory, max_by_workload)
        return max(1, optimal)  # At least 1 worker
