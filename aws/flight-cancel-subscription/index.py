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
import time, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
ddb = boto3.resource("dynamodb").Table("subscriptions")
_sqs = boto3.client("sqs")
_supabase = None


def resp(code, body):
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def supabase_email(token):
    """Return the signed-in user's email for a Supabase access token, or None."""
    global _supabase
    if _supabase is None:
        _supabase = json.loads(_sm.get_secret_value(SecretId="flight/supabase")["SecretString"])
    req = urllib.request.Request(_supabase["url"].rstrip("/") + "/auth/v1/user",
                                 headers={"apikey": _supabase["publishable_key"], "Authorization": f"Bearer {token}",
                                          "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return (json.loads(r.read()).get("email") or "").strip().lower() or None
    except (urllib.error.URLError, ValueError) as ex:
        print(f"supabase token check failed: {ex}")
        return None


def ecpay_cancel(mtn):
    cfg = ecpay_cfg()
    params = {"MerchantID": cfg["merchant_id"], "MerchantTradeNo": mtn, "Action": "Cancel",
              "TimeStamp": str(int(time.time()))}
    params["CheckMacValue"] = gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    req = urllib.request.Request(f"{ecpay_host()}/Cashier/CreditCardPeriodAction",
                                 data=urllib.parse.urlencode(params).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.URLError as ex:
        return None, f"network error {ex}"
    res = {k: v[0] for k, v in urllib.parse.parse_qs(body, keep_blank_values=True).items()}
    return res.get("RtnCode"), res.get("RtnMsg") or body[:200]


def handler(event, context):
    headers = {k.lower(): v for k, v in ((event or {}).get("headers") or {}).items()}
    auth = headers.get("authorization", "")
    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        data = json.loads(raw)
    except (ValueError, TypeError):
        return resp(400, {"error": "invalid JSON"})
    email = str(data.get("email", "")).strip().lower()
    route = str(data.get("route", "")).strip().upper()
    if not auth.lower().startswith("bearer ") or supabase_email(auth[7:].strip()) != email:
        return resp(401, {"error": "請重新登入後再取消訂閱"})

    key = {"email": email, "route": route}
    row = ddb.get_item(Key=key).get("Item")
    if not row:
        return resp(404, {"error": "找不到這筆訂閱"})
    status = row.get("subscription_status")
    if status == "cancelled":
        return resp(200, {"ok": True, "subscription_status": "cancelled",
                          "current_period_end_date": row.get("current_period_end_date")})
    if status != "active":
        return resp(400, {"error": "這筆訂閱目前沒有在扣款，不需要取消"})

    mtn = row.get("merchant_trade_no", "")
    code, msg = ecpay_cancel(mtn)
    print(f"{email}#{route} ECPay CreditCardPeriodAction Cancel {mtn}: RtnCode={code} {msg}")
    if code not in ("1", None) and "90100150" not in str(msg):
        print(f"{mtn} ECPay cancel not confirmed; cancelling locally anyway")

    now = now_utc()
    end_s = row.get("current_period_end")
    end_date = row.get("current_period_end_date")
    if not end_s:  # rows activated before period tracking: give one period of grace
        end = add_period(now)
        end_s, end_date = end.strftime(TS_FMT), taipei_date(end)
    ddb.update_item(Key=key,
                    UpdateExpression="SET subscription_status=:c, current_period_end=:e, current_period_end_date=:ed, "
                                     "cancelled_at=:n, ecpay_cancel_result=:r",
                    ExpressionAttributeValues={":c": "cancelled", ":e": end_s, ":ed": end_date,
                                               ":n": now.strftime(TS_FMT), ":r": f"{code}|{msg}"[:200]})
    _sqs.send_message(QueueUrl=_sqs.get_queue_url(QueueName="flight-status-queue")["QueueUrl"],
                      MessageBody=json.dumps({"event_type": "cancel", "email": email, "route": route,
                                              "merchant_trade_no": mtn, "current_period_end_date": end_date}))
    return resp(200, {"ok": True, "subscription_status": "cancelled", "current_period_end": end_s,
                      "current_period_end_date": end_date})
