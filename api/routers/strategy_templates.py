"""策略模板管理路由

提供策略模板的CRUD操作和回测历史记录
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import logging
from datetime import datetime

from api.auth import get_current_active_user, UserInDB
from core.database import get_database

router = APIRouter(prefix="/strategy-templates", tags=["strategy-templates"])
logger = logging.getLogger(__name__)


# --- API Models ---

class StrategyTemplateCreate(BaseModel):
    template_name: str
    strategy_id: str
    strategy_type: str  # 'classic' or 'stz'
    description: Optional[str] = None
    params: Dict[str, Any]
    is_public: bool = False


class StrategyTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    is_favorite: Optional[bool] = None


class StrategyTemplateResponse(BaseModel):
    id: int
    template_name: str
    strategy_id: str
    strategy_type: str
    description: Optional[str]
    params: Dict[str, Any]
    is_public: bool
    is_favorite: bool
    created_at: str
    updated_at: str


class BacktestHistoryCreate(BaseModel):
    template_id: Optional[int] = None
    strategy_id: str
    strategy_params: Dict[str, Any]
    tickers: List[str]
    start_date: str
    end_date: Optional[str] = None
    initial_capital: float
    metrics: Dict[str, Any]
    equity_curve: Optional[List[Dict[str, Any]]] = None


# --- Endpoints ---

@router.get("", response_model=List[StrategyTemplateResponse])
async def list_templates(
    strategy_type: Optional[str] = None,
    strategy_id: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    获取用户的策略模板列表
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        query = """
            SELECT id, template_name, strategy_id, strategy_type, description,
                   params, is_public, is_favorite, created_at, updated_at
            FROM strategy_templates
            WHERE user_id = ?
        """
        params = [current_user.id]

        if strategy_type:
            query += " AND strategy_type = ?"
            params.append(strategy_type)

        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)

        if is_favorite is not None:
            query += " AND is_favorite = ?"
            params.append(1 if is_favorite else 0)

        query += " ORDER BY is_favorite DESC, updated_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        templates = []
        for row in rows:
            templates.append({
                "id": row["id"],
                "template_name": row["template_name"],
                "strategy_id": row["strategy_id"],
                "strategy_type": row["strategy_type"],
                "description": row["description"],
                "params": json.loads(row["params"]),
                "is_public": bool(row["is_public"]),
                "is_favorite": bool(row["is_favorite"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })

        return templates

    except Exception as e:
        logger.error(f"获取策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略模板失败: {str(e)}")


@router.post("", response_model=StrategyTemplateResponse)
async def create_template(
    request: StrategyTemplateCreate,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    创建新的策略模板
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        cursor.execute("""
            INSERT INTO strategy_templates
            (user_id, template_name, strategy_id, strategy_type, description, params, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user.id,
            request.template_name,
            request.strategy_id,
            request.strategy_type,
            request.description,
            json.dumps(request.params),
            1 if request.is_public else 0
        ))

        db.conn.commit()
        template_id = cursor.lastrowid

        # 返回创建的模板
        cursor.execute("""
            SELECT * FROM strategy_templates WHERE id = ?
        """, (template_id,))
        row = cursor.fetchone()

        return {
            "id": row["id"],
            "template_name": row["template_name"],
            "strategy_id": row["strategy_id"],
            "strategy_type": row["strategy_type"],
            "description": row["description"],
            "params": json.loads(row["params"]),
            "is_public": bool(row["is_public"]),
            "is_favorite": bool(row["is_favorite"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    except Exception as e:
        logger.error(f"创建策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建策略模板失败: {str(e)}")


@router.get("/{template_id}", response_model=StrategyTemplateResponse)
async def get_template(
    template_id: int,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    获取单个策略模板详情
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        cursor.execute("""
            SELECT * FROM strategy_templates
            WHERE id = ? AND (user_id = ? OR is_public = 1)
        """, (template_id, current_user.id))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="策略模板不存在")

        return {
            "id": row["id"],
            "template_name": row["template_name"],
            "strategy_id": row["strategy_id"],
            "strategy_type": row["strategy_type"],
            "description": row["description"],
            "params": json.loads(row["params"]),
            "is_public": bool(row["is_public"]),
            "is_favorite": bool(row["is_favorite"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略模板失败: {str(e)}")


@router.put("/{template_id}", response_model=StrategyTemplateResponse)
async def update_template(
    template_id: int,
    request: StrategyTemplateUpdate,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    更新策略模板
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        # 检查所有权
        cursor.execute("""
            SELECT user_id FROM strategy_templates WHERE id = ?
        """, (template_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        if row["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权修改此模板")

        # 构建更新语句
        updates = []
        params = []

        if request.template_name is not None:
            updates.append("template_name = ?")
            params.append(request.template_name)

        if request.description is not None:
            updates.append("description = ?")
            params.append(request.description)

        if request.params is not None:
            updates.append("params = ?")
            params.append(json.dumps(request.params))

        if request.is_public is not None:
            updates.append("is_public = ?")
            params.append(1 if request.is_public else 0)

        if request.is_favorite is not None:
            updates.append("is_favorite = ?")
            params.append(1 if request.is_favorite else 0)

        updates.append("updated_at = CURRENT_TIMESTAMP")

        if not updates:
            raise HTTPException(status_code=400, detail="没有要更新的字段")

        params.append(template_id)

        cursor.execute(f"""
            UPDATE strategy_templates
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        db.conn.commit()

        # 返回更新后的模板
        return await get_template(template_id, current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新策略模板失败: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    删除策略模板
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        # 检查所有权
        cursor.execute("""
            SELECT user_id FROM strategy_templates WHERE id = ?
        """, (template_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        if row["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权删除此模板")

        cursor.execute("""
            DELETE FROM strategy_templates WHERE id = ?
        """, (template_id,))

        db.conn.commit()

        return {"success": True, "message": "策略模板已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除策略模板失败: {str(e)}")


# --- Backtest History Endpoints ---

@router.post("/{template_id}/backtest-history")
async def save_backtest_history(
    template_id: int,
    request: BacktestHistoryCreate,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    保存回测历史记录
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        # 验证模板所有权
        cursor.execute("""
            SELECT user_id FROM strategy_templates WHERE id = ?
        """, (template_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        if row["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权使用此模板")

        cursor.execute("""
            INSERT INTO backtest_history
            (user_id, template_id, strategy_id, strategy_params, tickers,
             start_date, end_date, initial_capital, metrics, equity_curve)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user.id,
            template_id,
            request.strategy_id,
            json.dumps(request.strategy_params),
            ','.join(request.tickers),
            request.start_date,
            request.end_date,
            request.initial_capital,
            json.dumps(request.metrics),
            json.dumps(request.equity_curve) if request.equity_curve else None
        ))

        db.conn.commit()

        return {"success": True, "id": cursor.lastrowid}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存回测历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存回测历史失败: {str(e)}")


@router.get("/{template_id}/backtest-history")
async def get_backtest_history(
    template_id: int,
    limit: int = 10,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    获取策略模板的回测历史
    """
    try:
        db = get_database()
        cursor = db.conn.cursor()

        cursor.execute("""
            SELECT * FROM backtest_history
            WHERE template_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (template_id, current_user.id, limit))

        rows = cursor.fetchall()

        history = []
        for row in rows:
            history.append({
                "id": row["id"],
                "strategy_id": row["strategy_id"],
                "strategy_params": json.loads(row["strategy_params"]),
                "tickers": row["tickers"].split(','),
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "initial_capital": row["initial_capital"],
                "metrics": json.loads(row["metrics"]) if row["metrics"] else {},
                "equity_curve": json.loads(row["equity_curve"]) if row["equity_curve"] else [],
                "created_at": row["created_at"],
            })

        return history

    except Exception as e:
        logger.error(f"获取回测历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取回测历史失败: {str(e)}")
