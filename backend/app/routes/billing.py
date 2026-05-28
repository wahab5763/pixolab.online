from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import CreditTransaction, User
from ..schemas import CheckoutRequest
from ..security import get_current_user

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()

PLANS = {
    "starter": {"credits": 100, "label": "Starter", "price_env": "stripe_price_starter"},
    "pro": {"credits": 500, "label": "Pro", "price_env": "stripe_price_pro"},
}


@router.post("/checkout")
def checkout(payload: CheckoutRequest, current_user: User = Depends(get_current_user)):
    plan = PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Unsupported plan")

    price_id = getattr(settings, plan["price_env"])
    if not settings.stripe_secret_key or not price_id:
        return {
            "mode": "mock",
            "message": "Stripe is not configured. Add STRIPE_SECRET_KEY and price IDs to backend/.env.",
            "plan": payload.plan,
            "would_add_credits": plan["credits"],
        }

    import stripe
    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=current_user.email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/pricing?success=true",
        cancel_url=f"{settings.frontend_url}/pricing?cancelled=true",
        metadata={"user_id": str(current_user.id), "plan": payload.plan},
    )
    return {"mode": "stripe", "checkout_url": session.url}


@router.post("/dev-add-credits")
def dev_add_credits(amount: int = 25, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if settings.environment != "development":
        raise HTTPException(status_code=403, detail="Development only")
    amount = max(1, min(amount, 500))
    current_user.credits += amount
    db.add(CreditTransaction(user_id=current_user.id, amount=amount, reason="Development credit top-up"))
    db.commit()
    return {"credits": current_user.credits}
