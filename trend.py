#!/usr/bin/env python

from binance.client import Client
from slackclient import SlackClient
from decimal import Decimal
import json
import time
import sys
import requests
import json
import pandas as pn

sys.path.insert(0, './config')

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

    def get_orderbooks(self):
        orders = self.client.get_order_book(symbol=self.trade_pair, limit=5)
        lastBid = Decimal(orders['bids'][0][0])  # last buy price (bid)
        lastAsk = Decimal(orders['asks'][0][0])
        return lastBid, lastAsk

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

    def _format(self, price):
        if float(price) < 0.1:
            return "{:.8f}".format(price)
        else:
            return "{:.2f}".format(price)

    def buy_limit(self, rate):
        currency_balance = self.get_currency_balance()
        purchase_amount = currency_balance * self.invest_percent
        purchase_qty = (purchase_amount / rate) // self.step_size * self.step_size
        if purchase_qty > self.min_qty and purchase_qty < self.max_qty:
            try:
                result = self.client.create_order(symbol=self.trade_pair,
                                              quantity=purchase_qty,
                                              side='BUY',
                                              type='LIMIT',
                                              price=self._format(rate),
                                              timeInForce = "GTC")
            except:
                result = "Trade quantity does not meet MIN/MAX allowed by exchange."
        else:
            result = "Trade quantity does not meet MIN/MAX allowed by exchange."
        return result

    def sell_limit(self, rate):
        coin_balance = self.get_coin_balance()
        sell_qty = coin_balance // self.step_size * self.step_size
        if sell_qty > self.min_qty and sell_qty < self.max_qty:
            try:
                result = self.client.create_order(symbol=self.trade_pair,
                                                  quantity=sell_qty,
                                                  side='SELL',
                                                  type='LIMIT',
                                                  price=self._format(rate),
                                                  timeInForce="GTC")
            except:
                result = "Trade quantity does not meet MIN/MAX allowed by exchange."

        else:
            result = "Trade quantity does not meet MIN/MAX allowed by exchange."
        return result
    def buy_coin(self):
        currency_balance = self.get_currency_balance()
        purchase_amount = currency_balance * self.invest_percent
        purchase_qty = (purchase_amount / self.current_price) // self.step_size * self.step_size
        if purchase_qty > self.min_qty and purchase_qty < self.max_qty:
            result = self.client.create_order(symbol=self.trade_pair, 
                                              quantity=purchase_qty,
                                              side='BUY', type='MARKET')
        else:
            result = "Trade quantity does not meet MIN/MAX allowed by exchange."                                  
        return result

    def cancel_order(self,orderId):
        try:
            result = self.client.cancel_order(symbol=self.trade_pair, orderId=orderId)
            return result
        except Exception:
            return "Not canceled"

    def sell_coin(self):
        coin_balance = self.get_coin_balance()
        sell_qty = coin_balance // self.step_size * self.step_size
        if sell_qty > self.min_qty and sell_qty < self.max_qty:
            result = self.client.create_order(symbol=self.trade_pair,
                                              quantity=sell_qty,
                                              side='SELL', type='MARKET')
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

    def get_order(self, orderId):
        result = self.client.get_order(symbol=self.trade_pair, orderId=orderId )
        return result

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
    currency_balance =trend.get_currency_balance()
    print("Coin (" + trend.coin_name + ") Balance: ", trend.get_coin_balance())
    print("Currency (" + trend.currency_name + ") Balance: ", currency_balance)
    print("Trade Pair Current Price: ", trend.current_price)
    print("Up Momentum:", up_percent, "Down Momentum:", down_percent)
    print("Looking for entry....")
    status_count = 0
    peak =0
    koef = 1.5
    while True:
        api = requests.get('https://api.binance.com/api/v1/aggTrades?symbol=BTCUSDT&limit=250')
        data = json.loads(api.text)
        data = pn.DataFrame(data)
        # data['Time']= data['T']/100
        # data['Time'] = pn.to_datetime(data['Time']/10, unit='s')
        data.head()
        from sklearn.linear_model import LinearRegression
        y_train = data["p"]
        data = data.drop(["M", "a", "f", "l", "m", "p", "q"], axis=1)
        # X_train, X_test, y_train, y_test = prepareData(data, test_size=0.3, lag_start=12, lag_end=48)
        X_train = data
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        X_test = data
        difference = X_test.iloc[-1] - X_test.iloc[0]
        X_test['T'] = X_test['T'] + difference[0]
        X_test.columns = ["p"]
        X_test.index = X_test.index + 250
        prediction = lr.predict(X_test)
        potential = prediction[-1] - prediction[0]
        #print("Потенциал: " + potential)
        status_message=trend.status, "potential: "+ '{!r:.9}'.format(potential),\
                       " peak: "+ '{!r:.9}'.format(peak),\
                       " current price: "+'{!r:.9}'.format(float(trend.current_price)),\
                       " coef.: "+'{!r:.9}'.format(koef),\
                       " invest. %.: "+'{!r:.4}'.format(float(trend.invest_percent)*100)

       # time.sleep(check_interval)
        trend.current_price = trend.get_current_price()
  
        if trend.current_price < trend.floor:
            trend.floor = trend.current_price
        elif trend.current_price > trend.ceiling:
            trend.ceiling = trend.current_price

        print(status_message)

        if potential > (float(trend.current_price)*0.002):#0.003 для BTC
            koef = 1.1
        elif potential > (float(trend.current_price) * 0.0015):#0.002 для BTC
            koef = 1.25

        if trend.status == 'OUT' and peak < (potential*1.5) and potential < 0:# and potential > -(float(trend.current_price)*0.001):#покупка 0,001 для BTC
            #try buy with decrease
            for decrease in [0.9998, 0.9999, 1, 1.0001,]:
                #print(decrease)
                lastBid, lastAsk = trend.get_orderbooks()
                buy_results = trend.buy_limit(lastBid * Decimal(decrease))
                if buy_results == "Trade quantity does not meet MIN/MAX allowed by exchange.":
                    #last order filled, exit the loop, go to sell
                    trend.reset_floor_ceiling()
                    status_count = 0
                    trend.status = 'IN'
                    break
                status_message = "Created buy limit order @ {} | {}".format(round(trend.current_price, 2), buy_results['price'])
                print(status_message)

                if decrease==1.0001:
                    time.sleep(10)
                else:
                    time.sleep(3)

                get_order_results = trend.get_order(buy_results['orderId'])
                if float(get_order_results['executedQty']) > (float(get_order_results['origQty']) * 0.5):
                    # получилось
                    status_message = "Bought limit @ {} | {}".format(round(trend.current_price, 2), get_order_results['price'])
                    print(status_message)

                    trend.reset_floor_ceiling()
                    status_count = 0
                    trend.status = 'IN'
                    #sell_results_order_increase1002 = trend.sell_limit(float(get_order_results['price']) * 1.002)

                    break
                else:
                    # не получилось
                    cancel_order_results = trend.cancel_order(buy_results['orderId'])
                    if cancel_order_results == "Not canceled":
                        print("Failed to cancel the order, probably order filled")
                        break
                    else:
                        print("Canceled limit order")

                    trend.status = 'WAIT'

        elif trend.status == 'IN' and peak > (potential*koef) and potential > 0:#продажа

            for increase in [1.0002, 1.0001, 1, 0.9999]:
                lastBid, lastAsk = trend.get_orderbooks()
                #3print(lastAsk)
                sell_results = trend.sell_limit(lastAsk * Decimal(increase))
                #print(type(trend.current_price))
                print(sell_results)
                if sell_results == "Trade quantity does not meet MIN/MAX allowed by exchange.":
                    # last order filled, exit the loop, go to buy
                    trend.reset_floor_ceiling()
                    status_count = 0
                    trend.status = 'OUT'
                    break

                status_message = "Created sell limit order @ {} | {}".format(round(trend.current_price, 2), sell_results['price'])
                print(status_message)

                if decrease==0.9999:
                    time.sleep(10)
                else:
                    time.sleep(3)
                get_order_results = trend.get_order(sell_results['orderId'])

                if float(get_order_results['executedQty']) > (float(get_order_results['origQty']) * 0.5):
                    status_message = "Sold limit @ {} | {}".format(round(trend.current_price, 2),
                                                                   get_order_results['price'])
                    print(status_message)
                    trend.reset_floor_ceiling()
                    status_count = 0
                    trend.status = 'OUT'

                    break
                else:
                    cancel_order_results = trend.cancel_order(get_order_results['orderId'])
                    print("Cancel limit order")

            koef = 1.5

        if (status_count % 20) == 0:
            trend.post_slack_message(status_message)
            
        status_count += 1

        if potential > 0:
            if peak < potential:
                peak=potential
        elif potential < 0:
            if peak > potential:
                peak=potential

        if trend.status == 'WAIT' and potential>0:
            trend.status = 'OUT'

        

if __name__ == '__main__':
    main()

