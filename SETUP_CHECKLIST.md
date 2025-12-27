# Setup Checklist - Replace These Values

Before deploying this project, you MUST replace the following values throughout the codebase:

## 1. Domain Name Replacement

**Search for:** `afrooexchange.com`
**Replace with:** Your domain name

### Files containing domain references:
- `docker-compose.prod.yml` - Lines 137, 139
- `nginx/nginx.conf` - Multiple locations
- `nginx/afrooexchange.conf` - Multiple locations (rename this file too)
- `bot/cogs/panels/cog.py` - Lines 133, 173, 298, 325, 344, 803
- `bot/cogs/leaderboard/views/leaderboard_view.py`
- `backend/app/services/transcript_service.py` - Line 354
- `backend/app/services/ticket_service.py` - Line 1400

**Tip:** Use find/replace across your entire project:
```bash
grep -r "afrooexchange.com" . --exclude-dir=node_modules --exclude-dir=.git
```

## 2. Environment Variables

Copy all `.env.example` files to `.env` and fill in your values:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp bot/.env.example bot/.env
cp ai-assistant-bot/.env.example ai-assistant-bot/.env
```

### Critical variables to set:
- All `ADMIN_WALLET_*` addresses (use YOUR wallets)
- `MONGODB_URL` (your database connection)
- `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`
- `TATUM_API_KEY` (get from https://dashboard.tatum.io)
- `ENCRYPTION_KEY` (generate new: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- `JWT_SECRET_KEY` (generate new: `openssl rand -hex 32`)
- All Discord role IDs and guild ID

## 3. SSL Certificates

Place your SSL certificates in `nginx/ssl/`:
- `fullchain.pem`
- `privkey.pem`

See `nginx/ssl/README.md` for instructions.

## 4. Container Names (Optional)

If you want, rename the container prefixes from `afroo-*`:
- In `docker-compose.prod.yml`
- Search for: `afroo-` and replace with your prefix

## 5. Discord Guild/Server

Update all Discord-specific references:
- Guild ID in environment variables
- Role IDs in environment variables
- Channel IDs if hardcoded anywhere

## 6. Database Name (Optional)

Default database name is `afroo_v4`. To change:
- Update in `backend/.env` (`DATABASE_NAME`)
- Update in `docker-compose.prod.yml`

## Final Check

Before deploying:
- [ ] All `.env` files created and filled
- [ ] All domain names replaced
- [ ] SSL certificates in place
- [ ] Admin wallet addresses set (YOUR wallets, not placeholders)
- [ ] Discord bot configured
- [ ] API keys obtained (Tatum, OpenAI, etc.)
- [ ] Database credentials set
- [ ] Tested locally with `docker-compose up`

---

**Important:** This checklist helps you avoid deploying with Afroo Exchange's old configuration.
