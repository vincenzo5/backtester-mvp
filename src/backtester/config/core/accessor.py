"""
Configuration accessor module.

Provides type-safe access to configuration values.
"""

from typing import Dict, List, Optional, Any
import warnings
from dataclasses import dataclass


@dataclass
class TradingConfig:
    """Trading configuration."""
    use_exchange_fees: bool
    fee_type: str  # 'maker' or 'taker'
    slippage: float
    risk_per_trade: float
    position_size: float
    commission: float
    commission_maker: float


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    name: str
    parameters: Dict[str, Any]


@dataclass
class DataQualityConfig:
    """Data quality configuration."""
    weights: Dict[str, float]
    thresholds: Dict[str, Any]
    warning_threshold: float
    liveliness_cache_days: int
    incremental_assessment: bool
    full_assessment_schedule: str
    gap_filling_schedule: str


@dataclass
class TracingConfig:
    """Tracing configuration."""
    enabled: bool
    level: str  # minimal, standard, detailed
    sample_rate: float


@dataclass
class AutoCaptureConfig:
    """Auto-capture configuration for crash reports."""
    triggers: List[str]
    min_severity: str  # error, warning, info


@dataclass
class CrashReportsConfig:
    """Crash reports configuration."""
    enabled: bool
    max_reports: int
    max_total_size_mb: float
    min_free_disk_mb: float
    auto_capture: AutoCaptureConfig


@dataclass
class LogRotationConfig:
    """Log rotation configuration."""
    max_bytes: int
    backup_count: int


@dataclass
class DebugLoggingConfig:
    """Debug logging configuration."""
    execution_trace_file: str
    crash_report_dir: str
    rotation: LogRotationConfig


@dataclass
class DebugConfig:
    """Debug configuration."""
    enabled: bool
    tracing: TracingConfig
    crash_reports: CrashReportsConfig
    logging: DebugLoggingConfig


class ConfigAccessor:
    """
    Type-safe access to configuration values.
    """
    
    def __init__(self, config: Dict[str, Any], metadata: Dict[str, Any] = None):
        """
        Initialize the accessor.
        
        Args:
            config: Merged configuration dictionary
            metadata: Exchange metadata dictionary
        """
        self.config = config
        self.metadata = metadata or {}
    
    # Data accessors
    def get_exchange_name(self) -> str:
        """Get the exchange name (from data config)."""
        return self.config.get('data', {}).get('exchange', 'coinbase')
    
    # Walk-forward accessors
    def get_walkforward_start_date(self) -> str:
        """Get start date for walk-forward optimization."""
        return self.config.get('walkforward', {}).get('start_date')
    
    def get_walkforward_end_date(self) -> str:
        """Get end date for walk-forward optimization."""
        return self.config.get('walkforward', {}).get('end_date')
    
    def get_walkforward_initial_capital(self) -> float:
        """Get initial capital for walk-forward optimization."""
        capital = self.config.get('walkforward', {}).get('initial_capital')
        return float(capital) if capital is not None else 100000.0
    
    def get_walkforward_symbols(self) -> List[str]:
        """
        Get symbols for walk-forward optimization.
        
        Returns symbols from walkforward config, validates against metadata.
        """
        symbols = self.config.get('walkforward', {}).get('symbols')
        
        if symbols is None:
            return []
        elif isinstance(symbols, str):
            return [symbols]
        elif isinstance(symbols, list):
            # Validate against metadata
            valid_symbols = self.metadata.get('top_markets', [])
            if valid_symbols:
                return [s for s in symbols if s in valid_symbols]
            return symbols
        else:
            return []
    
    def get_walkforward_timeframes(self) -> List[str]:
        """
        Get timeframes for walk-forward optimization.
        
        Returns timeframes from walkforward config, validates against metadata.
        """
        timeframes = self.config.get('walkforward', {}).get('timeframes')
        
        if timeframes is None:
            return []
        elif isinstance(timeframes, str):
            return [timeframes]
        elif isinstance(timeframes, list):
            # Validate against metadata
            valid_timeframes = self.metadata.get('timeframes', [])
            if valid_timeframes:
                return [tf for tf in timeframes if tf in valid_timeframes]
            return timeframes
        else:
            return []
    
    def get_walkforward_verbose(self) -> bool:
        """Get verbose flag for walk-forward optimization."""
        return self.config.get('walkforward', {}).get('verbose', False)
    
    # Trading accessors
    def get_trading_config(self) -> TradingConfig:
        """Get trading configuration as typed object."""
        trading = self.config.get('trading', {})
        return TradingConfig(
            use_exchange_fees=trading.get('use_exchange_fees', False),
            fee_type=trading.get('fee_type', 'taker'),
            slippage=float(trading.get('slippage', 0.0)),
            risk_per_trade=float(trading.get('risk_per_trade', 0.01)),
            position_size=float(trading.get('position_size', 0.1)),
            commission=float(trading.get('commission', 0.006)),
            commission_maker=float(trading.get('commission_maker', 0.004))
        )
    
    def get_commission(self) -> float:
        """Get commission rate for backtesting."""
        trading_config = self.get_trading_config()
        
        # Check if we should use exchange fees
        if trading_config.use_exchange_fees:
            fee_type = trading_config.fee_type
            return self.metadata.get('fees', {}).get(fee_type, 0.006)
        else:
            if trading_config.fee_type == 'maker':
                return trading_config.commission_maker
            else:
                return trading_config.commission
    
    def get_slippage(self) -> float:
        """Get slippage rate."""
        return self.get_trading_config().slippage
    
    # Strategy accessors
    def get_strategy_name(self) -> str:
        """Get the strategy name."""
        from backtester.config.core.exceptions import ConfigError
        if 'name' not in self.config.get('strategy', {}):
            raise ConfigError("Missing 'name' in strategy configuration")
        return self.config['strategy']['name']
    
    
    def get_strategy_config(self) -> StrategyConfig:
        """Get strategy configuration as typed object."""
        strategy = self.config.get('strategy', {})
        return StrategyConfig(
            name=strategy['name'],
            parameters=strategy.get('parameters', {})
        )
    
    # Data accessors
    def get_data_config(self) -> Dict[str, Any]:
        """Get data configuration dictionary."""
        return self.config.get('data', {}).copy()
    
    def get_historical_start_date(self) -> str:
        """Get historical start date for data collection."""
        return self.config.get('data', {}).get('historical_start_date', '2017-01-01')
    
    def get_data_exchange_name(self) -> str:
        """Get exchange name from data config (alias for get_exchange_name for clarity)."""
        return self.get_exchange_name()
    
    # Data quality accessors
    def get_data_quality_config(self) -> DataQualityConfig:
        """Get data quality configuration as typed object."""
        dq = self.config.get('data_quality', {})
        return DataQualityConfig(
            weights=dq.get('weights', {}),
            thresholds=dq.get('thresholds', {}),
            warning_threshold=float(dq.get('warning_threshold', 70)),
            liveliness_cache_days=int(dq.get('liveliness_cache_days', 30)),
            incremental_assessment=dq.get('incremental_assessment', True),
            full_assessment_schedule=dq.get('full_assessment_schedule', 'weekly'),
            gap_filling_schedule=dq.get('gap_filling_schedule', 'weekly')
        )
    
    # Parallel execution accessors
    def get_parallel_mode(self) -> str:
        """Get parallel execution mode: 'auto' or 'manual'."""
        return self.config.get('parallel', {}).get('mode', 'auto')
    
    def get_manual_workers(self) -> Optional[int]:
        """Get manual worker count (only used if mode='manual')."""
        workers = self.config.get('parallel', {}).get('max_workers')
        return int(workers) if workers is not None else None
    
    def get_memory_safety_factor(self) -> float:
        """Get memory safety factor for parallel execution."""
        return float(self.config.get('parallel', {}).get('memory_safety_factor', 0.75))
    
    def get_cpu_reserve_cores(self) -> int:
        """Get number of CPU cores to reserve for system."""
        return int(self.config.get('parallel', {}).get('cpu_reserve_cores', 1))
    
    # Walk-forward accessors
    def get_walkforward_periods(self) -> List[str]:
        """Get walk-forward period configurations (e.g., ["1Y/6M"])."""
        return self.config.get('walkforward', {}).get('periods', [])
    
    def get_walkforward_fitness_functions(self) -> List[str]:
        """
        Get fitness function names for walk-forward optimization.
        
        Returns:
            List of fitness function names (e.g., ["np_avg_dd", "net_profit"])
        """
        from backtester.config.core.exceptions import ConfigError
        fitness_funcs = self.config.get('walkforward', {}).get('fitness_functions', ['np_avg_dd'])
        if not isinstance(fitness_funcs, list):
            raise ConfigError(
                f"walkforward.fitness_functions must be a list, got {type(fitness_funcs)}. "
                f"Update config from 'fitness_function: \"...\"' to 'fitness_functions: [\"...\"]'"
            )
        return fitness_funcs
    
    def get_parameter_ranges(self) -> Dict[str, Dict[str, int]]:
        """Get parameter ranges for optimization (grid search)."""
        return self.config.get('walkforward', {}).get('parameter_ranges', {})
    
    def get_walkforward_filters(self) -> List[str]:
        """
        Get list of filter names for walk-forward optimization.
        
        Returns list of filter names from configuration (e.g., ['volatility_regime_atr'])
        Empty list if not configured or filters disabled.
        
        Returns:
            List of filter names (strings)
            Empty list if filters not configured
        
        Example:
            filters = config.get_walkforward_filters()
            # ['volatility_regime_atr', 'volatility_regime_stddev']
        """
        filters = self.config.get('walkforward', {}).get('filters', [])
        
        # Handle different input formats
        if filters is None:
            return []
        elif isinstance(filters, str):
            return [filters]  # Single filter name as string
        elif isinstance(filters, list):
            # Validate all are strings
            valid_filters = []
            for f in filters:
                if isinstance(f, str):
                    valid_filters.append(f)
                else:
                    warnings.warn(f"Ignoring invalid filter (must be string): {f}", UserWarning, stacklevel=2)
            return valid_filters
        else:
            return []
    
    # Debug accessors
    def get_debug_config(self) -> DebugConfig:
        """Get debug configuration as typed object."""
        debug = self.config.get('debug', {})
        tracing = debug.get('tracing', {})
        crash_reports = debug.get('crash_reports', {})
        auto_capture = crash_reports.get('auto_capture', {})
        logging = debug.get('logging', {})
        rotation = logging.get('rotation', {})
        
        return DebugConfig(
            enabled=debug.get('enabled', True),
            tracing=TracingConfig(
                enabled=tracing.get('enabled', True),
                level=tracing.get('level', 'standard'),
                sample_rate=float(tracing.get('sample_rate', 1.0))
            ),
            crash_reports=CrashReportsConfig(
                enabled=crash_reports.get('enabled', True),
                max_reports=int(crash_reports.get('max_reports', 50)),
                max_total_size_mb=float(crash_reports.get('max_total_size_mb', 500)),
                min_free_disk_mb=float(crash_reports.get('min_free_disk_mb', 1000)),
                auto_capture=AutoCaptureConfig(
                    triggers=auto_capture.get('triggers', []),
                    min_severity=auto_capture.get('min_severity', 'error')
                )
            ),
            logging=DebugLoggingConfig(
                execution_trace_file=logging.get('execution_trace_file', 'artifacts/logs/backtest_execution.jsonl'),
                crash_report_dir=logging.get('crash_report_dir', 'artifacts/logs/crash_reports'),
                rotation=LogRotationConfig(
                    max_bytes=int(rotation.get('max_bytes', 10485760)),
                    backup_count=int(rotation.get('backup_count', 5))
                )
            )
        )

