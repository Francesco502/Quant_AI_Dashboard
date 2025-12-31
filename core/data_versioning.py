"""数据版本管理

职责：
- 追踪数据变更历史
- 支持数据快照和回滚
- 记录数据变更日志
"""

from __future__ import annotations

import os
import json
import shutil
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import logging

import pandas as pd


logger = logging.getLogger(__name__)


class DataVersionManager:
    """数据版本管理器"""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化数据版本管理器

        Args:
            base_dir: 基础目录（可选，默认使用data_store的BASE_DIR）
        """
        if base_dir is None:
            from .data_store import BASE_DIR
            base_dir = BASE_DIR
        
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.snapshots_dir = self.versions_dir / "snapshots"
        self.metadata_file = self.versions_dir / "metadata.json"
        
        # 确保目录存在
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载元数据
        self.metadata = self._load_metadata()
        
        logger.info(f"数据版本管理器初始化完成: {self.base_dir}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """加载版本元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载版本元数据失败: {e}")
                return {"versions": [], "current_version": None}
        return {"versions": [], "current_version": None}
    
    def _save_metadata(self):
        """保存版本元数据"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存版本元数据失败: {e}")
    
    def _calculate_hash(self, file_path: Path) -> str:
        """计算文件哈希值"""
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def create_snapshot(
        self,
        ticker: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        创建数据快照

        Args:
            ticker: 标的代码
            description: 快照描述
            tags: 标签列表

        Returns:
            版本ID
        """
        from .data_store import get_price_file_path, load_local_ohlcv_history
        
        # 获取数据文件路径
        data_file = Path(get_price_file_path(ticker))
        
        if not data_file.exists():
            raise FileNotFoundError(f"数据文件不存在: {ticker}")
        
        # 计算文件哈希
        file_hash = self._calculate_hash(data_file)
        
        # 创建版本ID
        version_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建快照目录
        snapshot_dir = self.snapshots_dir / version_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制数据文件到快照目录
        snapshot_file = snapshot_dir / data_file.name
        shutil.copy2(data_file, snapshot_file)
        
        # 创建元数据
        version_info = {
            "version_id": version_id,
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "description": description or f"数据快照: {ticker}",
            "tags": tags or [],
            "file_hash": file_hash,
            "file_path": str(snapshot_file.relative_to(self.base_dir)),
        }
        
        # 添加到版本列表
        if "versions" not in self.metadata:
            self.metadata["versions"] = []
        
        self.metadata["versions"].append(version_info)
        self.metadata["current_version"] = version_id
        
        # 保存元数据
        self._save_metadata()
        
        logger.info(f"创建数据快照: {version_id} - {ticker}")
        
        return version_id
    
    def list_versions(
        self,
        ticker: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        列出所有版本

        Args:
            ticker: 标的代码（可选，用于过滤）
            limit: 返回数量限制

        Returns:
            版本列表
        """
        versions = self.metadata.get("versions", [])
        
        if ticker:
            versions = [v for v in versions if v.get("ticker") == ticker]
        
        # 按时间倒序
        versions = sorted(versions, key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return versions[:limit]
    
    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取版本信息"""
        versions = self.metadata.get("versions", [])
        for version in versions:
            if version.get("version_id") == version_id:
                return version
        return None
    
    def restore_version(
        self,
        version_id: str,
        backup_current: bool = True
    ) -> bool:
        """
        恢复到指定版本

        Args:
            version_id: 版本ID
            backup_current: 是否备份当前数据

        Returns:
            是否成功
        """
        version_info = self.get_version(version_id)
        if not version_info:
            logger.error(f"版本不存在: {version_id}")
            return False
        
        ticker = version_info["ticker"]
        from .data_store import get_price_file_path
        
        # 获取当前数据文件路径
        current_file = Path(get_price_file_path(ticker))
        
        # 备份当前数据
        if backup_current and current_file.exists():
            backup_id = f"{ticker}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir = self.snapshots_dir / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current_file, backup_dir / current_file.name)
            logger.info(f"已备份当前数据: {backup_id}")
        
        # 获取快照文件路径
        snapshot_file = self.base_dir / version_info["file_path"]
        
        if not snapshot_file.exists():
            logger.error(f"快照文件不存在: {snapshot_file}")
            return False
        
        # 恢复数据
        try:
            shutil.copy2(snapshot_file, current_file)
            logger.info(f"已恢复到版本: {version_id} - {ticker}")
            return True
        except Exception as e:
            logger.error(f"恢复版本失败: {e}")
            return False
    
    def delete_version(self, version_id: str) -> bool:
        """删除版本"""
        version_info = self.get_version(version_id)
        if not version_info:
            return False
        
        # 删除快照文件
        snapshot_file = self.base_dir / version_info["file_path"]
        if snapshot_file.exists():
            try:
                snapshot_file.unlink()
                # 删除快照目录（如果为空）
                snapshot_dir = snapshot_file.parent
                if snapshot_dir.exists() and not any(snapshot_dir.iterdir()):
                    snapshot_dir.rmdir()
            except Exception as e:
                logger.error(f"删除快照文件失败: {e}")
        
        # 从元数据中移除
        versions = self.metadata.get("versions", [])
        self.metadata["versions"] = [v for v in versions if v.get("version_id") != version_id]
        
        # 如果删除的是当前版本，更新当前版本
        if self.metadata.get("current_version") == version_id:
            if versions:
                self.metadata["current_version"] = versions[-1].get("version_id")
            else:
                self.metadata["current_version"] = None
        
        self._save_metadata()
        
        logger.info(f"已删除版本: {version_id}")
        return True
    
    def get_version_diff(
        self,
        version_id1: str,
        version_id2: str
    ) -> Optional[Dict[str, Any]]:
        """
        比较两个版本的差异

        Args:
            version_id1: 版本1 ID
            version_id2: 版本2 ID

        Returns:
            差异信息
        """
        v1_info = self.get_version(version_id1)
        v2_info = self.get_version(version_id2)
        
        if not v1_info or not v2_info:
            return None
        
        return {
            "version1": v1_info,
            "version2": v2_info,
            "hash_changed": v1_info.get("file_hash") != v2_info.get("file_hash"),
            "time_diff": (
                datetime.fromisoformat(v2_info["timestamp"]) -
                datetime.fromisoformat(v1_info["timestamp"])
            ).total_seconds(),
        }
    
    def cleanup_old_versions(
        self,
        keep_count: int = 10,
        ticker: Optional[str] = None
    ) -> int:
        """
        清理旧版本

        Args:
            keep_count: 保留的版本数量
            ticker: 标的代码（可选，用于过滤）

        Returns:
            删除的版本数量
        """
        versions = self.list_versions(ticker=ticker, limit=1000)
        
        if len(versions) <= keep_count:
            return 0
        
        # 保留最新的keep_count个版本
        to_keep = versions[:keep_count]
        to_delete = versions[keep_count:]
        
        deleted_count = 0
        for version in to_delete:
            if self.delete_version(version["version_id"]):
                deleted_count += 1
        
        logger.info(f"清理旧版本完成: 删除了 {deleted_count} 个版本")
        
        return deleted_count
    
    def get_version_statistics(self) -> Dict[str, Any]:
        """获取版本统计信息"""
        versions = self.metadata.get("versions", [])
        
        # 按标的统计
        ticker_counts = {}
        for version in versions:
            ticker = version.get("ticker", "unknown")
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        
        return {
            "total_versions": len(versions),
            "unique_tickers": len(ticker_counts),
            "versions_by_ticker": ticker_counts,
            "current_version": self.metadata.get("current_version"),
            "oldest_version": min([v.get("timestamp") for v in versions], default=None),
            "newest_version": max([v.get("timestamp") for v in versions], default=None),
        }

