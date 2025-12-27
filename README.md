# Afroo Exchange Web, API, Bots

> **Note:** This project was developed rapidly over a few days, so while functional, the code may not follow best practices in all areas. It served as the foundation for the Afroo Exchange platform, which has now been discontinued. The codebase is provided as is for educational purposes and as a starting point for similar projects. Yes its functional but just change stuff as you need.

## About This Project

**Created by:** Pax (AfrooExchAdmin)
**License:** MIT (Free to use, modify, or sell with credit)

This codebase is now open source and available for anyone to learn from, modify, or use for their own projects. If you use this code in your project, please give credit to Pax (AfrooExchAdmin) as the original author.

## Features

Discord and Website for tickets, exchange system, crypto to crypto swaps, Auto Middle Man, Crypto Wallets, Applicatoins and MUCH MUCH more. System was designed to be scam proof unless shitty admin's!

## Tech Stack

**Backend:**
- FastAPI (Python)
- MongoDB (Database)
- Redis (Caching/Sessions)
- Tatum API (Blockchain integration)

**Frontend:**
- Next.js 14 (React)
- TypeScript
- Tailwind CSS
- shadcn/ui components

**Bot:**
- py-cord (Discord bot framework)
- Motor (Async MongoDB driver)

**Infrastructure:**
- Docker & Docker Compose
- NGINX (Reverse proxy)
- Prometheus & Grafana (Monitoring)


## Project Structure

```
ProjectAfroo/
├── backend/            # FastAPI backend service
├── frontend/           # Next.js web application
├── bot/                # Discord bot (py-cord)
├── ai-assistant-bot/   # AI assistant bot (Anthropic)
├── nginx/              # NGINX reverse proxy config
├── monitoring/         # Prometheus & Grafana
└── scripts/            # MongoDB initialization scripts
```

## Configuration

Each service requires its own `.env` file. See the respective `.env.example` files:
- `backend/.env.example` - API configuration
- `frontend/.env.example` - Frontend configuration
- `bot/.env.example` - Discord bot configuration
- `ai-assistant-bot/.env.example` - AI assistant configuration

**Important:** Generate secure keys for production:
```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate JWT secret
openssl rand -hex 32
```

## Security

 **Important Security Notes:**
- Never commit `.env` files to git
- Change all default passwords in production
- Use strong encryption keys
- Keep private keys encrypted
- Enable rate limiting in production

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**You are free to:**
- Use this code for any purpose (personal or commercial)
- Modify and adapt it to your needs
- Sell products or services based on this code

**Requirement:**
- Give credit to Pax (AfrooExchAdmin) as the original author

## Acknowledgments

- Original author: Pax (AfrooExchAdmin)
- Built with FastAPI, Next.js, and py-cord
- Blockchain integration powered by Tatum
- Thanks to everyone who used and supported Afroo Exchange

---

**Created by Pax (AfrooExchAdmin) | Free to use or sell with credit**
