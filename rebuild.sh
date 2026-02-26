#!/bin/bash
docker compose down 
docker compose build --no-cache scraper 
docker compose up -d --force-recreate scraper
