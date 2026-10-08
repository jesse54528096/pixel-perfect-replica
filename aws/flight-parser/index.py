import json, os, urllib.request, urllib.parse, urllib.error
from datetime import date, datetime, timezone
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Attr

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
_sm = boto3.client("secretsmanager")
_sqs = boto3.client("sqs")
_s3 = boto3.client("s3")
_ddb = boto3.resource("dynamodb").Table("subscriptions")
_token = None
_qurl = None


def token():
    global _token
    if _token is None:
        _token = json.loads(_sm.get_secret_value(SecretId="flight/travelpayouts")["SecretString"])["token"]
    return _token


def qurl():
    global _qurl
    if _qurl is None:
        _qurl = _sqs.get_queue_url(QueueName="flight-fare-queue")["QueueUrl"]
    return _qurl


def next_month():
    t = date.today()
    y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
    return f"{y:04d}-{m:02d}"


def fetch_cheapest(origin, destination, month, tok, currency):
    q = urllib.parse.urlencode({"origin": origin, "destination": destination, "depart_date": month,
                                "currency": currency, "token": tok})
    req = urllib.request.Request(f"https://api.travelpayouts.com/v1/prices/cheap?{q}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
    except (urllib.error.URLError, ValueError) as ex:
        print(f"fetch {origin}-{destination} {currency} failed: {ex}")
        return None
    if not body.get("success") or not body.get("data"):
        return None
    offers = body["data"].get(destination, {})
    if not offers:
        return None
    best = min(offers.values(), key=lambda o: o["price"])
    return {"price": best["price"], "currency": currency.upper(), "airline": best.get("airline"),
            "depart_date": best.get("departure_at"), "return_date": best.get("return_at")}


def save_latest(route, month, tw, us):
    # Latest fare per route, read by GET /prices for the dashboard; never blocks matching.
    body = {"route": route, "month": month, "price": tw["price"], "currency": "TWD", "airline": tw["airline"],
            "depart_date": tw["depart_date"], "return_date": tw["return_date"],
            "price_usd": us["price"] if us else None,
            "checked_at": datetime.now(timezone.utc).isoformat()}
    try:
        _s3.put_object(Bucket=os.environ["CONFIG_BUCKET"], Key=f"prices/{route}.json",
                       Body=json.dumps(body), ContentType="application/json")
    except Exception as ex:
        print(f"save latest price for {route} failed: {ex}")


def subscribers(route):
    items, kw = [], {"FilterExpression": Attr("route").eq(route)}
    while True:
        page = _ddb.scan(**kw)
        items += page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            return items
        kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def paid_gate(it, now_s):
    """Paywall: serve active rows and cancelled rows still inside the paid period; lazily expire lapsed ones."""
    st = it.get("subscription_status")
    if st == "active":
        return True
    if st == "cancelled":
        if it.get("current_period_end", "") >= now_s:
            return True
        _ddb.update_item(Key={"email": it["email"], "route": it["route"]},
                         UpdateExpression="SET subscription_status=:x, expired_at=:n",
                         ConditionExpression="subscription_status = :c",
                         ExpressionAttributeValues={":x": "expired", ":n": now_s, ":c": "cancelled"})
        print(f"{it['email']}#{it['route']} gate: cancelled grace ended {it.get('current_period_end')} -> expired")
        return False
    print(f"{it['email']}#{it['route']} gate: skip ({st or 'no status'})")
    return False


def handler(event, context):
    origin, destination = event["origin"], event["destination"]
    route = event.get("route") or f"{origin}-{destination}"
    month = next_month()
    tok = token()

    tw = fetch_cheapest(origin, destination, month, tok, "twd")
    if not tw:
        print("no TWD fare for", route, month, "(empty/429) - skipping")
        return {"ok": True, "route": route, "matched": 0}
    print(f"{route} {month} cheapest {tw['price']} TWD {tw['airline']} {tw['depart_date']}")
    us = fetch_cheapest(origin, destination, month, tok, "usd")  # best-effort only
    if us:
        print(f"{route} {month} cheapest {us['price']} USD {us['airline']}")
    save_latest(route, month, tw, us)

    matched = 0
    now_s = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for it in subscribers(route):
        if not paid_gate(it, now_s):
            continue
        tp = Decimal(str(it.get("target_price", 0)))
        if tp < Decimal(str(tw["price"])):
            continue
        body = {"email": it["email"], "route": route, "plan_name": it.get("plan_name"),
                "target_price": int(tp),
                "cheapest": {"price": tw["price"], "currency": "TWD", "airline": tw["airline"],
                             "depart_date": tw["depart_date"], "return_date": tw["return_date"]}}
        if us:
            body["cheapest_usd"] = {"price": us["price"], "currency": "USD", "airline": us["airline"],
                                    "depart_date": us["depart_date"], "return_date": us["return_date"]}
        _sqs.send_message(QueueUrl=qurl(), MessageBody=json.dumps(body))
        matched += 1
    print(f"{route} matched {matched} subscriber(s)")
    return {"ok": True, "route": route, "price_twd": tw["price"], "matched": matched}
