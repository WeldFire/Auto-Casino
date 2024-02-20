import asyncio
import websockets
import json
import aiohttp
import pprint
import observer_gui
import basicstrategy

ALLOW_BROWSER_REFRESHING = False
USE_GUI = True

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

    if USE_GUI:
        asyncio.create_task(observer_gui.start_gui())

    observer_gui.updateStatus("Auto Casino Starting")

    SS_LOGGING_PREFIX = 'Observer - '
    # Chrome runs an HTTP handler listing available tabs
    async with aiohttp.ClientSession() as session:
        async with session.get(spy_host_address) as resp:
            observer_gui.updateStatus("Attached to a chromium instance!")
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
                observer_gui.updateStatus("Attached to Blackjack Tab!")
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
                                    if "body" in eventResponseParsed["result"]:
                                        print(SS_LOGGING_PREFIX, 'Interesting event just happened!!!')
                                        parsedBody = json.loads(eventResponseParsed["result"]["body"])
                                        pp.pprint(parsedBody)
                                        process_blackjack_response(parsedBody)

def process_blackjack_response(eventResponseParsed):
    dealersCards = []
    playersCards = []
    # playOutcome > dealerHand > cards[]
    # playOutcome > playerHands[] > 0 > hand > cards[]
    if "playOutcome" in eventResponseParsed:
        playOutcome = eventResponseParsed["playOutcome"]

        # Dealer Hand Parsing
        if "dealerHand" in playOutcome:
            dealerHand = playOutcome["dealerHand"]
            dealersCards = dealerHand["cards"]

            cardString = ""
            for card in dealerHand["cards"]:
                cardString = f"{cardString}, {card['symbol']} of {card['suit']}"

            observer_gui.updateDealerCards(cardString[1:])

        # Player Hand Parsing
        if "playerHands" in playOutcome:
            playerHands = playOutcome["playerHands"]
            firstPlayerHand = playerHands[0]

            playersCards = firstPlayerHand["hand"]["cards"]

            cardString = ""
            for card in firstPlayerHand["hand"]["cards"]:
                cardString = f"{cardString}, {card['symbol']} of {card['suit']}"

            observer_gui.updatePlayerCards(cardString[1:])

            if "winType" in firstPlayerHand:
                observer_gui.updateAction(f"GameFinished - {firstPlayerHand['winType']}")
            else:
                playersCardOutput = calculateCardOutput(playersCards)
                dealersCardOutput = calculateCardOutput(dealersCards)
                action = basicstrategy.calculate_basic_strategy(playersCardOutput, dealersCardOutput)
                observer_gui.updateAction(f"InGame - You should {action}")

def parseCardtoScore(card):
    if card == "ONE":
        return 1
    elif card == "TWO":
        return 2
    elif card == "THREE":
        return 3
    elif card == "FOUR":
        return 4
    elif card == "FIVE":
        return 5
    elif card == "SIX":
        return 6
    elif card == "SEVEN":
        return 7
    elif card == "EIGHT":
        return 8
    elif card == "NINE":
        return 9
    elif card == "TEN" or card == "JACK" or card == "QUEEN" or card == "KING":
        return 10
    elif card == "ACE":
        return 0
    else:
        return -100


def calculateCardOutput(cards):
    cardScore = 0
    aces_in_cards = 0
    for card in cards:
        cardSymbol = card["symbol"]
        if cardSymbol == "ACE":
            aces_in_cards = aces_in_cards + 1

        cardScore = cardScore + parseCardtoScore(cardSymbol)

    cardOutput = ""
    if len(cards) == 2:
        if cards[0]["symbol"] == "ACE" or cards[1]["symbol"] == "ACE":
            cardOutput = f"A{cardScore}"
        elif cards[0]["symbol"] == cards[1]["symbol"]:
            cardOutput = parseCardtoScore(card[0]) + parseCardtoScore(card[1])
        else:
            cardOutput = f"{cardScore}"
    elif aces_in_cards > 0:
        if cardScore + aces_in_cards + 10 <= 21:
            cardOutput = f"{cardScore + aces_in_cards + 10}"
        else:
            cardOutput = f"{cardScore + aces_in_cards}"
    else:
        cardOutput = f"{cardScore}"

    return cardOutput

print(f"OBSERVE SCRIPT VERSION {VERSION} {'WITH' if ALLOW_BROWSER_REFRESHING else 'WITHOUT' } BROWSER REFRESHING STARTING!")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main())