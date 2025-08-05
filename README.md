# 🏦 Card Payment Terminal - Production Grade

A production-ready **M0/M1 card payment settlement server** that processes card transactions via ISO8583 and automatically converts funds to cryptocurrency payouts.

## 🏗️ Architecture

```
Customer → Card Terminal → Card Issuer Server (ISO8583) → Crypto Engine → Merchant Wallet
```

## ⚡ Key Features

- **M0/M1 Card Processing** - Handles privately loaded cards with real balances
- **ISO8583 Integration** - Connects to card issuer servers (not Visa/MC directly)
- **Immediate Crypto Payouts** - Instant USDT conversion (TRC-20/ERC-20)
- **Production Security** - Rate limiting, logging, error handling
- **Mobile Compatible** - Responsive web interface + Android support
- **Multi-Protocol Support** - POS Terminal protocols 101.1-201.5

## 🚀 Quick Deploy to Render

### 1. **Environment Setup**
```bash
# Copy environment template
cp .env.example .env

# Edit with your values
nano .env
```

### 2. **Required Environment Variables**
```bash
# Crypto Keys (CRITICAL - Set in Render Dashboard)
TRON_PRIVATE_KEY=your-tron-private-key
ETH_PRIVATE_KEY=your-ethereum-private-key
INFURA_PROJECT_ID=your-infura-project-id

# Security
SECRET_KEY=your-super-secret-key

# Conversion Settings
CONVERSION_FEE_PERCENT=2.5
```

### 3. **Deploy to Render**
1. Connect your GitHub repo to Render
2. Use `render.yaml` configuration (already included)
3. Set environment variables in Render dashboard
4. Deploy! 🚀

## 📱 API Endpoints

### **Settlement Webhook** (For Card Terminals)
```http
POST /api/v1/settlement
Content-Type: application/json

{
  "transaction_id": "TXN123456789",
  "card_number": "4000000000001234",
  "amount": "100.00",
  "merchant_id": "MERCHANT001",
  "wallet_address": "TQn9Y2khEsLMWD...",
  "network": "TRON",
  "fund_type": "M0"
}
```

### **Health Check**
```http
GET /health
```

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run development server
python app.py
```

## 🏭 Production Features

### **Security**
- ✅ Rate limiting (60/min, 1000/hour)
- ✅ Security headers (XSS, CSRF protection)
- ✅ Input validation & sanitization
- ✅ Secure session management
- ✅ Login attempt limiting

### **Monitoring & Logging**
- ✅ Structured JSON logging
- ✅ Performance metrics
- ✅ Error tracking
- ✅ Transaction audit trail
- ✅ Real-time health checks

### **Crypto Processing**
- ✅ TRON TRC-20 USDT payouts
- ✅ Ethereum ERC-20 USDT payouts
- ✅ Gas optimization
- ✅ Transaction retry logic
- ✅ Address validation

### **Scalability**
- ✅ Gunicorn WSGI server
- ✅ Connection pooling
- ✅ Async crypto processing
- ✅ Database-ready architecture

## 📊 Transaction Flow

1. **Card Insert** - Customer inserts M0/M1 card
2. **BIN Lookup** - System identifies card issuer server
3. **ISO8583 Request** - Sends authorization to issuer
4. **Network Validation** - Issuer validates with Visa/MC
5. **Authorization Response** - Approve/Decline received
6. **Crypto Conversion** - If approved, convert M0/M1 → USDT
7. **Immediate Payout** - Send USDT to merchant wallet
8. **Transaction Log** - Record complete audit trail

## 🔒 Security Best Practices

- Store private keys in environment variables only
- Use HTTPS in production (Render provides this)
- Regularly rotate API keys and secrets
- Monitor transaction logs for anomalies
- Set appropriate transaction limits

## 📈 Monitoring

Access logs and metrics at:
- Health: `https://your-app.onrender.com/health`
- Admin: `https://your-app.onrender.com/login`

## 🆘 Support

For production issues:
1. Check `/health` endpoint
2. Review application logs in Render dashboard
3. Verify environment variables are set
4. Check crypto network status

## 📝 License

Production-ready card payment terminal system.

---

**⚠️ Important:** This system processes real financial transactions. Ensure proper testing and compliance before production use.
