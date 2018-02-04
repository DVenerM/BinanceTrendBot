# BinanceTrendBot
Simple Momentum Trade Bot for Binance. Tracks upward/downward momentum via maket floors/ceilings and triggers buy/sell. Supports all valid trade pairs.

# Requires
Binance Account (Referral: https://www.binance.com/?ref=15669890)

`pip install python-binance`

`pip install slackclient`

# Settings
Rename `config/trendConfig.json.example` to `config/trendConfig.json`.

| Setting  | Description |
| ------------- | ------------- |
| api_key  | Account API key from Binance  |
| api_secret  | Account API secret from Binance  |
| coin | First part of trade pair you are trying to buy
| currency | Second part of trade pair you are using to fund your buy |
| up_percent | When market moves this percentage up, buy is triggered |
| down_percent | When market moves this percentage down, sell is triggered |
| invest_percent | Percentage of your currency you want to spend during a buy |
| check_interval | Number of seconds the bot waits to check market
| slack_token | Slack API token for your slack account
| slack_channel | Slack channel to post updates (eg. #general)
