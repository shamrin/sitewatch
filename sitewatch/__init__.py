import asyncio
import httpx

async def main():
    print('starting up')
    url = 'https://httpbin.org/get'
    sleep = 60 * 5
    async with httpx.AsyncClient() as client:
        while True:
            r = await client.get(url)
            print(f'{url}:', 'OK' if b'httpx' in r.content else 'ERROR')
            print(f'waiting {sleep}s...')
            await asyncio.sleep(sleep)

def start():
    asyncio.run(main())
