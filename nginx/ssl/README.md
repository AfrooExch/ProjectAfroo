# SSL Certificates Directory

This directory should contain your SSL/TLS certificates for HTTPS.

## Required Files

Place your SSL certificates here:
- `fullchain.pem` - Full certificate chain
- `privkey.pem` - Private key

## Generating Certificates

### Option 1: Let's Encrypt (Recommended for Production)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Certificates will be in /etc/letsencrypt/live/yourdomain.com/
# Copy them to this directory or update nginx.conf paths
```

### Option 2: Self-Signed (Development Only)

```bash
# Generate self-signed certificate (for testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem \
  -out fullchain.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

## Security Notes

⚠️ **IMPORTANT:**
- **NEVER** commit SSL certificates to git
- Keep your private key secure and encrypted
- Certificates are already in `.gitignore`
- Rotate certificates before expiration
- Use strong encryption (RSA 2048+ or ECC)

## File Permissions

Set proper permissions for security:
```bash
chmod 644 fullchain.pem
chmod 600 privkey.pem
```

## Nginx Configuration

The nginx configuration expects certificates at:
- `/etc/nginx/ssl/fullchain.pem`
- `/etc/nginx/ssl/privkey.pem`

Update `nginx/nginx.conf` and `nginx/afrooexchange.conf` with your domain name and certificate paths.
