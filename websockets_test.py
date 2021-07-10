import asyncio

import websockets


async def listen():
    # url = 'wss://stream.binance.com:9443/stream?streams={symbol}@miniTicker' working websocket, but from different site

    url = 'wss://stream.coinmarketcap.com/price/latest'
    print(url)
    async with websockets.connect(url) as client:
        print(await client.recv())


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(listen())
