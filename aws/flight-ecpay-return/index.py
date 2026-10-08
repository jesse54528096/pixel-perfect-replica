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
from botocore.exceptions import ClientError

ddb = boto3.resource("dynamodb").Table("subscriptions")
_sqs = boto3.client("sqs")


def status_queue():
    return _sqs.get_queue_url(QueueName="flight-status-queue")["QueueUrl"]


def handler(event, context):
    p = form_params(event)
    mtn, rtn = p.get("MerchantTradeNo", ""), p.get("RtnCode", "")
    safe = {k: v for k, v in p.items() if k not in ("CheckMacValue", "CustomField1")}
    print("ReturnURL callback", json.dumps(safe, ensure_ascii=False))
    if not verify_cmv(p):
        print(f"{mtn} CheckMacValueInvalid")
        return text("0|CheckMacValueInvalid", 400)
    if p.get("MerchantID") != ecpay_cfg()["merchant_id"]:
        print(f"{mtn} MerchantID mismatch {p.get('MerchantID')}")
        return text("0|MerchantIDMismatch", 400)
    if p.get("SimulatePaid") == "1":
        print(f"{mtn} SimulatePaid=1: CMV verified, not activating")
        return text("1|OK")
    if rtn != "1":
        print(f"{mtn} first charge failed RtnCode={rtn} {p.get('RtnMsg')}: row stays pending_payment")
        return text("1|OK")

    email, route = p.get("CustomField1", "").strip().lower(), p.get("CustomField2", "").strip()
    if not email or not route:
        print(f"{mtn} missing CustomField1/2")
        return text("0|MissingCustomField", 400)
    now = now_utc()
    end = add_period(now, p.get("PeriodType") or "M", p.get("Frequency") or 1)
    try:
        ddb.update_item(
            Key={"email": email, "route": route},
            UpdateExpression=("SET subscription_status=:a, merchant_trade_no=:m, current_period_end=:e, "
                              "current_period_end_date=:ed, activated_at=:n, last_paid_at=:n, paid_amount=:amt, "
                              "total_success_times=:one, failed_renewals=:zero"),
            ConditionExpression="attribute_exists(email) AND NOT (subscription_status = :a AND merchant_trade_no = :m)",
            ExpressionAttributeValues={":a": "active", ":m": mtn, ":e": end.strftime(TS_FMT),
                                       ":ed": taipei_date(end), ":n": now.strftime(TS_FMT),
                                       ":amt": int(p.get("Amount") or p.get("TradeAmt") or 0), ":one": 1, ":zero": 0},
        )
    except ClientError as ex:
        if ex.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        print(f"{mtn} already active (or no row) for {route}: ack only")
        return text("1|OK")
    print(f"{mtn} {route} -> active until {end.strftime(TS_FMT)}")
    _sqs.send_message(QueueUrl=status_queue(), MessageBody=json.dumps(
        {"event_type": "welcome", "email": email, "route": route, "merchant_trade_no": mtn,
         "current_period_end_date": taipei_date(end), "amount": int(ecpay_cfg()["amount"])}))
    return text("1|OK")
