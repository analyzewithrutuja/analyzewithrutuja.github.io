# Deploying the chatbot worker

This Cloudflare Worker proxies chat requests from the portfolio site to Groq, keeping the API key secret.

## 1. Install Wrangler (Cloudflare's CLI)

```bash
npm install -g wrangler
```

## 2. Log in to Cloudflare (free account, no card needed)

```bash
wrangler login
```

This opens a browser window to authorize.

## 3. Set the Groq API key as a secret

From inside the `chatbot-worker` folder:

```bash
cd chatbot-worker
wrangler secret put GROQ_API_KEY
```

Paste your Groq API key (from console.groq.com/keys) when prompted. It is stored encrypted on Cloudflare, never in this repo.

## 4. Deploy

```bash
wrangler deploy
```

Wrangler prints a URL like `https://rutuja-portfolio-chatbot.<your-subdomain>.workers.dev`.

## 5. Point the widget at it

Copy that URL and paste it into `chatbot/widget.js`, replacing the placeholder:

```js
var WORKER_URL = 'https://rutuja-portfolio-chatbot.<your-subdomain>.workers.dev';
```

Add `/chat` is not needed — the worker handles all POST requests at its root.

## 6. Test

Open the site locally or after pushing to GitHub Pages, click the chat bubble, and send a message.

## Re-deploying after changes

Any time you edit `index.js`, just run `wrangler deploy` again from the `chatbot-worker` folder.
