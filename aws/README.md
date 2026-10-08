# Deployed Lambda sources (M2)

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
| flight-parser | invoked by flight-parser-wrapper (paywall: active, or cancelled until current_period_end) |

ECPay credentials and the monthly amount live in the `flight/ecpay` Secrets Manager secret.
