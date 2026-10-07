import uuid
from datetime import datetime

class MockPaymentService:
    """Simulates Hubtel MoMo payment initiation for development."""
    
    def initiate_momo_payment(self, order, phone_number: str) -> str:
        # In production, this would call Hubtel API and return a real reference.
        # For now, generate a fake reference.
        payment_ref = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        # Normally, you'd store this in the order or payment table.
        # We'll just return it and let the caller assign it.
        return payment_ref

payment_service = MockPaymentService()