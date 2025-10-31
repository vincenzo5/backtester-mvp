"""
Change tracking for performance attribution.

Captures git commit, config hashes, and dependency versions
to enable correlation between code/config changes and performance.
"""

import subprocess
import hashlib
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json

try:
    import yaml
except ImportError:
    yaml = None


class ChangeTracker:
    """Tracks code, config, and dependency changes for performance attribution."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize change tracker.
        
        Args:
            project_root: Project root directory (defaults to git root)
        """
        self.project_root = project_root or self._find_git_root()
    
    def get_change_metadata(self) -> Dict[str, Any]:
        """
        Get comprehensive change metadata for current execution.
        
        Returns:
            Dictionary with git info, config hashes, dependency versions
        """
        metadata = {
            'git': self._get_git_info(),
            'config': self._get_config_hashes(),
            'environment': self._get_environment_info(),
            'dependencies': self._get_dependency_versions()
        }
        
        return metadata
    
    def _find_git_root(self) -> Path:
        """Find git repository root."""
        current = Path.cwd()
        while current != current.parent:
            if (current / '.git').exists():
                return current
            current = current.parent
        return Path.cwd()  # Fallback to current dir
    
    def _get_git_info(self) -> Dict[str, Any]:
        """Get git commit information."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1.0
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else None
            
            # Get branch name
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1.0
            )
            branch = result.stdout.strip() if result.returncode == 0 else None
            
            # Get commit message (first line)
            if commit_hash:
                result = subprocess.run(
                    ['git', 'log', '-1', '--pretty=%s', commit_hash],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=1.0
                )
                commit_message = result.stdout.strip() if result.returncode == 0 else None
            else:
                commit_message = None
            
            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'diff', '--quiet'],
                cwd=self.project_root,
                timeout=1.0
            )
            has_uncommitted = result.returncode != 0
            
            return {
                'commit_hash': commit_hash or 'unknown',
                'branch': branch or 'unknown',
                'commit_message': commit_message or 'unknown',
                'has_uncommitted_changes': has_uncommitted
            }
        except Exception:
            # Git not available or not a git repo
            return {
                'commit_hash': 'unknown',
                'branch': 'unknown',
                'commit_message': 'unknown',
                'has_uncommitted_changes': False
            }
    
    def _get_config_hashes(self) -> Dict[str, str]:
        """Calculate SHA256 hashes of config files."""
        config_dir = self.project_root / 'config'
        hashes = {}
        
        if not config_dir.exists():
            return hashes
        
        config_files = [
            'strategy.yaml',
            'trading.yaml',
            'data.yaml',
            'parallel.yaml',
            'walkforward.yaml',
            'debug.yaml'
        ]
        
        for config_file in config_files:
            config_path = config_dir / config_file
            if config_path.exists():
                try:
                    with open(config_path, 'rb') as f:
                        content = f.read()
                        hashes[config_file] = hashlib.sha256(content).hexdigest()[:16]
                except Exception:
                    hashes[config_file] = 'error'
        
        # Also hash profile configs
        profiles_dir = config_dir / 'profiles'
        if profiles_dir.exists():
            for profile_file in profiles_dir.glob('*.yaml'):
                try:
                    with open(profile_file, 'rb') as f:
                        content = f.read()
                        hashes[f'profiles/{profile_file.name}'] = hashlib.sha256(content).hexdigest()[:16]
                except Exception:
                    pass
        
        return hashes
    
    def _get_environment_info(self) -> Dict[str, str]:
        """Get environment information."""
        return {
            'python_version': sys.version.split()[0],
            'platform': sys.platform,
            'os': sys.platform
        }
    
    def _get_dependency_versions(self) -> Dict[str, str]:
        """Get versions of key dependencies."""
        versions = {}
        
        key_packages = [
            'pandas', 'numpy', 'backtrader', 'scipy',
            'ta', 'ccxt', 'psutil', 'pyyaml'
        ]
        
        for package in key_packages:
            try:
                if package == 'backtrader':
                    import backtrader as module
                    # Backtrader uses different version attribute
                    versions[package] = getattr(module, '__version__', getattr(module, 'version', 'unknown'))
                elif package == 'ta':
                    import ta as module
                    versions[package] = getattr(module, '__version__', 'unknown')
                elif package == 'pyyaml':
                    import yaml as module
                    versions[package] = getattr(module, '__version__', 'unknown')
                else:
                    module = __import__(package)
                    versions[package] = getattr(module, '__version__', 'unknown')
            except ImportError:
                versions[package] = 'not_installed'
        
        return versions

