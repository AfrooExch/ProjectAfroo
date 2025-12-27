# Backend Utility Scripts

This directory contains utility scripts for maintenance, troubleshooting, and administrative tasks for the Afroo Exchange backend.

## Directory Structure

```
scripts/
├── checks/          # Diagnostic and verification scripts
├── fixes/           # Scripts to fix data inconsistencies
├── withdrawals/     # Manual withdrawal and fund movement scripts
├── maintenance/     # Routine maintenance and cleanup scripts
├── analysis/        # Data analysis and investigation scripts
└── backup_*.py      # Database backup scripts (root level)
```

---

## Checks (Diagnostic Scripts)

Located in `/checks/` - These scripts verify system state and data integrity without making changes.

### Balance Verification
- **check_balances.py** - Verify wallet balance consistency across systems
- **check_all_exchanger_balances.py** - Check all exchanger wallet balances
- **check_exchanger_balances.py** - Check specific exchanger balances
- **check_all_user_wallets.py** - Verify all user wallet states

### Deposit Verification
- **check_deposits.py** - Verify deposit transactions
- **check_specific_deposit.py** - Check a specific deposit by ID/hash
- **check_user_deposits.py** - Check deposits for a specific user

### Cryptocurrency-Specific Checks
- **check_ltc_wallet_status.py** - Litecoin wallet status
- **check_ltc_wallets.py** - Check all LTC wallets
- **check_ltc_wallets_v4.py** - LTC wallet verification (v4 system)
- **check_ltc_exchanger_keys.py** - Verify LTC private key encryption
- **check_usdc_sol_onchain.py** - USDC-SOL on-chain verification
- **check_exchanger_usd_onchain.py** - On-chain USD value verification

### Usage
```bash
# Run from backend directory
python check_balances.py
python check_deposits.py
python check_specific_deposit.py <deposit_id>
```

**Safety**: ✅ Read-only operations, safe to run anytime

---

## Fixes (Repair Scripts)

Located in `/fixes/` - These scripts modify data to fix inconsistencies. **Use with caution**.

- **fix_exchanger_encryption.py** - Re-encrypt exchanger private keys if encryption is broken
- **fix_owner_sol_wallet.py** - Fix owner's Solana wallet configuration
- **fix_usdc_sol_wallets.py** - Repair USDC-SOL wallet data

### Usage
```bash
# Run with caution - these modify data
python fix_exchanger_encryption.py
```

**Safety**: ⚠️  **Modifies database** - Always backup first
**Prerequisites**:
- Database backup created
- Understand what the script does
- Test in development first if possible

---

## Withdrawals (Fund Movement)

Located in `/withdrawals/` - Scripts for manually moving funds. **Highly sensitive**.

- **withdraw_all_wallet_funds.py** - Withdraw all funds from specified wallet
- **withdraw_exchanger_balances.py** - Withdraw exchanger wallet balances
- **withdraw_ltc_direct.py** - Direct LTC withdrawal bypass
- **withdraw_sol_direct.py** - Direct SOL withdrawal bypass

### Usage
```bash
# Requires admin credentials
python withdraw_exchanger_balances.py --exchanger-id <id>
```

**Safety**: 🔴 **MOVES REAL FUNDS** - Extreme caution required
**Prerequisites**:
- Admin authorization
- Double-check recipient addresses
- Verify gas fees and network
- Test with small amount first
- Document all withdrawals

---

## Maintenance (Routine Operations)

Located in `/maintenance/` - Regular maintenance and administrative tasks.

- **decrypt_exchanger_key.py** - Decrypt and view an exchanger's private key (admin only)
- **get_exchanger_keys.py** - Retrieve exchanger key information
- **recover_private_key.py** - Recover private key from encrypted format
- **sweep_all_exchanger_wallets.py** - Consolidate funds from multiple exchanger wallets

### Usage
```bash
python decrypt_exchanger_key.py --exchanger-id <id>
python sweep_all_exchanger_wallets.py --dry-run
```

**Safety**: ⚠️  **Access to sensitive data** - Admin only
**Prerequisites**:
- ENCRYPTION_KEY must be correctly set
- Admin authorization
- Log all access

---

## Analysis (Investigation)

Located in `/analysis/` - Scripts for investigating issues and analyzing data.

- **analyze_ltc_issue.py** - Analyze Litecoin transaction issues

### Usage
```bash
python analysis/analyze_ltc_issue.py
```

**Safety**: ✅ Read-only analysis

---

## Backup Scripts (Root Level)

Located in `/scripts/` - Database backup automation.

- **backup_mongodb.py** - Local MongoDB backup with rotation
- **backup_mongodb_atlas.py** - MongoDB Atlas cloud backup

### Usage
```bash
python backup_mongodb.py
```

**Schedule**: Run via cron job (recommended: every 6 hours)

---

## Best Practices

### Before Running Any Script

1. **Understand what it does** - Read the script or ask a senior developer
2. **Check if it modifies data** - Look for database write operations
3. **Backup if needed** - For any fix/withdrawal/maintenance script
4. **Test in development** - If possible, test on dev environment first
5. **Document execution** - Log when you ran it and why

### Required Environment Variables

All scripts require these environment variables to be set (from `/backend/.env`):

```bash
MONGODB_URL=...
ENCRYPTION_KEY=...
REDIS_URL=...
# etc.
```

### Running Scripts

```bash
# From backend directory
cd /root/ProjectAfroo/backend

# Activate virtual environment if using one
# source venv/bin/activate

# Run script
python scripts/checks/check_balances.py
```

### Common Flags

Many scripts support these flags:
- `--dry-run` - Show what would happen without making changes
- `--verbose` - Detailed output
- `--help` - Show usage information

### Error Handling

If a script fails:
1. Check logs for error details
2. Verify environment variables are set
3. Check database connectivity
4. Ensure MongoDB/Redis are running
5. Verify ENCRYPTION_KEY is correct (for key-related scripts)

---

## Security Warnings

### Scripts That Access Private Keys
⚠️  These scripts can decrypt and view private keys:
- `decrypt_exchanger_key.py`
- `recover_private_key.py`
- `get_exchanger_keys.py`

**Access Control**:
- Admin only
- Log all executions
- Never share output (contains sensitive data)
- Use encrypted communication if sharing keys

### Scripts That Move Funds
🔴 These scripts can transfer cryptocurrency:
- All scripts in `/withdrawals/`
- `sweep_all_exchanger_wallets.py`

**Access Control**:
- Requires explicit authorization from management
- Two-person verification recommended
- Document all fund movements
- Verify addresses before execution

---

## Adding New Scripts

When creating new utility scripts:

1. **Choose appropriate directory**:
   - Read-only verification → `/checks/`
   - Data modifications → `/fixes/`
   - Fund movements → `/withdrawals/`
   - Regular tasks → `/maintenance/`
   - Investigation → `/analysis/`

2. **Follow naming convention**:
   - `check_*.py` for diagnostic scripts
   - `fix_*.py` for repair scripts
   - `withdraw_*.py` for fund movement
   - Descriptive names (e.g., `check_ltc_wallet_status.py`)

3. **Include documentation**:
   - Docstring explaining purpose
   - Usage examples
   - Safety warnings if it modifies data
   - Required environment variables

4. **Add to this README** - Document the new script in the appropriate section

---

## Questions or Issues?

For questions about these scripts or to report issues:
- Check inline comments in the script
- Ask in #tech-support Discord channel
- Contact backend development team

**For urgent issues with fund movements**: Contact head admin immediately.

---

**Last Updated**: 2024-12-16
