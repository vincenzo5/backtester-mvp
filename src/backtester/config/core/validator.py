"""
Configuration validator module.

Validates configuration structure, types, ranges, and logical constraints.
"""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime


class ValidationResult:
    """Result of configuration validation."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0
    
    def add_error(self, message: str):
        """Add a validation error."""
        self.errors.append(message)
    
    def add_warning(self, message: str):
        """Add a validation warning."""
        self.warnings.append(message)


class ConfigValidator:
    """
    Validates configuration structure, types, and constraints.
    """
    
    def __init__(self):
        """Initialize the validator."""
        pass
    
    def validate(self, config: Dict[str, Any], metadata: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate entire configuration.
        
        Args:
            config: Configuration dictionary to validate
            metadata: Optional exchange metadata for cross-validation
        
        Returns:
            ValidationResult with errors and warnings
        """
        from backtester.config.core.exceptions import ConfigError
        result = ValidationResult()
        
        # Validate each domain
        self.validate_data(config.get('data', {}), result, metadata)
        self.validate_trading(config.get('trading', {}), result)
        self.validate_strategy(config.get('strategy', {}), result)
        self.validate_data_quality(config.get('data_quality', {}), result)
        self.validate_parallel(config.get('parallel', {}), result)
        self.validate_walkforward(config.get('walkforward', {}), result, metadata)
        self.validate_debug(config.get('debug', {}), result)
        
        return result
    
    def validate_data(self, config: Dict[str, Any], result: ValidationResult, metadata: Dict[str, Any] = None):
        """Validate data configuration."""
        if not config:
            result.add_error("Missing 'data' configuration section")
            return
        
        # Validate exchange name
        if 'exchange' not in config:
            result.add_error("Missing 'data.exchange' field")
        elif not isinstance(config['exchange'], str):
            result.add_error("'data.exchange' must be a string")
        elif metadata and 'exchanges' in metadata:
            if config['exchange'] not in metadata['exchanges']:
                result.add_warning(f"Exchange '{config['exchange']}' not found in metadata")
        
        # Validate cache settings
        if 'cache_enabled' in config and not isinstance(config['cache_enabled'], bool):
            result.add_error("'data.cache_enabled' must be a boolean")
        
        if 'cache_directory' in config and not isinstance(config['cache_directory'], str):
            result.add_error("'data.cache_directory' must be a string")
        
        # Validate historical_start_date
        if 'historical_start_date' in config:
            try:
                pd.to_datetime(config['historical_start_date'])
            except (ValueError, TypeError):
                result.add_error("'data.historical_start_date' must be a valid date string")
    
    def validate_trading(self, config: Dict[str, Any], result: ValidationResult):
        """Validate trading configuration."""
        if not config:
            result.add_error("Missing 'trading' configuration section")
            return
        
        # Validate use_exchange_fees
        if 'use_exchange_fees' in config and not isinstance(config['use_exchange_fees'], bool):
            result.add_error("'trading.use_exchange_fees' must be a boolean")
        
        # Validate fee_type
        if 'fee_type' in config:
            if config['fee_type'] not in ['maker', 'taker']:
                result.add_error("'trading.fee_type' must be 'maker' or 'taker'")
        
        # Validate slippage
        if 'slippage' in config:
            try:
                slippage = float(config['slippage'])
                if slippage < 0:
                    result.add_error("'trading.slippage' must be >= 0")
            except (ValueError, TypeError):
                result.add_error("'trading.slippage' must be a number")
        
        # Validate risk_per_trade
        if 'risk_per_trade' in config:
            try:
                risk = float(config['risk_per_trade'])
                if risk <= 0 or risk > 1.0:
                    result.add_error("'trading.risk_per_trade' must be between 0 and 1.0")
            except (ValueError, TypeError):
                result.add_error("'trading.risk_per_trade' must be a number")
        
        # Validate position_size
        if 'position_size' in config:
            try:
                size = float(config['position_size'])
                if size <= 0 or size > 1.0:
                    result.add_error("'trading.position_size' must be between 0 and 1.0")
            except (ValueError, TypeError):
                result.add_error("'trading.position_size' must be a number")
        
        # Validate commission rates
        for field in ['commission', 'commission_maker']:
            if field in config:
                try:
                    rate = float(config[field])
                    if rate < 0 or rate > 1.0:
                        result.add_error(f"'trading.{field}' must be between 0 and 1.0")
                except (ValueError, TypeError):
                    result.add_error(f"'trading.{field}' must be a number")
    
    def validate_strategy(self, config: Dict[str, Any], result: ValidationResult):
        """Validate strategy configuration."""
        if not config:
            result.add_error("Missing 'strategy' configuration section")
            return
        
        # Validate strategy name
        if 'name' not in config:
            result.add_error("Missing 'strategy.name' field")
        elif not isinstance(config['name'], str):
            result.add_error("'strategy.name' must be a string")
        
    
    
    def validate_data_quality(self, config: Dict[str, Any], result: ValidationResult):
        """Validate data quality configuration."""
        if not config:
            return  # Data quality config is optional
        
        # Validate weights
        if 'weights' in config:
            if not isinstance(config['weights'], dict):
                result.add_error("'data_quality.weights' must be a dictionary")
            else:
                total_weight = sum(float(v) for v in config['weights'].values())
                if abs(total_weight - 1.0) > 0.01:  # Allow small floating point error
                    result.add_warning(f"'data_quality.weights' sum to {total_weight:.2f}, expected 1.0")
                
                for key, value in config['weights'].items():
                    try:
                        weight = float(value)
                        if weight < 0 or weight > 1.0:
                            result.add_error(f"'data_quality.weights.{key}' must be between 0 and 1.0")
                    except (ValueError, TypeError):
                        result.add_error(f"'data_quality.weights.{key}' must be a number")
        
        # Validate thresholds
        if 'thresholds' in config and isinstance(config['thresholds'], dict):
            for key, value in config['thresholds'].items():
                try:
                    float(value)  # Most thresholds are numbers
                except (ValueError, TypeError):
                    if key != 'outlier_iqr_multiplier':  # This might be int or float
                        result.add_warning(f"'data_quality.thresholds.{key}' should be a number")
        
        # Validate warning_threshold
        if 'warning_threshold' in config:
            try:
                threshold = float(config['warning_threshold'])
                if threshold < 0 or threshold > 100:
                    result.add_error("'data_quality.warning_threshold' must be between 0 and 100")
            except (ValueError, TypeError):
                result.add_error("'data_quality.warning_threshold' must be a number")
        
        # Validate schedules
        for field in ['full_assessment_schedule', 'gap_filling_schedule']:
            if field in config:
                if field == 'full_assessment_schedule':
                    valid_values = ['weekly', 'daily']
                else:
                    valid_values = ['weekly', 'monthly']
                
                if config[field] not in valid_values:
                    result.add_error(f"'data_quality.{field}' must be one of {valid_values}")
    
    def validate_parallel(self, config: Dict[str, Any], result: ValidationResult):
        """Validate parallel execution configuration."""
        if not config:
            return  # Parallel config is optional
        
        # Validate mode
        if 'mode' in config:
            if config['mode'] not in ['auto', 'manual']:
                result.add_error("'parallel.mode' must be 'auto' or 'manual'")
        
        # Validate max_workers
        if 'max_workers' in config and config['max_workers'] is not None:
            try:
                workers = int(config['max_workers'])
                if workers <= 0:
                    result.add_error("'parallel.max_workers' must be positive or null")
            except (ValueError, TypeError):
                result.add_error("'parallel.max_workers' must be an integer or null")
        
        # Validate memory_safety_factor
        if 'memory_safety_factor' in config:
            try:
                factor = float(config['memory_safety_factor'])
                if factor <= 0 or factor > 1.0:
                    result.add_error("'parallel.memory_safety_factor' must be between 0 and 1.0")
            except (ValueError, TypeError):
                result.add_error("'parallel.memory_safety_factor' must be a number")
        
        # Validate cpu_reserve_cores
        if 'cpu_reserve_cores' in config:
            try:
                cores = int(config['cpu_reserve_cores'])
                if cores < 0:
                    result.add_error("'parallel.cpu_reserve_cores' must be >= 0")
            except (ValueError, TypeError):
                result.add_error("'parallel.cpu_reserve_cores' must be an integer")
    
    def validate_walkforward(self, config: Dict[str, Any], result: ValidationResult, metadata: Dict[str, Any] = None):
        """Validate walk-forward optimization configuration."""
        if not config:
            result.add_error("Missing 'walkforward' configuration section")
            return
        
        # Validate start_date
        if 'start_date' not in config:
            result.add_error("Missing required field 'walkforward.start_date'")
        else:
            try:
                pd.to_datetime(config['start_date'])
            except (ValueError, TypeError):
                result.add_error("'walkforward.start_date' must be a valid date string (YYYY-MM-DD)")
        
        # Validate end_date
        if 'end_date' not in config:
            result.add_error("Missing required field 'walkforward.end_date'")
        else:
            try:
                pd.to_datetime(config['end_date'])
            except (ValueError, TypeError):
                result.add_error("'walkforward.end_date' must be a valid date string (YYYY-MM-DD)")
        
        # Validate date range logic
        if 'start_date' in config and 'end_date' in config:
            try:
                start = pd.to_datetime(config['start_date'])
                end = pd.to_datetime(config['end_date'])
                if start >= end:
                    result.add_error("'walkforward.start_date' must be before 'walkforward.end_date'")
            except (ValueError, TypeError):
                pass  # Already caught above
        
        # Validate initial_capital
        if 'initial_capital' not in config:
            result.add_error("Missing required field 'walkforward.initial_capital'")
        else:
            try:
                capital = float(config['initial_capital'])
                if capital <= 0:
                    result.add_error("'walkforward.initial_capital' must be positive")
            except (ValueError, TypeError):
                result.add_error("'walkforward.initial_capital' must be a number")
        
        # Validate verbose
        if 'verbose' in config and not isinstance(config['verbose'], bool):
            result.add_error("'walkforward.verbose' must be a boolean")
        
        # Validate symbols
        if 'symbols' in config:
            symbols = config['symbols']
            if symbols is not None:
                if not isinstance(symbols, (str, list)):
                    result.add_error("'walkforward.symbols' must be a string or list of strings")
                elif isinstance(symbols, list):
                    for i, symbol in enumerate(symbols):
                        if not isinstance(symbol, str):
                            result.add_error(f"'walkforward.symbols[{i}]' must be a string")
                        elif metadata and 'top_markets' in metadata:
                            if symbol not in metadata['top_markets']:
                                result.add_warning(f"Symbol '{symbol}' not found in metadata.top_markets")
        
        # Validate timeframes
        if 'timeframes' in config:
            timeframes = config['timeframes']
            if timeframes is not None:
                if not isinstance(timeframes, (str, list)):
                    result.add_error("'walkforward.timeframes' must be a string or list of strings")
                elif isinstance(timeframes, list):
                    for i, tf in enumerate(timeframes):
                        if not isinstance(tf, str):
                            result.add_error(f"'walkforward.timeframes[{i}]' must be a string")
                        elif metadata and 'timeframes' in metadata:
                            if tf not in metadata['timeframes']:
                                result.add_warning(f"Timeframe '{tf}' not found in metadata.timeframes")
        
        # Validate periods
        if 'periods' in config:
            if not isinstance(config['periods'], list):
                result.add_error("'walkforward.periods' must be a list")
            else:
                for period in config['periods']:
                    if not isinstance(period, str):
                        result.add_error("Each 'walkforward.periods' entry must be a string")
                    elif '/' not in period:
                        result.add_error(f"Invalid period format '{period}': expected 'X/Y' (e.g., '1Y/6M')")
        
        # Validate fitness_functions
        if 'fitness_functions' in config:
            if not isinstance(config['fitness_functions'], list):
                result.add_error("'walkforward.fitness_functions' must be a list")
            else:
                valid_functions = ['net_profit', 'sharpe_ratio', 'max_dd', 'profit_factor', 'np_avg_dd']
                for func in config['fitness_functions']:
                    if func not in valid_functions:
                        result.add_error(f"Invalid fitness function '{func}': must be one of {valid_functions}")
        
        # Validate parameter_ranges
        if 'parameter_ranges' in config:
            if not isinstance(config['parameter_ranges'], dict):
                result.add_error("'walkforward.parameter_ranges' must be a dictionary")
            else:
                for param_name, param_range in config['parameter_ranges'].items():
                    if not isinstance(param_range, dict):
                        result.add_error(f"'walkforward.parameter_ranges.{param_name}' must be a dictionary")
                    else:
                        for field in ['start', 'end', 'step']:
                            if field not in param_range:
                                result.add_error(f"Missing 'walkforward.parameter_ranges.{param_name}.{field}'")
                            else:
                                try:
                                    value = int(param_range[field])
                                    if value <= 0:
                                        result.add_error(f"'walkforward.parameter_ranges.{param_name}.{field}' must be positive")
                                except (ValueError, TypeError):
                                    result.add_error(f"'walkforward.parameter_ranges.{param_name}.{field}' must be an integer")
                        
                        # Validate logical constraint: start < end
                        if 'start' in param_range and 'end' in param_range:
                            try:
                                start = int(param_range['start'])
                                end = int(param_range['end'])
                                if start >= end:
                                    result.add_error(f"'walkforward.parameter_ranges.{param_name}.start' must be less than 'end'")
                            except (ValueError, TypeError):
                                pass  # Already caught above
        
        # Validate filters (optional)
        if 'filters' in config:
            filters = config['filters']
            if filters is not None:
                if not isinstance(filters, (str, list)):
                    result.add_error("'walkforward.filters' must be a string or list of strings")
                elif isinstance(filters, list):
                    for i, f in enumerate(filters):
                        if not isinstance(f, str):
                            result.add_error(f"'walkforward.filters[{i}]' must be a string, got {type(f).__name__}")
    
    def validate_debug(self, config: Dict[str, Any], result: ValidationResult):
        """Validate debug configuration."""
        if not config:
            return  # Debug config is optional
        
        # Validate enabled
        if 'enabled' in config and not isinstance(config['enabled'], bool):
            result.add_error("'debug.enabled' must be a boolean")
        
        # Validate tracing
        if 'tracing' in config:
            tracing = config['tracing']
            if not isinstance(tracing, dict):
                result.add_error("'debug.tracing' must be a dictionary")
            else:
                if 'enabled' in tracing and not isinstance(tracing['enabled'], bool):
                    result.add_error("'debug.tracing.enabled' must be a boolean")
                
                if 'level' in tracing:
                    valid_levels = ['minimal', 'standard', 'detailed']
                    if tracing['level'] not in valid_levels:
                        result.add_error(f"'debug.tracing.level' must be one of {valid_levels}")
                
                if 'sample_rate' in tracing:
                    try:
                        rate = float(tracing['sample_rate'])
                        if rate <= 0 or rate > 1.0:
                            result.add_error("'debug.tracing.sample_rate' must be between 0 and 1.0")
                    except (ValueError, TypeError):
                        result.add_error("'debug.tracing.sample_rate' must be a number")
        
        # Validate crash_reports
        if 'crash_reports' in config:
            crash_reports = config['crash_reports']
            if not isinstance(crash_reports, dict):
                result.add_error("'debug.crash_reports' must be a dictionary")
            else:
                if 'enabled' in crash_reports and not isinstance(crash_reports['enabled'], bool):
                    result.add_error("'debug.crash_reports.enabled' must be a boolean")
                
                # Validate max_reports
                if 'max_reports' in crash_reports:
                    try:
                        max_reports = int(crash_reports['max_reports'])
                        if max_reports <= 0:
                            result.add_error("'debug.crash_reports.max_reports' must be positive")
                    except (ValueError, TypeError):
                        result.add_error("'debug.crash_reports.max_reports' must be an integer")
                
                # Validate max_total_size_mb
                if 'max_total_size_mb' in crash_reports:
                    try:
                        size = float(crash_reports['max_total_size_mb'])
                        if size <= 0:
                            result.add_error("'debug.crash_reports.max_total_size_mb' must be positive")
                    except (ValueError, TypeError):
                        result.add_error("'debug.crash_reports.max_total_size_mb' must be a number")
                
                # Validate min_free_disk_mb
                if 'min_free_disk_mb' in crash_reports:
                    try:
                        free = float(crash_reports['min_free_disk_mb'])
                        if free < 0:
                            result.add_error("'debug.crash_reports.min_free_disk_mb' must be >= 0")
                    except (ValueError, TypeError):
                        result.add_error("'debug.crash_reports.min_free_disk_mb' must be a number")
                
                # Validate auto_capture
                if 'auto_capture' in crash_reports:
                    auto_capture = crash_reports['auto_capture']
                    if not isinstance(auto_capture, dict):
                        result.add_error("'debug.crash_reports.auto_capture' must be a dictionary")
                    else:
                        # Validate triggers
                        if 'triggers' in auto_capture:
                            triggers = auto_capture['triggers']
                            if not isinstance(triggers, list):
                                result.add_error("'debug.crash_reports.auto_capture.triggers' must be a list")
                            else:
                                valid_triggers = [
                                    'exception', 'zero_trades', 'validation_error',
                                    'memory_warning', 'filter_error', 'indicator_error',
                                    'data_alignment_error'
                                ]
                                for trigger in triggers:
                                    if trigger not in valid_triggers:
                                        result.add_warning(f"Unknown trigger '{trigger}' (will be ignored)")
                        
                        # Validate min_severity
                        if 'min_severity' in auto_capture:
                            valid_severities = ['error', 'warning', 'info']
                            if auto_capture['min_severity'] not in valid_severities:
                                result.add_error(f"'debug.crash_reports.auto_capture.min_severity' must be one of {valid_severities}")
        
        # Validate logging
        if 'logging' in config:
            logging = config['logging']
            if not isinstance(logging, dict):
                result.add_error("'debug.logging' must be a dictionary")
            else:
                # Validate execution_trace_file
                if 'execution_trace_file' in logging and not isinstance(logging['execution_trace_file'], str):
                    result.add_error("'debug.logging.execution_trace_file' must be a string")
                
                # Validate crash_report_dir
                if 'crash_report_dir' in logging and not isinstance(logging['crash_report_dir'], str):
                    result.add_error("'debug.logging.crash_report_dir' must be a string")
                
                # Validate rotation
                if 'rotation' in logging:
                    rotation = logging['rotation']
                    if not isinstance(rotation, dict):
                        result.add_error("'debug.logging.rotation' must be a dictionary")
                    else:
                        if 'max_bytes' in rotation:
                            try:
                                max_bytes = int(rotation['max_bytes'])
                                if max_bytes <= 0:
                                    result.add_error("'debug.logging.rotation.max_bytes' must be positive")
                            except (ValueError, TypeError):
                                result.add_error("'debug.logging.rotation.max_bytes' must be an integer")
                        
                        if 'backup_count' in rotation:
                            try:
                                backup_count = int(rotation['backup_count'])
                                if backup_count < 0:
                                    result.add_error("'debug.logging.rotation.backup_count' must be >= 0")
                            except (ValueError, TypeError):
                                result.add_error("'debug.logging.rotation.backup_count' must be an integer")

