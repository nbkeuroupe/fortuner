# 🏦 M0/M1 Card Terminal - Production Deployment Guide

## 🚀 Quick Deploy to Render

### Step 1: Prepare Repository
```bash
# Initialize Git repository
git init
git add .
git commit -m "Initial M0/M1 Card Terminal"

# Create GitHub repository and push
git remote add origin https://github.com/yourusername/m0-m1-terminal.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Render
1. **Create Render Account**: https://render.com
2. **Connect GitHub**: Link your repository
3. **Create Web Service**: 
   - Repository: `yourusername/m0-m1-terminal`
   - Branch: `main`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn main:app --bind 0.0.0.0:$PORT --workers 2`

### Step 3: Environment Variables
Set these in Render Dashboard:

**Required:**
```
SECRET_KEY=your-super-secret-production-key
TERMINAL_USERNAME=blackrock
TERMINAL_PASSWORD=terminal123
MAX_TRANSACTION_AMOUNT=10000000.00
CONVERSION_FEE_PERCENT=2.5
```

**For Real Crypto (Optional):**
```
TRON_MERCHANT_WALLET=your-tron-mainnet-address
ETH_MERCHANT_WALLET=your-ethereum-mainnet-address
TRON_PRIVATE_KEY=your-tron-private-key
ETH_PRIVATE_KEY=your-ethereum-private-key
INFURA_PROJECT_ID=your-infura-project-id
```

---

## 🧪 Local Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Locally
```bash
# Development mode
python test_app.py

# Production mode
python main.py
```

### Test Crypto Payouts
```bash
# Test testnet payouts
python crypto_testnet.py

# Test full transaction flow
python test_testnet_transaction.py
```

---

## 🔧 Production Configuration

### Security Checklist
- [ ] Change default login credentials
- [ ] Set strong SECRET_KEY
- [ ] Configure real blockchain private keys
- [ ] Set up SSL/HTTPS
- [ ] Configure rate limiting
- [ ] Set up monitoring

### Blockchain Networks
- **Testnet**: TRON Shasta, Ethereum Sepolia
- **Mainnet**: TRON, Ethereum (for production)

### M0/M1 Card Integration
- Configure ISO8583 host/port for real card processing
- Update `iso_client.py` with production endpoints

---

## 📊 Features

✅ **Core Functionality:**
- Login dashboard
- Card terminal interface
- Transaction processing
- Crypto payouts (TRON/Ethereum)
- Transaction results page
- Real testnet integration

✅ **Security:**
- Rate limiting
- Session management
- Input validation
- Secure headers

✅ **Production Ready:**
- Gunicorn WSGI server
- Environment configuration
- Health check endpoint
- Error handling

---

## 🌐 Live URLs

After deployment:
- **Terminal**: `https://your-app.onrender.com`
- **Health Check**: `https://your-app.onrender.com/health`
- **Login**: `https://your-app.onrender.com/login`

---

## 📞 Support

For issues or questions:
1. Check logs in Render dashboard
2. Verify environment variables
3. Test locally first
4. Check blockchain network status

**Your M0/M1 Card Terminal is production-ready!** 🚀
