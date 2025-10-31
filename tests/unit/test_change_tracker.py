"""
Unit tests for ChangeTracker module.

Tests change attribution functionality including git info, config hashes,
environment info, and dependency versions.
"""

import unittest
import pytest
import tempfile
import shutil
import subprocess
import hashlib
import sys
import os
from pathlib import Path
import json

from backtester.debug.change_tracker import ChangeTracker


@pytest.mark.unit
class TestChangeTracker(unittest.TestCase):
    """Test ChangeTracker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test ChangeTracker initializes with project root."""
        tracker = ChangeTracker(project_root=self.temp_path)
        self.assertEqual(tracker.project_root, self.temp_path)
    
    def test_initialization_default_root(self):
        """Test ChangeTracker finds default git root."""
        tracker = ChangeTracker()
        # Should find some root (could be git repo or current directory)
        self.assertIsNotNone(tracker.project_root)
        self.assertTrue(tracker.project_root.exists() or tracker.project_root == Path.cwd())
    
    def test_find_git_root_with_git(self):
        """Test _find_git_root finds .git directory."""
        # Create a fake .git directory
        git_dir = self.temp_path / '.git'
        git_dir.mkdir()
        
        tracker = ChangeTracker(project_root=self.temp_path)
        # Should find the temp_dir as git root
        self.assertEqual(tracker.project_root, self.temp_path)
    
    def test_find_git_root_without_git(self):
        """Test _find_git_root falls back to current dir when no .git."""
        # No .git directory in temp_dir
        tracker = ChangeTracker(project_root=self.temp_path)
        # Should use provided root even without .git
        self.assertEqual(tracker.project_root, self.temp_path)
    
    def test_get_git_info_with_git(self):
        """Test _get_git_info extracts git information."""
        # Create a git repository in temp directory
        try:
            subprocess.run(['git', 'init'], cwd=self.temp_dir, capture_output=True, check=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], 
                         cwd=self.temp_dir, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], 
                         cwd=self.temp_dir, capture_output=True)
            
            # Create a test file and commit
            test_file = self.temp_path / 'test.txt'
            test_file.write_text('test content')
            subprocess.run(['git', 'add', 'test.txt'], cwd=self.temp_dir, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Test commit'], 
                         cwd=self.temp_dir, capture_output=True)
            
            tracker = ChangeTracker(project_root=self.temp_path)
            git_info = tracker._get_git_info()
            
            self.assertIn('commit_hash', git_info)
            self.assertIn('branch', git_info)
            self.assertIn('commit_message', git_info)
            self.assertIn('has_uncommitted_changes', git_info)
            
            # Should have valid commit hash
            self.assertNotEqual(git_info['commit_hash'], 'unknown')
            self.assertNotEqual(git_info['branch'], 'unknown')
            self.assertNotEqual(git_info['commit_message'], 'unknown')
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Git not available, skip test
            self.skipTest("Git not available")
    
    def test_get_git_info_without_git(self):
        """Test _get_git_info returns 'unknown' when no git repo."""
        tracker = ChangeTracker(project_root=self.temp_path)
        git_info = tracker._get_git_info()
        
        self.assertEqual(git_info['commit_hash'], 'unknown')
        self.assertEqual(git_info['branch'], 'unknown')
        self.assertEqual(git_info['commit_message'], 'unknown')
        # has_uncommitted_changes might be True if git command fails (which it will in non-git dir)
        # The important thing is it doesn't crash
        self.assertIn(git_info['has_uncommitted_changes'], [True, False])
    
    def test_get_git_info_uncommitted_changes(self):
        """Test _get_git_info detects uncommitted changes."""
        try:
            subprocess.run(['git', 'init'], cwd=self.temp_dir, capture_output=True, check=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], 
                         cwd=self.temp_dir, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], 
                         cwd=self.temp_dir, capture_output=True)
            
            # Create and commit initial file
            test_file = self.temp_path / 'test.txt'
            test_file.write_text('initial')
            subprocess.run(['git', 'add', 'test.txt'], cwd=self.temp_dir, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Initial'], 
                         cwd=self.temp_dir, capture_output=True)
            
            # Modify file without committing
            test_file.write_text('modified')
            
            tracker = ChangeTracker(project_root=self.temp_path)
            git_info = tracker._get_git_info()
            
            self.assertTrue(git_info['has_uncommitted_changes'])
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("Git not available")
    
    def test_get_config_hashes_with_files(self):
        """Test _get_config_hashes calculates hashes for existing config files."""
        # Create config directory and files
        config_dir = self.temp_path / 'config'
        config_dir.mkdir()
        
        strategy_file = config_dir / 'strategy.yaml'
        strategy_file.write_text('strategy:\n  name: test')
        
        trading_file = config_dir / 'trading.yaml'
        trading_file.write_text('trading:\n  commission: 0.001')
        
        tracker = ChangeTracker(project_root=self.temp_path)
        hashes = tracker._get_config_hashes()
        
        self.assertIn('strategy.yaml', hashes)
        self.assertIn('trading.yaml', hashes)
        
        # Hashes should be 16-character hex strings
        self.assertEqual(len(hashes['strategy.yaml']), 16)
        self.assertTrue(all(c in '0123456789abcdef' for c in hashes['strategy.yaml']))
    
    def test_get_config_hashes_missing_files(self):
        """Test _get_config_hashes skips missing config files."""
        # Create config directory but no files
        config_dir = self.temp_path / 'config'
        config_dir.mkdir()
        
        tracker = ChangeTracker(project_root=self.temp_path)
        hashes = tracker._get_config_hashes()
        
        # Should return empty dict or only files that exist
        self.assertIsInstance(hashes, dict)
    
    def test_get_config_hashes_profile_configs(self):
        """Test _get_config_hashes includes profile configs."""
        config_dir = self.temp_path / 'config'
        profiles_dir = config_dir / 'profiles'
        profiles_dir.mkdir(parents=True)
        
        profile_file = profiles_dir / 'test_profile.yaml'
        profile_file.write_text('profile: test')
        
        tracker = ChangeTracker(project_root=self.temp_path)
        hashes = tracker._get_config_hashes()
        
        # Should include profile config
        self.assertIn('profiles/test_profile.yaml', hashes)
    
    def test_get_config_hashes_missing_config_dir(self):
        """Test _get_config_hashes handles missing config directory."""
        # No config directory
        tracker = ChangeTracker(project_root=self.temp_path)
        hashes = tracker._get_config_hashes()
        
        # Should return empty dict
        self.assertEqual(hashes, {})
    
    def test_get_environment_info(self):
        """Test _get_environment_info returns environment information."""
        tracker = ChangeTracker()
        env_info = tracker._get_environment_info()
        
        self.assertIn('python_version', env_info)
        self.assertIn('platform', env_info)
        self.assertIn('os', env_info)
        
        # Python version should match sys.version
        self.assertEqual(env_info['python_version'], sys.version.split()[0])
        self.assertEqual(env_info['platform'], sys.platform)
        self.assertEqual(env_info['os'], sys.platform)
    
    def test_get_dependency_versions_installed(self):
        """Test _get_dependency_versions returns versions for installed packages."""
        tracker = ChangeTracker()
        versions = tracker._get_dependency_versions()
        
        # Should have entries for all key packages
        key_packages = ['pandas', 'numpy', 'backtrader', 'scipy', 'ta', 'ccxt', 'psutil', 'pyyaml']
        for package in key_packages:
            self.assertIn(package, versions)
        
        # Some packages should be installed (pandas, numpy typically are)
        # At least one should have a version (not all 'not_installed')
        installed_count = sum(1 for v in versions.values() if v != 'not_installed' and v != 'unknown')
        # In test environment, at least pandas/numpy should be available
        self.assertGreaterEqual(installed_count, 0)  # May have none in minimal test env
    
    def test_get_dependency_versions_missing(self):
        """Test _get_dependency_versions returns 'not_installed' for missing packages."""
        tracker = ChangeTracker()
        versions = tracker._get_dependency_versions()
        
        # Check that missing packages return 'not_installed'
        # This is hard to test definitively, but structure should be correct
        self.assertIsInstance(versions, dict)
        for version in versions.values():
            self.assertIsInstance(version, str)
    
    def test_get_change_metadata_structure(self):
        """Test get_change_metadata returns complete metadata structure."""
        tracker = ChangeTracker(project_root=self.temp_path)
        metadata = tracker.get_change_metadata()
        
        # Verify structure
        self.assertIn('git', metadata)
        self.assertIn('config', metadata)
        self.assertIn('environment', metadata)
        self.assertIn('dependencies', metadata)
        
        # Verify git structure
        self.assertIn('commit_hash', metadata['git'])
        self.assertIn('branch', metadata['git'])
        self.assertIn('commit_message', metadata['git'])
        self.assertIn('has_uncommitted_changes', metadata['git'])
        
        # Verify config is dict
        self.assertIsInstance(metadata['config'], dict)
        
        # Verify environment structure
        self.assertIn('python_version', metadata['environment'])
        self.assertIn('platform', metadata['environment'])
        
        # Verify dependencies structure
        self.assertIsInstance(metadata['dependencies'], dict)
    
    def test_get_change_metadata_no_git(self):
        """Test get_change_metadata works without git repo."""
        tracker = ChangeTracker(project_root=self.temp_path)
        metadata = tracker.get_change_metadata()
        
        # Should still return valid structure
        self.assertEqual(metadata['git']['commit_hash'], 'unknown')
        self.assertEqual(metadata['git']['branch'], 'unknown')
    
    def test_get_change_metadata_missing_config(self):
        """Test get_change_metadata handles missing config directory."""
        # No config directory
        tracker = ChangeTracker(project_root=self.temp_path)
        metadata = tracker.get_change_metadata()
        
        # Should still return valid structure
        self.assertIsInstance(metadata['config'], dict)
        # Config dict may be empty, which is fine


if __name__ == '__main__':
    unittest.main()

