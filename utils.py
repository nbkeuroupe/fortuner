# utils.py
import json
import os
from functools import wraps
from flask import session, redirect, url_for, flash
from config import PASSWORD_FILE
from datetime import datetime
import random

# Password check / update
def check_password(input_password):
    if not os.path.exists(PASSWORD_FILE):
        return False
    with open(PASSWORD_FILE, 'r') as f:
        data = json.load(f)
    return data.get("password") == input_password

def set_password(new_password):
    with open(PASSWORD_FILE, 'w') as f:
        json.dump({"password": new_password}, f)

# Simple session-based login required
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Login required.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Simulated OTP storage
OTP_STORE = {}

def send_otp(username):
    otp = str(random.randint(100000, 999999))
    OTP_STORE[username] = otp
    print(f"[OTP DEBUG] OTP for {username}: {otp}")  # For testing/logging
    return otp

def verify_otp(username, otp):
    return OTP_STORE.get(username) == otp

# Transaction saving and loading
TRANSACTIONS_FILE = 'transactions.json'

def save_transaction(txn):
    if os.path.exists(TRANSACTIONS_FILE):
        with open(TRANSACTIONS_FILE, 'r') as f:
            data = json.load(f)
    else:
        data = []

    data.insert(0, txn)  # newest first

    with open(TRANSACTIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_transactions():
    if not os.path.exists(TRANSACTIONS_FILE):
        return []
    with open(TRANSACTIONS_FILE, 'r') as f:
        return json.load(f)
