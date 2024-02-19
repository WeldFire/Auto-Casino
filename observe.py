import asyncio
import os
import websockets
import json
import aiohttp
import random
import datetime as dt
import pprint


ALLOW_BROWSER_REFRESHING = False

VERSION="1.0"

refreshBrowser = False
id = 1
spy_host_address = "http://localhost:9332/json"
targeted_tab = "https://lobby.chumbacasino.com"

# Interesting urls
# games/blackjack/init
# games/blackjack/hit
# games/blackjack/deal
interesting_url = "games/blackjack/"

pp = pprint.PrettyPrinter(indent=4)

async def sendCommand(ws, method, params={}):
    global id
    print(f"Sending command {method}, with id {id} and params {params}")
    await ws.send(json.dumps({"id":id, "method":method,"params":params}))
    id = id + 1
    

async def refreshBrowser(ws):
    if ALLOW_BROWSER_REFRESHING:
        print("Attempting to reload page")
        await sendCommand(ws, "Page.stopLoading")
        await sendCommand(ws, "Network.clearBrowserCache")
        await sendCommand(ws, "Network.clearBrowserCookies")
        await sendCommand(ws, "Page.reload", {"ignoreCache":True})
        print("Finished forcefully reloading the page")
    else:
        print("Browser refreshing has been disabled!")

            


async def main():
    global fingerprint
    global appCheckToken
    
    SS_LOGGING_PREFIX = 'Observer - '
    # Chrome runs an HTTP handler listing available tabs
    async with aiohttp.ClientSession() as session:
        async with session.get(spy_host_address) as resp:
            resp_json = await resp.json()
            print(f"{SS_LOGGING_PREFIX}{len(resp_json)} available tabs, Chrome response:")
            targetTabId = -1
            tabId = 0
            for resp_json_element in resp_json:
                tabUrl = resp_json_element['url']
                print(" - " + tabUrl)
                if targeted_tab in tabUrl:
                    targetTabId = tabId
                tabId = tabId + 1

            # connect to the target tab via the WS debug URL
            uri = resp_json[targetTabId]['webSocketDebuggerUrl']
            async with websockets.connect(uri) as ws:
                print(f"\n\n{SS_LOGGING_PREFIX}Attached to interesting tab with URL: {resp_json[targetTabId]['url']}\nWaiting for new interesting requests!\n\n")
                # once connected, enable network tracking
                await ws.send(json.dumps({ 'id': 1, 'method': 'Network.enable' }))

                while True:
                    # print event notifications from Chrome to the console
                    event = await ws.recv()
                    if(interesting_url in event):
                        ogEvent = json.loads(event)
                        # print([SS_LOGGING_PREFIX, 'Interesting event just happened!!!', ogEvent])

                        if 'method' in ogEvent and ogEvent['method'] == 'Network.responseReceived':
                            # print([SS_LOGGING_PREFIX, 'Interesting event just happened!!!', ogEvent])
                            requestId = ogEvent['params']['requestId']
                            type = ogEvent['params']['type']
                            if "xhr" in type.lower():
                                print(f"{SS_LOGGING_PREFIX}Trying to fetch body for interesting event with type: {type} and request id: {requestId}")
                                message = await ws.recv()
                                while "Network.loadingFinished" not in message:
                                    message = await ws.recv()

                                await sendCommand(ws, "Network.getResponseBody", {"requestId":requestId})
                                eventBody = await ws.recv()
                                # print(f"{SS_LOGGING_PREFIX}Data returned for {requestId} was: {eventBody}")
                                if "result" in eventBody:
                                    eventResponseParsed = json.loads(eventBody)
                                    print(SS_LOGGING_PREFIX, 'Interesting event just happened!!!')
                                    pp.pprint(eventResponseParsed)
                            


print(f"OBSERVE SCRIPT VERSION {VERSION} {'WITH' if ALLOW_BROWSER_REFRESHING else 'WITHOUT' } BROWSER REFRESHING STARTING!")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main())