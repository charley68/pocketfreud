# PocketFreud Project Documentation

## Introduction

PocketFreud is a lightweight AI companion focused on emotional support and daily mental well-being. It offers a secure, user-friendly chat interface powered by OpenAI or local LLMs via Ollama.

## Architecture Overview

The app is hosted on AWS and provisioned via Terraform. It uses:

- Flask (Python backend)
- Gunicorn (WSGI server)
- Nginx (reverse proxy)
- SQLite (initial DB, can be upgraded)
- Certbot (HTTPS via Let's Encrypt)
- Optional Ollama for local AI models
- OpenAI API fallback

## Key Features (Current)

- Secure login & signup
- Per-user chat history stored
- OpenAI or Ollama model routing
- Beautiful mobile-friendly UI

## Diagrams

See `/diagrams/` for:
- Architecture
- Chat flow
- Mobile UI mockup
