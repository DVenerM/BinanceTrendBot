#!/usr/bin/env python

from binance.client import Client
from slackclient import SlackClient
from decimal import Decimal
import json
import time

class Trend:

    def __init__(self, api_key, api_secret, coin_name, currency_name, 
                 up_percent, down_percent, invest_percent, slack_token, slack_channel):
        self.client = Client(api_key, api_secret)
        self.coin_name = coin_name
        self.currency_name = currency_name
        self.trade_pair = coin_name + currency_name
        self.current_price = self.get_current_price()
        self.up_percent = round(Decimal(up_percent / 100), 3)
        self.down_percent = round(Decimal(down_percent / 100), 3)
        self.status = 'OUT'
        self.floor = self.current_price 
        self.ceiling = self.current_price
        self.invest_percent = Decimal(invest_percent / 100)
        self.slack_token = slack_token
        self.slack_channel = slack_channel
        self.get_market_attributes()

    def get_current_price(self):
        ticker = self.client.get_ticker(symbol=self.trade_pair)
        price = round(Decimal(ticker['lastPrice']), 8)
        return price

    def get_coin_balance(self):
        coin = self.client.get_asset_balance(asset=self.coin_name)
        balance = round(Decimal(coin['free']), 8)
        return balance

    def get_currency_balance(self):
        currency = self.client.get_asset_balance(asset=self.currency_name)
        balance = round(Decimal(currency['free']), 8)
        return balance

    def get_market_attributes(self):
        info = self.client.get_symbol_info(self.trade_pair)
        self.min_qty = Decimal(info['filters'][1]['minQty'])
        self.max_qty = Decimal(info['filters'][1]['maxQty'])
        self.step_size = Decimal(info['filters'][1]['stepSize'])
        tick_size = Decimal(info['filters'][0]['tickSize'].rstrip('0'))
        self.precision = abs(tick_size.as_tuple().exponent)
        return

    def buy_coin(self):
        currency_balance = self.get_currency_balance()
        purchase_amount = currency_balance * self.invest_percent
        purchase_qty = (purchase_amount / self.current_price) // self.step_size * self.step_size
        if purchase_qty > self.min_qty and purchase_qty < self.max_qty:
            result = self.client.create_order(symbol=self.trade_pair, 
                                              quantity=purchase_qty,
                                              side='BUY', type='MARKET')
            self.status = 'IN'
        else:
            result = "Trade quantity does not meet MIN/MAX allowed by exchange."                                  
        return result

    def sell_coin(self):
        coin_balance = self.get_coin_balance()
        sell_qty = coin_balance // self.step_size * self.step_size
        if sell_qty > self.min_qty and sell_qty < self.max_qty:
            result = self.client.create_order(symbol=self.trade_pair, 
                                              quantity=sell_qty,
                                              side='SELL', type='MARKET')
            self.status = 'OUT'
        else:
            result = "Trade quantity does not meet MIN/MAX allowed by exchange."                                  
        return result

    def reset_floor_ceiling(self):
        self.floor = self.current_price
        self.ceiling = self.current_price

    def post_slack_message(self, message):
        message = str(message)
        sc = SlackClient(self.slack_token)
        sc.api_call("chat.postMessage", channel=self.slack_channel, text=message)


def main():

    with open("config/trendConfig.json", "r") as settings:
        config = json.load(settings)

    api_key = str(config['api_key'])
    api_secret = str(config['api_secret'])
    coin_name = config['coin']
    currency_name = config['currency']
    up_percent = config.get('up_percent', 2)
    down_percent = config.get('down_percent', 3)
    invest_percent = config.get('invest_percent', 20)
    check_interval = config.get('check_interval', 60)
    slack_token = str(config['slack_token'])
    slack_channel = str(config['slack_channel'])

    print("Initializing....")
    
    trend = Trend(api_key, api_secret, coin_name, currency_name, 
                  up_percent, down_percent, invest_percent, slack_token, slack_channel)

    print("Coin (" + trend.coin_name + ") Balance: ", trend.get_coin_balance())
    print("Currency (" + trend.currency_name + ") Balance: ", trend.get_currency_balance())
    print("Trade Pair Current Price: ", trend.current_price)
    print("Up Momentum:", up_percent, "Down Momentum:", down_percent)
    print("Looking for entry....")
    status_count = 0

    while True:
        time.sleep(check_interval)
        trend.current_price = trend.get_current_price()
  
        if trend.current_price < trend.floor:
            trend.floor = trend.current_price
        elif trend.current_price > trend.ceiling:
            trend.ceiling = trend.current_price

        target_buy_price = trend.floor * (1 + trend.up_percent)
        target_sell_price = trend.ceiling * (1 - trend.down_percent)      

        if trend.status == 'OUT':
            status_message = "{}: {} | Floor: {} | Buy: {}".format(trend.trade_pair, 
                    round(trend.current_price, trend.precision), 
                    round(trend.floor, trend.precision),
                    round(target_buy_price, trend.precision))
        elif trend.status =='IN':
            status_message = "{}: {} | Ceiling: {} | Sell: {}".format(trend.trade_pair, 
                    round(trend.current_price, trend.precision), 
                    round(trend.ceiling, trend.precision),
                    round(target_sell_price, trend.precision))

        if trend.status == 'OUT' and trend.current_price >= target_buy_price:
            buy_results = trend.buy_coin()
            status_message = "Bought @ {} | {}".format(round(trend.current_price, trend.precision), buy_results) 
            trend.reset_floor_ceiling()
            status_count = 0
        elif trend.status == 'IN' and trend.current_price <= target_sell_price:
            sell_results = trend.sell_coin()
            status_message = "Sold @ {} | {}".format(round(trend.current_price, trend.precision), sell_results) 
            trend.reset_floor_ceiling()
            status_count = 0

        print(status_message)

        if (status_count % 20) == 0:
            trend.post_slack_message(status_message)
            
        status_count += 1
        

if __name__ == '__main__':
    main()
