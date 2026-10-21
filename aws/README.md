# Deployed Lambda sources (M2, M4)

Each folder holds the exact single-file `index.py` (handler `index.handler`, python3.12, role `flight-lambda-role`)
deployed to the AWS Lambda function of the same name in us-east-1. The front-end never calls these directly
except through the `flight-api` HTTP API.

| Function | Route / trigger |
|---|---|
| flight-save-subscription | `POST /subscribe` (pending_payment + ECPay recurring checkout form) |
| flight-ecpay-return | `POST /ecpay-return` (ECPay ReturnURL, first charge → active) |
| flight-ecpay-period | `POST /ecpay-period` (ECPay PeriodReturnURL, renewals) |
| flight-ecpay-result | `ANY /ecpay-result` (OrderResultURL, 302 back to `/app`) |
| flight-cancel-subscription | `POST /cancel` (Supabase token required; ECPay CreditCardPeriodAction Cancel → cancelled) |
| flight-status-notification | SQS `flight-status-queue` (welcome / cancel emails via Resend) |
| flight-chat | `POST /chat` (M4 AI customer service; optional Supabase token; LLM provider/key/model in `flight/llm`) |
| flight-latest-prices | `GET /prices` (latest fare per route in `flight-routes.json`) |
| flight-fare-notification | SQS `flight-fare-queue` (price-drop emails via Resend) |
| flight-parser | invoked by flight-parser-wrapper (paywall: active, or cancelled until current_period_end) |

ECPay credentials and the monthly amount live in the `flight/ecpay` Secrets Manager secret.

Routes live in `s3://flight-config-375461734944/flight-routes.json` (read by flight-parser-wrapper and flight-latest-prices). Adding a route also needs `PLANS` in flight-save-subscription and `src/components/PlanCards.tsx`, `CITY` in both notification Lambdas, and `ROUTES` in flight-chat.
