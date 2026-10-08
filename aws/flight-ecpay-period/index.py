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
from boto3.dynamodb.conditions import Attr

ddb = boto3.resource("dynamodb").Table("subscriptions")
MAX_FAILED = 6  # ECPay terminates the series after 6 consecutive failed renewals


def find_row(p):
    email, route = p.get("CustomField1", "").strip().lower(), p.get("CustomField2", "").strip()
    if email and route:
        return ddb.get_item(Key={"email": email, "route": route}).get("Item")
    kw = {"FilterExpression": Attr("merchant_trade_no").eq(p.get("MerchantTradeNo", ""))}
    while True:
        page = ddb.scan(**kw)
        if page.get("Items"):
            return page["Items"][0]
        if "LastEvaluatedKey" not in page:
            return None
        kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def handler(event, context):
    p = form_params(event)
    mtn, rtn = p.get("MerchantTradeNo", ""), p.get("RtnCode", "")
    safe = {k: v for k, v in p.items() if k not in ("CheckMacValue", "CustomField1")}
    print("PeriodReturnURL callback", json.dumps(safe, ensure_ascii=False))
    if not verify_cmv(p):
        print(f"{mtn} CheckMacValueInvalid")
        return text("0|CheckMacValueInvalid", 400)
    if p.get("MerchantID") != ecpay_cfg()["merchant_id"]:
        return text("0|MerchantIDMismatch", 400)
    if p.get("SimulatePaid") == "1":
        print(f"{mtn} SimulatePaid=1: CMV verified, not changing the row")
        return text("1|OK")
    row = find_row(p)
    if not row or row.get("merchant_trade_no") != mtn:
        print(f"{mtn} no matching subscription row: ack only")
        return text("1|OK")
    key = {"email": row["email"], "route": row["route"]}
    now = now_utc()
    if rtn == "1":
        times = int(p.get("TotalSuccessTimes") or 0)
        if times and times <= int(row.get("total_success_times", 0)):
            print(f"{mtn} renewal #{times} already recorded: ack only")
            return text("1|OK")
        prev_end = row.get("current_period_end", "")
        start = max(now, datetime.strptime(prev_end, TS_FMT).replace(tzinfo=timezone.utc)) if prev_end else now
        end = add_period(start, p.get("PeriodType") or "M", p.get("Frequency") or 1)
        status = "cancelled" if row.get("subscription_status") == "cancelled" else "active"
        ddb.update_item(Key=key, UpdateExpression=("SET subscription_status=:s, current_period_end=:e, "
                                                   "current_period_end_date=:ed, last_paid_at=:n, "
                                                   "total_success_times=:t, failed_renewals=:z"),
                        ExpressionAttributeValues={":s": status, ":e": end.strftime(TS_FMT), ":ed": taipei_date(end),
                                                   ":n": now.strftime(TS_FMT), ":t": times or int(row.get("total_success_times", 0)) + 1,
                                                   ":z": 0})
        print(f"{mtn} renewal ok #{times} -> {status} until {end.strftime(TS_FMT)}")
        return text("1|OK")
    failed = int(row.get("failed_renewals", 0)) + 1
    expire = failed >= MAX_FAILED
    ddb.update_item(Key=key, UpdateExpression="SET failed_renewals=:f" + (", subscription_status=:x" if expire else ""),
                    ExpressionAttributeValues={":f": failed, **({":x": "expired"} if expire else {})})
    print(f"{mtn} renewal failed RtnCode={rtn} {p.get('RtnMsg')} (#{failed}){' -> expired' if expire else ''}")
    return text("1|OK")
