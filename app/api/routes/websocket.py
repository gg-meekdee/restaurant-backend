from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.services.websocket import manager
from app.core.database import async_session
from app.models.order import Order, OrderStatus

router = APIRouter()

@router.websocket("/ws/kds")
async def kds_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current active orders on connect
        async with async_session() as session:
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.status.in_([OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY]))
                .order_by(Order.created_at)
            )
            orders = result.scalars().all()
            orders_data = []
            for order in orders:
                orders_data.append({
                    "id": str(order.id),
                    "status": order.status.value,
                    "total_amount": float(order.total_amount),
                    "special_notes": order.special_notes,
                    "created_at": order.created_at.isoformat(),
                    "items": [
                        {
                            "item_name": item.item_name,
                            "quantity": item.quantity,
                            "item_price": float(item.item_price)
                        }
                        for item in order.items
                    ]
                })
            await websocket.send_json({"type": "initial", "orders": orders_data})

        # Keep connection open
        while True:
            # Wait for messages from the client (we ignore them)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)