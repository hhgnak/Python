import pyupbit
import requests
import numpy as np
import pandas as pd
import ta
from time import time, gmtime, sleep, strftime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError

import warnings
warnings.filterwarnings('ignore')

tickers = []
tickerLimit = 10

holdList = []
holdLimit = 3

df = dict()

coeff = 1
windowFast = 12 * coeff
windowSlow = 26 * coeff
windowSign = 9 * coeff

iniBalance = 0
commission = 1 - 0.05/100


def cur_time():
    return strftime('%Y-%m-%d %H:%M:%S', gmtime())


def search_top_trading_value_tickers():
    print(cur_time(), '  Searching tickers', end='')
    global tickers

    # start = time()

    headers = {"accept": "application/json"}

    temp = []
    for ticker in pyupbit.get_tickers(fiat="KRW"):
        url = "https://api.upbit.com/v1/ticker?markets=" + ticker
        response = requests.get(url, headers=headers)
        acc_trade_price = response.json()[0]['acc_trade_price_24h']
        temp.append((ticker, acc_trade_price))
        sleep(0.1)
        print('.', end='')

    temp.sort(key=lambda x: x[1], reverse=True)

    temp = temp[:tickerLimit]
    for i in range(tickerLimit):
        temp[i] = temp[i][0]

    for ticker in holdList:
        if ticker not in temp:
            i = 0
            while True:
                i += 1
                if temp[-i] not in holdList:
                    del(df[temp[-i]])
                    temp.remove(temp[-i])
                    temp.append(ticker)
                    break
    
    # print(time() - start, 'search_top_trading_value_tickers')
    
    while True:
        if 55 <= gmtime().tm_sec <= 59:
            tickers = temp
            break
        sleep(1)
    
    print('\n')
    # print(cur_time())


def get_initial_data(lst):
    print(cur_time(), '  Getting data', end='')
    # start = time()

    for ticker in lst:
        df[ticker] = pyupbit.get_ohlcv(ticker,
                                       interval="minute1",
                                       count=windowSlow + windowSign)
        
        # calculate_technical_indicators(df[ticker])
        
        df[ticker].reset_index(inplace=True)
        df[ticker].columns.values[0] = 'datetime'
        print('.', end='')
    
    print('\n')
    # print(time() - start, 'get_initial_data')
    # print(cur_time())


def get_additional_data(ticker):
    # start = time()

    df_new = pyupbit.get_ohlcv(ticker, interval="minute1", count=10)
    df_new.reset_index(inplace=True)
    df_new.columns.values[0] = 'datetime'

    df[ticker] = pd.concat([df[ticker], df_new], axis=0)
    df[ticker].drop_duplicates(subset='datetime',
                               keep='last',
                               inplace=True,
                               ignore_index=True)
    
    df[ticker] = df[ticker].iloc[-(windowSlow + windowSign):]
    df[ticker].reset_index(drop=True, inplace=True)

    calculate_technical_indicators(df[ticker])
    
    # print(time() - start, 'get_additional_data')
    # print(cur_time())


def calculate_technical_indicators(dataframe):
    # start = time()

    for window in [windowFast, windowSlow]:
        column_name = ''.join(('ma', str(window)))
        dataframe[column_name] = ta.trend.ema_indicator(dataframe['close'],
                                                        window=window)
    
    # dataframe['macd'] = ta.trend.macd(dataframe['close'], 
    #                                   window_slow=windowSlow,
    #                                   window_fast=windowFast)
    
    dataframe['macdDiff'] = ta.trend.macd_diff(dataframe['close'], 
                                                window_slow=windowSlow,
                                                window_fast=windowFast,
                                                window_sign=windowSign)
    
    # print(time() - start, 'calculate_technical_indicators')
    # print(cur_time())


def decide_buy_or_sell(ticker):
    data = df[ticker].iloc[-2]

    if (
        data[''.join(('ma', str(windowFast)))] > data[''.join(('ma', str(windowSlow)))] and
        data['macdDiff'] > 0
    ):
        flag = 1
    
    elif (
        not data[''.join(('ma', str(windowFast)))] > data[''.join(('ma', str(windowSlow)))]
    ):
        flag = -1
    
    else:
        flag = 0

    return flag


def buy(ticker):
    print('%s  Buy  %5s' %(cur_time(), ticker.split('-')[1]))


def sell(ticker):
    print('%s  Sell %5s' %(cur_time(), ticker.split('-')[1]))


def trade():
    start = time()

    for ticker in tickers:
        try:
            df[ticker]
        except KeyError:
            get_initial_data(list(ticker))
            continue

        get_additional_data(ticker)

        decision = decide_buy_or_sell(ticker)
        if decision == 1:
            buy(ticker)
        elif decision == -1:
            sell(ticker)
    # print(df['KRW-BTC'].tail())


def report():
    import datetime as dt
    import time
    import smtplib
    from email.mime.text import MIMEText

    # curBalance = upbit.get_balance("KRW")
    # dailyReturn = (curBalance / iniBalance - 1) * 100
    # iniBalance = curBalance

    iniBalance = 1
    curBalance = 1.15
    dailyReturn = (curBalance / iniBalance - 1) * 100

    transaction = [('2023-04-18  13:04:05', 'BTC', 2.6), ('2023-04-18  23:44:55', 'ETH', -1.4), ('2023-04-21  05:41:01', 'ETH', 0.4)]

    #smtp 인스턴스 생성 (서버url, port)
    smtp = smtplib.SMTP('smtp.gmail.com', 587)

    # TLS 보안 시작
    smtp.starttls()

    # 서버 로그인을 위해 login 함수 호출
    smtp.login('hhgnak@gmail.com', 'opzeqzibovjpiutl')

    # 보낼 메시지
    today = time.strftime('%Y-%m-%d', time.localtime(time.time()))

    msg_dailyReturn = 'Daily Return : %5.1f %%\n\n' % dailyReturn

    msg_transaction = ''
    for t, m, r in transaction:
        msg_transaction += '%s    %4s   %5.1f %%\n' % (t, m, r)

    msg = msg_dailyReturn + msg_transaction

    message = MIMEText(msg)
    message['Subject'] = 'TradingBot Report / ' + today

    # 메일 보내기
    smtp.sendmail('hhgnak@gmail.com', 'hhgnak@gmail.com', message.as_string())

    # 세션 종료
    smtp.quit()
    # print(msg)


def main():
    # iniBalance = upbit.get_balance("KRW")

    search_top_trading_value_tickers()
    get_initial_data(tickers)

    schedule = BackgroundScheduler()
    schedule.add_job(search_top_trading_value_tickers, 'cron', minute='0, 30', id='update_tickers')
    schedule.add_job(trade, 'cron', second=2, id='trade')
    schedule.add_job(report, 'cron', hour=0, id='report')
    schedule.start()

    while True:
        # print(cur_time())
        sleep(10)


if __name__ == "__main__":
    main()
