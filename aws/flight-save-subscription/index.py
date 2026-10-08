# ---------- shared ECPay helpers (folded into each single-file Lambda) ----------
import base64, hashlib, json, urllib.parse
from datetime import datetime, timedelta, timezone
import boto3

TS_FMT = "%Y-%m-%dT%H:%M:%SZ"  # fixed-width UTC; current_period_end is compared as a string
_sm = boto3.client("secretsmanager")
_ecpay = None


def ecpay_cfg():
    global _ecpay
    if _ecpay is None:
        _ecpay = json.loads(_sm.get_secret_value(SecretId="flight/ecpay")["SecretString"])
    return _ecpay


def ecpay_host():
    return "https://payment.ecpay.com.tw" if ecpay_cfg().get("env") == "prod" else "https://payment-stage.ecpay.com.tw"


def ecpay_url_encode(s):
    e = urllib.parse.quote_plus(str(s)).replace("~", "%7E").lower()
    for o, n in (("%2d", "-"), ("%5f", "_"), ("%2e", "."), ("%21", "!"), ("%2a", "*"), ("%28", "("), ("%29", ")")):
        e = e.replace(o, n)
    return e


def gen_cmv(params, hash_key, hash_iv):
    items = {k: v for k, v in params.items() if k != "CheckMacValue"}  # keep "" values
    body = "&".join(f"{k}={items[k]}" for k in sorted(items, key=str.lower))
    raw = f"HashKey={hash_key}&{body}&HashIV={hash_iv}"
    return hashlib.sha256(ecpay_url_encode(raw).encode()).hexdigest().upper()


def verify_cmv(params):
    cfg = ecpay_cfg()
    return params.get("CheckMacValue", "").upper() == gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])


def form_params(event):
    raw = (event or {}).get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}


def text(body, status=200):
    return {"statusCode": status, "headers": {"Content-Type": "text/plain; charset=utf-8"}, "body": body}


def now_utc():
    return datetime.now(timezone.utc)


def add_period(start, period_type="M", frequency=1):
    n = max(int(frequency or 1), 1)
    if period_type == "D":
        return start + timedelta(days=n)
    if period_type == "Y":
        return start.replace(year=start.year + n)
    m = start.month - 1 + n
    y, m = start.year + m // 12, m % 12 + 1
    for day in (start.day, 30, 29, 28):
        try:
            return start.replace(year=y, month=m, day=day)
        except ValueError:
            continue


def taipei_date(dt):
    return (dt + timedelta(hours=8)).strftime("%Y-%m-%d")
import html, os, re, secrets
from decimal import Decimal, InvalidOperation

PLANS = {"tokyo": {"origin": "TPE", "destination": "TYO"}, "seoul": {"origin": "TPE", "destination": "SEL"}}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
API_BASE = os.environ["API_BASE"].strip().rstrip("/")
SITE_URL = os.environ["SITE_URL"].strip().rstrip("/")
PERIOD_TYPE, FREQUENCY, EXEC_TIMES = "M", "1", "999"  # monthly; set D/1/2 to test renewals next day
ddb = boto3.resource("dynamodb").Table("subscriptions")


def resp(code, body):
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def in_service(item, now_s):
    st = item.get("subscription_status")
    return st == "active" or (st == "cancelled" and item.get("current_period_end", "") >= now_s)


def checkout_form(email, route, plan_name, mtn):
    cfg = ecpay_cfg()
    amount = str(int(cfg["amount"]))
    params = {
        "MerchantID": cfg["merchant_id"], "MerchantTradeNo": mtn,
        "MerchantTradeDate": (now_utc() + timedelta(hours=8)).strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio", "ChoosePayment": "Credit", "EncryptType": "1",
        "TotalAmount": amount, "PeriodAmount": amount,
        "PeriodType": PERIOD_TYPE, "Frequency": FREQUENCY, "ExecTimes": EXEC_TIMES,
        "ItemName": f"機票降價通知月費 {route}", "TradeDesc": "Flight price alert monthly subscription",
        "ReturnURL": f"{API_BASE}/ecpay-return", "PeriodReturnURL": f"{API_BASE}/ecpay-period",
        "OrderResultURL": f"{API_BASE}/ecpay-result", "ClientBackURL": f"{SITE_URL}/app",
        "CustomField1": email, "CustomField2": route, "CustomField3": plan_name,
    }
    params["CheckMacValue"] = gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    inputs = "".join(f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">' for k, v in params.items())
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>前往綠界付款…</title></head><body>'
            f'<p>正在前往綠界付款頁面…</p>'
            f'<form id="ecpay" action="{ecpay_host()}/Cashier/AioCheckOut/V5" method="post">{inputs}</form>'
            f'<script>document.forms[0].submit()</script></body></html>')


def handler(event, context):
    try:
        raw = event.get("body") if isinstance(event, dict) else None
        if raw and event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        data = json.loads(raw) if isinstance(raw, str) else (raw or event)
    except (ValueError, TypeError):
        return resp(400, {"error": "invalid JSON"})

    email = str(data.get("email", "")).strip().lower()
    plan_name = str(data.get("plan_name", "")).strip().lower()
    if not EMAIL_RE.match(email):
        return resp(400, {"error": "invalid email"})
    if plan_name not in PLANS:
        return resp(400, {"error": "plan_name must be tokyo or seoul"})
    try:
        target = Decimal(str(data.get("target_price")))
    except (InvalidOperation, TypeError):
        return resp(400, {"error": "target_price must be a number"})
    if target <= 0 or target > 1000000:
        return resp(400, {"error": "target_price out of range"})

    plan = PLANS[plan_name]
    route = f"{plan['origin']}-{plan['destination']}"
    now = now_utc()
    now_iso, now_s = now.isoformat(), now.strftime(TS_FMT)
    existing = ddb.get_item(Key={"email": email, "route": route}).get("Item") or {}
    common = {":p": plan_name, ":o": plan["origin"], ":d": plan["destination"], ":t": target, ":c": "TWD", ":u": now_iso}
    base_set = ("SET plan_name=:p, origin=:o, destination=:d, target_price=:t, currency=:c, "
                "updated_at=:u, created_at=if_not_exists(created_at, :u)")

    if in_service(existing, now_s):
        # Paid (or cancelled but still inside the paid period): update the target in place, no re-payment.
        ddb.update_item(Key={"email": email, "route": route}, UpdateExpression=base_set, ExpressionAttributeValues=common)
        print(f"{email}#{route} target updated in place ({existing.get('subscription_status')})")
        return resp(200, {"ok": True, "email": email, "route": route, "plan_name": plan_name,
                          "target_price": int(target), "currency": "TWD",
                          "subscription_status": existing.get("subscription_status"),
                          "current_period_end": existing.get("current_period_end"),
                          "current_period_end_date": existing.get("current_period_end_date")})

    # Not paying yet (new, pending_payment, expired, or a legacy M1 row): record pending_payment + send to ECPay.
    mtn = "FP" + (now + timedelta(hours=8)).strftime("%y%m%d%H%M%S") + secrets.token_hex(3).upper()  # 20 chars
    ddb.update_item(Key={"email": email, "route": route},
                    UpdateExpression=base_set + ", subscription_status=:s, merchant_trade_no=:m, checkout_at=:u",
                    ExpressionAttributeValues={**common, ":s": "pending_payment", ":m": mtn})
    print(f"{email}#{route} pending_payment {mtn} (was {existing.get('subscription_status') or 'none'})")
    return {"statusCode": 200, "headers": {"content-type": "text/html; charset=utf-8"},
            "body": checkout_form(email, route, plan_name, mtn)}
